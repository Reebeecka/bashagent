"""String comparison for commands. This module does not run them."""

from __future__ import annotations

import re
from typing import Any


def normalize_command(command: str) -> str:
    """Collapse whitespace, unify quotes, and sort clusters of short flags."""
    text = " ".join(command.replace('"', "'").split())
    return _FLAG_CLUSTER.sub(_sort_flags, text)


def reference_for(task: dict[str, Any], platform: str) -> str:
    reference = task["reference"]
    if platform in reference:
        return str(reference[platform])
    return str(reference["default"])


def variant_match(command: str, task: dict[str, Any], platform: str) -> bool:
    expected = {normalize_command(reference_for(task, platform))}
    for variant in task.get("accepted_variants") or []:
        expected.add(normalize_command(str(variant)))
    return normalize_command(command) in expected


def _sort_flags(match: re.Match[str]) -> str:
    body = match.group(0)[1:]
    if body.isalpha():
        return "-" + "".join(sorted(body))
    return match.group(0)


_FLAG_CLUSTER = re.compile(r"(?<!\S)-[A-Za-z]+(?!\S)")
