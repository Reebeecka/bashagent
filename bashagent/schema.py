"""Structured model output: one command, an explanation, and a risk label."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ValidationError, field_validator

RiskName = Literal["safe", "caution", "destructive"]

# Sent to providers that support strict JSON schema mode. additionalProperties
# is false and every field is required, which is what OpenAI strict mode demands.
SUGGESTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "command": {"type": "string"},
        "explanation": {"type": "string"},
        "risk": {"type": "string", "enum": ["safe", "caution", "destructive"]},
        "risk_reason": {"type": "string"},
        "platform_notes": {"type": "string"},
    },
    "required": ["command", "explanation", "risk", "risk_reason", "platform_notes"],
}


class SchemaError(ValueError):
    """The model output was not a valid command suggestion."""


class Suggestion(BaseModel):
    command: str
    explanation: str
    risk: RiskName
    risk_reason: str
    platform_notes: str

    @field_validator("command", "explanation")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_suggestion(text: str) -> Suggestion:
    """Parse model output. One local repair, then a clear error.

    The repair strips a markdown fence and, if that is not enough, the first
    JSON object. There is no second model call: that would be another API request.
    """
    last_error: Exception | None = None
    for candidate in _candidates(text):
        try:
            return Suggestion.model_validate_json(candidate)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
    raise SchemaError(f"Model output is not a valid command suggestion: {last_error}")


def _candidates(text: str) -> list[str]:
    raw = text.strip()
    unfenced = _strip_fence(raw)
    extracted = _first_object(unfenced)
    ordered: list[str] = []
    for item in (raw, unfenced, extracted):
        if item and item not in ordered:
            ordered.append(item)
    return ordered


def _strip_fence(text: str) -> str:
    match = _FENCE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _first_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
