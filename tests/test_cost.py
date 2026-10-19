import json

from bashagent.providers.base import RawResponse
from eval.behavior import is_reading_task, may_execute
from eval.cost import Ledger, RunCostExceeded, cost_usd, refuse_reason
from eval.runner import main, run_eval


def test_prices_match_the_recorded_table():
    assert cost_usd("gpt-4.1-mini", 1_000_000, 0) == 0.40
    assert cost_usd("gpt-4.1-mini", 0, 1_000_000) == 1.60
    assert cost_usd("gpt-4.1", 1_000_000, 1_000_000) == 10.0
    assert cost_usd("gpt-4.1-mini-2025-04-14", 1_000_000, 0) == 0.40


def test_gpt_5_mini_is_refused_before_any_call(capsys):
    assert refuse_reason("gpt-5-mini")
    assert refuse_reason("gpt-5-mini-2025-08-07")
    assert refuse_reason("gpt-4.1-mini") is None
    code = main(["--provider", "openai", "--model", "gpt-5-mini", "--smoke"])
    assert code == 1
    assert "temperature 0" in capsys.readouterr().out


def test_cap_stops_before_a_second_paid_call(monkeypatch, tmp_path):
    calls: list[object] = []

    class Stub:
        def complete(self, request: object) -> RawResponse:
            calls.append(request)
            return RawResponse(
                text=json.dumps(
                    {
                        "command": "ls",
                        "explanation": "Listar.",
                        "risk": "safe",
                        "risk_reason": "Läser bara.",
                        "platform_notes": "Lika.",
                    }
                ),
                input_tokens=1_000_000,
                output_tokens=1_000_000,
                latency_ms=1.0,
                model="gpt-4.1-mini",
            )

    monkeypatch.setattr("eval.runner.get_provider", lambda *args, **kwargs: Stub())
    monkeypatch.setattr("eval.runner.load_tasks", lambda path: [_variant("one"), _variant("two")])
    code = run_eval(
        provider_name="openai",
        model="gpt-4.1-mini",
        cache_dir=tmp_path,
        max_run_cost_usd=1.0,
        execute_reading=False,
    )
    assert code == 2
    assert len(calls) == 1


def test_reading_gate_blocks_a_destructive_command():
    reading = {
        "method": "behavior",
        "compare": "stdout",
        "risk_label": "safe",
        "reference": {"default": "find . -type f -name '*.pdf' -size +10M"},
    }
    assert is_reading_task(reading)
    assert may_execute(reading, "find . -type f -name '*.pdf' -size +10M")
    assert not may_execute(reading, "find . -type f -name '*.tmp' -delete")
    destructive = {
        "method": "variants",
        "risk_label": "destructive",
        "compare": "stdout",
        "reference": {"default": "find . -type f -name '*.tmp' -delete"},
    }
    assert not may_execute(destructive, "find . -type f -name '*.tmp' -delete")


def test_ledger_ignores_cache_hits_for_the_cap():
    ledger = Ledger(cap_usd=1.0)
    ledger.note("gpt-4.1-mini", 1000, 1000, paid=False)
    assert ledger.paid_usd == 0
    assert ledger.cache_hits == 1
    try:
        ledger.note("gpt-4.1", 1_000_000, 0, paid=True)
    except RunCostExceeded:
        pass
    assert ledger.paid_calls == 1
    assert ledger.paid_usd == 2.0


def _variant(task_id: str) -> dict[str, object]:
    return {
        "id": task_id,
        "prompt_sv": "lista filer",
        "risk_label": "safe",
        "method": "variants",
        "reference": {"default": "ls", "status": "draft"},
    }
