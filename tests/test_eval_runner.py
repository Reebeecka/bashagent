import json
from pathlib import Path

from eval.runner import main, run_eval


def test_fake_provider_parses_the_draft_set(tmp_path, capsys):
    assert run_eval(provider_name="fake", platform_mode="gnu", cache_dir=tmp_path / "gnu") == 0
    gnu = capsys.readouterr().out
    assert "Not a measurement" in gnu
    assert "No commands were executed." in gnu
    assert run_eval(provider_name="fake", platform_mode="bsd", cache_dir=tmp_path / "bsd") == 0


def test_unpriced_model_is_refused(capsys):
    code = main(["--provider", "openai", "--model", "not-a-priced-model", "--smoke"])
    assert code == 1
    assert "No price" in capsys.readouterr().out


def test_product_and_eval_do_not_shell_out():
    roots = [Path("bashagent"), Path("eval")]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "shell=True" not in text
            assert "os.system" not in text


def test_string_eval_does_not_call_docker():
    source = Path("eval/runner.py").read_text(encoding="utf-8")
    assert "docker" not in source


def test_results_jsonl_has_one_row_per_task(tmp_path):
    results = tmp_path / "results"
    code = run_eval(
        provider_name="fake",
        platform_mode="gnu",
        cache_dir=tmp_path / "cache",
        model="gpt-4.1-mini",
        results_dir=results,
        execute_reading=False,
    )
    assert code == 0
    rows = [
        json.loads(line)
        for line in (results / "gpt-4.1-mini.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 54
    assert set(rows[0]) == {
        "task_id",
        "category",
        "difficulty",
        "command",
        "correct",
        "model_risk",
        "net_risk",
        "input_tokens",
        "output_tokens",
        "tokens",
        "cost_usd",
        "latency_ms",
    }
    assert all(isinstance(row["correct"], bool) for row in rows)
    assert all(row["tokens"] == row["input_tokens"] + row["output_tokens"] for row in rows)
    assert all(isinstance(row["cost_usd"], float) for row in rows)
    assert all(row["net_risk"] for row in rows)


def test_cache_only_does_not_call_the_provider(tmp_path, monkeypatch, capsys):
    def explode(*_args, **_kwargs):
        raise AssertionError("provider was called")

    monkeypatch.setattr("eval.runner.get_provider", explode)
    code = run_eval(
        provider_name="openai",
        platform_mode="gnu",
        cache_dir=tmp_path / "empty",
        model="gpt-4.1-mini",
        cache_only=True,
        execute_reading=False,
        results_dir=tmp_path / "results",
    )
    assert code == 1
    assert "No cached response" in capsys.readouterr().out
    assert not (tmp_path / "results").exists()
