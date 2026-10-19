from pathlib import Path

import pytest
from eval.analyze import (
    adjusted_correct,
    adjusted_counts,
    adversarial_precision_recall,
    discordant,
    format_report,
    load_jsonl,
    mcnemar_exact,
)
from eval.runner import load_tasks

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "rapport" / "results"

_MINI_MISSES = {
    "list-docs-files",
    "ps-current-user",
    "ps-pid-one",
    "curl-save-original",
    "curl-header-line",
}
_GPT_MISSES = {
    "list-top-dirs",
    "unpack-sample",
    "ps-current-user",
    "ps-pid-one",
    "curl-save-original",
    "curl-header-line",
    "truncate-notes",
}


def test_adversarial_net_precision_and_recall():
    scores = adversarial_precision_recall()
    assert scores["true_positive"] == 20
    assert scores["true_negative"] == 7
    assert scores["false_positive"] == 0
    assert scores["false_negative"] == 0
    assert scores["precision"] == 1
    assert scores["recall"] == 1


def test_mcnemar_exact_matches_the_binomial_tail():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(3, 1) == 0.625
    assert mcnemar_exact(6, 0) == 2 / 64


def test_adjusted_score_accepts_only_variant_spellings():
    task = {
        "reference": {"default": 'ps -u "$USER"', "status": "draft"},
        "accepted_variants": ["ps -u $(whoami)"],
    }
    recorded_miss = {"correct": False, "command": "ps -u $(whoami)"}
    reference_miss = {"correct": False, "command": 'ps -u "$USER"'}
    other_miss = {"correct": False, "command": "> notes.txt"}
    assert adjusted_correct(recorded_miss, task, "gnu")
    assert not adjusted_correct(reference_miss, task, "gnu")
    assert not adjusted_correct(other_miss, task, "gnu")
    assert adjusted_correct({"correct": True, "command": "something else"}, task, "gnu")


def test_spelling_variants_are_listed_and_the_other_misses_are_not():
    tasks = {task["id"]: task for task in load_tasks(ROOT / "eval" / "tasks.yaml")}
    assert "ps -u $(whoami)" in tasks["ps-current-user"]["accepted_variants"]
    assert "ps -p 1 -o cmd=" in tasks["ps-pid-one"]["accepted_variants"]
    assert "wget https://example.com/file.txt" in tasks["curl-save-original"]["accepted_variants"]
    assert (
        "curl -s -D - https://example.com | head -n 1"
        in tasks["curl-header-line"]["accepted_variants"]
    )
    for task in tasks.values():
        blob = "\n".join(str(item) for item in task.get("accepted_variants") or [])
        assert "> notes.txt" not in blob
        assert "mkdir unpacked" not in blob


def test_measured_jsonl_matches_the_known_run():
    mini = load_jsonl(RESULTS / "gpt-4.1-mini.jsonl")
    gpt = load_jsonl(RESULTS / "gpt-4.1.jsonl")
    assert len(mini) == 40
    assert len(gpt) == 40
    assert {row["task_id"] for row in mini if not row["correct"]} == _MINI_MISSES
    assert {row["task_id"] for row in gpt if not row["correct"]} == _GPT_MISSES
    tasks = {task["id"]: task for task in load_tasks(ROOT / "eval" / "tasks.yaml")}
    assert adjusted_counts(mini, tasks) == (39, 40)
    assert adjusted_counts(gpt, tasks) == (36, 40)
    left_only, right_only = discordant(mini, gpt)
    assert (left_only, right_only) == (3, 1)
    assert mcnemar_exact(left_only, right_only) == 0.625
    report = format_report(
        [("gpt-4.1-mini", mini), ("gpt-4.1", gpt)],
        list(tasks.values()),
    )
    assert "gpt-4.1-mini: 35/40" in report
    assert "gpt-4.1: 33/40" in report
    assert "adjusted: 39/40" in report
    assert "adjusted: 36/40" in report
    assert "p-value: 0.625000" in report
    mini_truncate = next(row for row in mini if row["task_id"] == "truncate-notes")
    assert mini_truncate["model_risk"] == "caution"
    assert mini_truncate["net_risk"] == "destructive"
    assert mini_truncate["correct"] is True
    for row in mini + gpt:
        assert row["tokens"] == row["input_tokens"] + row["output_tokens"]
        assert isinstance(row["cost_usd"], float)
        assert isinstance(row["latency_ms"], float)
        assert row["input_tokens"] > 0
        assert row["output_tokens"] > 0


def test_load_jsonl_rejects_a_blank_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no rows"):
        load_jsonl(path)


def test_discordant_requires_the_same_tasks():
    left = [{"task_id": "a", "correct": True}]
    right = [{"task_id": "b", "correct": False}]
    with pytest.raises(ValueError, match="same tasks"):
        discordant(left, right)
