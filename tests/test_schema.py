import json

import pytest
from bashagent.schema import SchemaError, parse_suggestion


def test_parses_raw_json():
    suggestion = parse_suggestion(
        json.dumps(
            {
                "command": "ls",
                "explanation": "Listar katalogen.",
                "risk": "safe",
                "risk_reason": "Läser bara.",
                "platform_notes": "Lika på båda.",
            }
        )
    )
    assert suggestion.command == "ls"
    assert suggestion.risk == "safe"


def _payload(**overrides: str) -> str:
    body = {
        "command": "pwd",
        "explanation": "Visar katalogen.",
        "risk": "safe",
        "risk_reason": "Läser.",
        "platform_notes": "",
    }
    body.update(overrides)
    return json.dumps(body, ensure_ascii=False)


def test_repairs_a_markdown_fence():
    text = f"Here you go:\n```json\n{_payload()}\n```\n"
    assert parse_suggestion(text).command == "pwd"


def test_extracts_the_first_object():
    text = "Sure " + _payload(command="du -h", explanation="Visar storlek.") + " thanks"
    assert parse_suggestion(text).command == "du -h"


def test_rejects_blank_command():
    text = _payload(command="  ", explanation="x", risk_reason="x")
    with pytest.raises(SchemaError):
        parse_suggestion(text)


def test_rejects_prose():
    with pytest.raises(SchemaError):
        parse_suggestion("I do not know.")
