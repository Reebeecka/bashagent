"""Provider protocol. Latency and token counts are measured here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CompletionRequest:
    system_prompt: str
    user_prompt: str
    model: str
    temperature: float
    max_output_tokens: int
    json_schema: dict[str, Any]


@dataclass(frozen=True)
class RawResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model: str


class Provider(Protocol):
    def complete(self, request: CompletionRequest) -> RawResponse:
        """Return the raw model text plus the measurements for this call."""


class ProviderError(RuntimeError):
    """The provider failed before a usable response existed."""


class UnknownProviderError(ProviderError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown provider {name!r}. Expected 'fake' or 'openai'.")
        self.name = name
