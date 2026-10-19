from dataclasses import replace

from bashagent.cache import CallIdentity, DiskCache, cache_key
from bashagent.providers.base import RawResponse
from bashagent.schema import SUGGESTION_JSON_SCHEMA


def _identity() -> CallIdentity:
    return CallIdentity(
        system_prompt="system",
        user_prompt="hitta pdf",
        prompt_version="0.1.0",
        model_id="fake",
        temperature=0.0,
        max_output_tokens=400,
        platform_mode="gnu",
        json_schema=SUGGESTION_JSON_SCHEMA,
        provider="fake",
    )


def test_same_identity_has_the_same_key():
    assert cache_key(_identity()) == cache_key(_identity())


def test_every_identity_field_changes_the_key():
    base = _identity()
    key = cache_key(base)
    variants = [
        replace(base, system_prompt=base.system_prompt + "x"),
        replace(base, user_prompt=base.user_prompt + "x"),
        replace(base, prompt_version="0.2.0"),
        replace(base, model_id="other"),
        replace(base, temperature=1.0),
        replace(base, max_output_tokens=200),
        replace(base, platform_mode="auto"),
        replace(base, json_schema={"type": "object"}),
        replace(base, provider="openai"),
    ]
    assert len({cache_key(item) for item in variants}) == len(variants)
    for item in variants:
        assert cache_key(item) != key


def test_roundtrip_does_not_store_a_secret(tmp_path):
    cache = DiskCache(tmp_path)
    identity = _identity()
    response = RawResponse(
        text='{"command":"ls"}',
        input_tokens=12,
        output_tokens=4,
        latency_ms=3.5,
        model="fake",
    )
    path = cache.put(identity, response)
    loaded = cache.get(identity)
    assert loaded == response
    body = path.read_text(encoding="utf-8")
    assert "api_key" not in body
    assert "Bearer" not in body
    assert '"id"' in body
    assert cache.get(replace(identity, model_id="other")) is None
