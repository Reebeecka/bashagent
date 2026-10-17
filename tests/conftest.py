import pytest


@pytest.fixture(autouse=True)
def _isolate_home_config(tmp_path, monkeypatch):
    """Keep tests off the real home directory, cache, and any API key."""
    monkeypatch.setenv("BASHAGENT_CONFIG", str(tmp_path / "no-config.toml"))
    monkeypatch.setenv("BASHAGENT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BASHAGENT_PROVIDER", raising=False)
    monkeypatch.delenv("BASHAGENT_MODEL", raising=False)
    monkeypatch.delenv("BASHAGENT_PLATFORM", raising=False)
    monkeypatch.delenv("BASHAGENT_EXPLAIN_LEVEL", raising=False)
