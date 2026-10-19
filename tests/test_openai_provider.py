"""The OpenAI provider refuses to start without a key and is not called for real."""

import json

import pytest
from bashagent.prompt import MAX_OUTPUT_TOKENS, TEMPERATURE
from bashagent.providers.base import CompletionRequest
from bashagent.providers.openai import MissingAPIKeyError, OpenAIProvider
from bashagent.schema import SUGGESTION_JSON_SCHEMA


def test_missing_key_refuses_to_start(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        OpenAIProvider(model="gpt-5-mini")
    with pytest.raises(MissingAPIKeyError):
        OpenAIProvider(model="gpt-5-mini", api_key="  ")


def test_request_shape_uses_an_injected_opener_instead_of_the_network():
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def read(self) -> bytes:
            body = {
                "model": "gpt-5-mini",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "command": "ls",
                                    "explanation": "Listar.",
                                    "risk": "safe",
                                    "risk_reason": "Läser.",
                                    "platform_notes": "",
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            return json.dumps(body).encode("utf-8")

    def opener(request, data=None, *, timeout: float):
        # urlopen treats a second positional argument as the body, not the timeout.
        assert data is None
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.get_header("Authorization")
        return _Response()

    provider = OpenAIProvider(
        model="gpt-5-mini", api_key="present-but-not-a-real-key", opener=opener
    )
    response = provider.complete(
        CompletionRequest(
            system_prompt="system",
            user_prompt="lista",
            model="gpt-5-mini",
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            json_schema=SUGGESTION_JSON_SCHEMA,
        )
    )
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["temperature"] == 0
    assert body["max_completion_tokens"] == 400
    assert body["response_format"]["type"] == "json_schema"
    assert "present-but-not-a-real-key" not in json.dumps(body)
    assert response.text.startswith("{")
    assert response.input_tokens == 10
    assert response.output_tokens == 5
