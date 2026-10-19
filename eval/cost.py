"""Price a run from token counts and stop it when the cap is crossed.

Prices are the uncached input rate plus the output rate. A cached prompt is
billed as if it were new, so the cap trips early rather than late.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_PRICES = ROOT / "pricing.yaml"
DEFAULT_CAP_USD = 1.0


class RunCostExceeded(RuntimeError):
    """A run's paid total passed ``max_run_cost_usd``. No further call is made."""

    def __init__(self, paid_usd: float, cap_usd: float) -> None:
        self.paid_usd = paid_usd
        self.cap_usd = cap_usd
        super().__init__(
            f"Stopped: this run reached {paid_usd:.6f} USD, above the {cap_usd:.2f} USD cap. "
            "No further calls were made."
        )


class UnpricedModelError(RuntimeError):
    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(f"No price is recorded for {model}. The run will not call it.")


def load_prices(path: Path = DEFAULT_PRICES) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not isinstance(loaded.get("models"), dict):
        raise ValueError(f"{path} has no models table")
    return loaded


def refuse_reason(model: str) -> str | None:
    """gpt-5-mini rejects temperature 0, so the eval never selects it."""
    if model == "gpt-5-mini" or model.startswith("gpt-5-mini-"):
        return "gpt-5-mini refuses temperature 0 and is not used."
    return None


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    prices: dict[str, Any] | None = None,
) -> float:
    table = prices if prices is not None else load_prices()
    chosen = _match_model(model, table["models"])
    row = table["models"][chosen]
    per_input = float(row["input_per_million"])
    per_output = float(row["output_per_million"])
    return (input_tokens * per_input + output_tokens * per_output) / 1_000_000


@dataclass
class Ledger:
    cap_usd: float
    paid_usd: float = 0.0
    cached_usd: float = 0.0
    paid_calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def note(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        *,
        paid: bool,
        prices: dict[str, Any] | None = None,
    ) -> None:
        amount = cost_usd(model, input_tokens, output_tokens, prices)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if not paid:
            self.cached_usd += amount
            self.cache_hits += 1
            return
        self.paid_usd += amount
        self.paid_calls += 1
        if self.paid_usd > self.cap_usd:
            raise RunCostExceeded(self.paid_usd, self.cap_usd)

    def over_cap(self) -> bool:
        return self.paid_usd > self.cap_usd


def _match_model(model: str, models: dict[str, Any]) -> str:
    if model in models:
        return model
    best: str | None = None
    for name in models:
        if model.startswith(name) and (best is None or len(name) > len(best)):
            best = name
    if best is None:
        raise UnpricedModelError(model)
    return best
