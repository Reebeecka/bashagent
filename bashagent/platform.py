"""Detect BSD (macOS) versus GNU (Linux) command syntax."""

from __future__ import annotations

import platform as platform_mod
from typing import Literal

PlatformName = Literal["bsd", "gnu"]
PlatformChoice = Literal["auto", "bsd", "gnu"]

CHOICES: frozenset[str] = frozenset({"auto", "bsd", "gnu"})


def detect_platform(*, system: str | None = None) -> PlatformName:
    """Map an operating-system name to the coreutils family we prompt for.

    Darwin is BSD. Linux, including WSL, is GNU. Anything else is treated as
    GNU because that is the reference platform for the eval suite.
    """
    name = (system if system is not None else platform_mod.system()).lower()
    if name == "darwin":
        return "bsd"
    return "gnu"


def resolve_platform(choice: str, *, system: str | None = None) -> PlatformName:
    if choice not in CHOICES:
        raise ValueError("platform must be one of: auto, bsd, gnu")
    if choice == "bsd":
        return "bsd"
    if choice == "gnu":
        return "gnu"
    return detect_platform(system=system)
