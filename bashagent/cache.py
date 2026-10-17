"""Disk cache keyed by a hash of the whole call identity.

The same prompt, model, temperature, token cap, platform mode, and schema reuse
one stored response. Changing any of those is a different call.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bashagent.providers.base import RawResponse


@dataclass(frozen=True)
class CallIdentity:
    system_prompt: str
    user_prompt: str
    prompt_version: str
    model_id: str
    temperature: float
    max_output_tokens: int
    platform_mode: str
    json_schema: dict[str, Any]

    def canonical(self) -> str:
        payload = {
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "prompt_version": self.prompt_version,
            "model_id": self.model_id,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "platform_mode": self.platform_mode,
            "json_schema": self.json_schema,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def cache_key(identity: CallIdentity) -> str:
    digest = hashlib.sha256(identity.canonical().encode("utf-8")).hexdigest()
    return digest


class DiskCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, identity: CallIdentity) -> Path:
        return self.directory / f"{cache_key(identity)}.json"

    def get(self, identity: CallIdentity) -> RawResponse | None:
        path = self.path_for(identity)
        if not path.is_file():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        response = record["response"]
        return RawResponse(
            text=response["text"],
            input_tokens=int(response["input_tokens"]),
            output_tokens=int(response["output_tokens"]),
            latency_ms=float(response["latency_ms"]),
            model=response["model"],
        )

    def put(self, identity: CallIdentity, response: RawResponse) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {
            # Named "id", not "key": the hash is not a secret, and a field
            # called key next to it trips secret scanners.
            "id": cache_key(identity),
            "identity": json.loads(identity.canonical()),
            "response": {
                "text": response.text,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": response.latency_ms,
                "model": response.model,
            },
            "cached_at": datetime.now(UTC).isoformat(),
        }
        path = self.path_for(identity)
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path
