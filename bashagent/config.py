"""Defaults, environment variables, and an optional config file.

Precedence is command-line flag, then environment, then
``~/.config/bashagent/config.toml``, then the built-in default.
The default provider is ``fake`` so the tool runs without an API key and a
key sitting in the environment is not spent by accident.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from bashagent.platform import CHOICES
from bashagent.prompt import MAX_OUTPUT_TOKENS, TEMPERATURE, ExplainLevel

DEFAULT_PROVIDER = "fake"
DEFAULT_MODEL = "gpt-5-mini"
EXPLAIN_LEVELS = frozenset({"kort", "lång"})
PROVIDERS = frozenset({"fake", "openai"})


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    platform: str
    explain_level: ExplainLevel
    temperature: float
    max_output_tokens: int
    no_clipboard: bool
    json_output: bool
    no_cache: bool
    cache_dir: Path


def load_settings(
    *,
    provider: str | None = None,
    model: str | None = None,
    platform: str | None = None,
    explain_level: str | None = None,
    no_clipboard: bool = False,
    json_output: bool = False,
    no_cache: bool = False,
    cache_dir: Path | None = None,
    config_path: Path | None = None,
) -> Settings:
    file_config = _read_config(config_path if config_path is not None else default_config_path())
    resolved_provider = _pick(
        provider, "BASHAGENT_PROVIDER", file_config, "provider", DEFAULT_PROVIDER
    )
    resolved_model = _pick(model, "BASHAGENT_MODEL", file_config, "model", DEFAULT_MODEL)
    resolved_platform = _pick(platform, "BASHAGENT_PLATFORM", file_config, "platform", "auto")
    resolved_explain = _pick(
        explain_level,
        "BASHAGENT_EXPLAIN_LEVEL",
        file_config,
        "explain_level",
        "kort",
    )
    if resolved_provider not in PROVIDERS:
        raise ValueError(f"provider must be one of: {', '.join(sorted(PROVIDERS))}")
    if resolved_platform not in CHOICES:
        raise ValueError("platform must be one of: auto, bsd, gnu")
    explain: ExplainLevel
    if resolved_explain == "lång":
        explain = "lång"
    elif resolved_explain == "kort":
        explain = "kort"
    else:
        raise ValueError("explain-level must be one of: kort, lång")
    return Settings(
        provider=resolved_provider,
        model=resolved_model,
        platform=resolved_platform,
        explain_level=explain,
        temperature=TEMPERATURE,
        max_output_tokens=_max_tokens(file_config),
        no_clipboard=no_clipboard,
        json_output=json_output,
        no_cache=no_cache,
        cache_dir=cache_dir if cache_dir is not None else default_cache_dir(),
    )


def default_config_path() -> Path:
    override = os.environ.get("BASHAGENT_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "bashagent" / "config.toml"


def default_cache_dir() -> Path:
    override = os.environ.get("BASHAGENT_CACHE_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "bashagent"


def load_dotenv(path: Path | None = None) -> None:
    """Set variables from ``.env`` only when they are not already set.

    Values already in the environment win. The file is never required.
    """
    env_path = path if path is not None else Path(".env")
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            os.environ.setdefault(key, value)


def _pick(
    flag: str | None,
    env_name: str,
    file_config: dict[str, object],
    file_key: str,
    default: str,
) -> str:
    if flag is not None:
        return flag
    env_value = os.environ.get(env_name)
    if env_value:
        return env_value
    file_value = file_config.get(file_key)
    if isinstance(file_value, str) and file_value:
        return file_value
    return default


def _max_tokens(file_config: dict[str, object]) -> int:
    raw = os.environ.get("BASHAGENT_MAX_OUTPUT_TOKENS")
    if raw is None:
        file_value = file_config.get("max_output_tokens")
        raw = str(file_value) if isinstance(file_value, int) else None
    if raw is None:
        return MAX_OUTPUT_TOKENS
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("max_output_tokens must be an integer") from exc
    if value < 1:
        raise ValueError("max_output_tokens must be positive")
    return value


def _read_config(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        loaded = tomllib.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must be a TOML table")
    return loaded
