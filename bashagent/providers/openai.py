"""OpenAI chat-completions provider.

The client is constructed only when an API key is present. Nothing in the test
suite calls the network: ``complete`` is the only method that would, and tests
that exercise it inject an opener.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from bashagent.providers.base import CompletionRequest, ProviderError, RawResponse

API_URL = "https://api.openai.com/v1/chat/completions"
_OPENER = Callable[[urllib.request.Request, float], Any]


class MissingAPIKeyError(ProviderError):
    """``OPENAI_API_KEY`` is missing or blank. The provider refuses to start."""


class OpenAIProvider:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        timeout_s: float = 60.0,
        opener: _OPENER | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if key is None or not key.strip():
            raise MissingAPIKeyError(
                "OPENAI_API_KEY is not set. bashagent will not call OpenAI without it. "
                "Export the variable, or pass --provider fake to run without a key."
            )
        self._api_key = key.strip()
        self.model = model
        self._timeout_s = timeout_s
        self._opener = opener or urllib.request.urlopen

    def complete(self, request: CompletionRequest) -> RawResponse:
        body = {
            "model": request.model or self.model,
            "temperature": request.temperature,
            "max_completion_tokens": request.max_output_tokens,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "bash_command",
                    "strict": True,
                    "schema": request.json_schema,
                },
            },
        }
        raw = json.dumps(body).encode("utf-8")
        http_request = urllib.request.Request(
            API_URL,
            data=raw,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with self._opener(http_request, self._timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ProviderError(f"OpenAI returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"OpenAI request failed: {exc.reason}") from exc
        latency_ms = (time.perf_counter() - started) * 1000
        try:
            text = payload["choices"][0]["message"]["content"]
            usage = payload.get("usage") or {}
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("OpenAI response did not contain a message.") from exc
        return RawResponse(
            text=text or "",
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency_ms,
            model=str(payload.get("model") or request.model),
        )
