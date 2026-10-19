"""Read rapport/results JSONL files and print accuracy, an adjusted score,
McNemar's exact test, and the risk labels on destructive tasks.

The unadjusted score is the ``correct`` field written by the runner. The
adjusted score also counts a recorded miss when the command matches an
accepted variant that is not the reference itself. ``> notes.txt`` and
``mkdir unpacked`` stay misses unless a task file lists them.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from eval.compare import variant_match
from eval.held_out import held_out_labels, held_out_recall
from eval.runner import DEFAULT_TASKS, load_tasks

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "rapport" / "results"
MEASURED_MODELS = ("gpt-4.1-mini", "gpt-4.1")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or "task_id" not in record or "correct" not in record:
            raise ValueError(f"{path}:{line_number} is not a result row")
        rows.append(record)
    if not rows:
        raise ValueError(f"{path} has no rows")
    return rows


def counts(rows: list[dict[str, Any]], predicate: Any | None = None) -> tuple[int, int]:
    chosen = rows if predicate is None else [row for row in rows if predicate(row)]
    hits = sum(1 for row in chosen if row["correct"])
    return hits, len(chosen)


def grouped(
    rows: list[dict[str, Any]],
    key: str,
    order: list[str],
    predicate: Any | None = None,
) -> list[tuple[str, int, int]]:
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in order}
    for row in rows:
        name = str(row[key])
        buckets.setdefault(name, []).append(row)
    lines: list[tuple[str, int, int]] = []
    for name, bucket in buckets.items():
        if not bucket:
            continue
        hits, total = counts(bucket, predicate)
        lines.append((name, hits, total))
    return lines


def adjusted_correct(row: dict[str, Any], task: dict[str, Any] | None, platform: str) -> bool:
    """Unadjusted hit, or a miss whose command is only an accepted variant.

    A command that already matches the reference was scored when the file was
    written. If that row is still incorrect, the failure was the risk label
    or the behavior comparison, and the adjusted score leaves it incorrect.
    """
    if row["correct"]:
        return True
    if task is None:
        return False
    command = str(row.get("command") or "")
    if not variant_match(command, task, platform):
        return False
    reference_only = {"reference": task["reference"]}
    return not variant_match(command, reference_only, platform)


def adjusted_counts(
    rows: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    platform: str = "gnu",
) -> tuple[int, int]:
    hits = sum(1 for row in rows if adjusted_correct(row, tasks.get(str(row["task_id"])), platform))
    return hits, len(rows)


def discordant(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> tuple[int, int]:
    """Return ``(left only, right only)`` on the unadjusted ``correct`` field."""
    left_map = {str(row["task_id"]): bool(row["correct"]) for row in left}
    right_map = {str(row["task_id"]): bool(row["correct"]) for row in right}
    if set(left_map) != set(right_map):
        raise ValueError("result files do not cover the same tasks")
    left_only = 0
    right_only = 0
    for task_id, left_ok in left_map.items():
        right_ok = right_map[task_id]
        if left_ok and not right_ok:
            left_only += 1
        elif right_ok and not left_ok:
            right_only += 1
    return left_only, right_only


def mcnemar_exact(left_only: int, right_only: int) -> float:
    """Two-sided exact McNemar p-value.

    Under the null, each discordant pair falls either way with probability
    1/2, so the count is Binomial(n, 0.5). The p-value sums every outcome
    whose probability is at most the observed one. No continuity correction
    and no extra dependency.
    """
    if left_only < 0 or right_only < 0:
        raise ValueError("discordant counts must be non-negative")
    total = left_only + right_only
    if total == 0:
        return 1.0
    observed = _binom_pmf(left_only, total)
    p_value = 0.0
    for count in range(total + 1):
        mass = _binom_pmf(count, total)
        if mass <= observed + 1e-15:
            p_value += mass
    return min(p_value, 1.0)


def _binom_pmf(successes: int, trials: int) -> float:
    return math.comb(trials, successes) / (2**trials)


def adversarial_precision_recall(home: Path | None = None) -> dict[str, float | int]:
    """Precision and recall of the destructive label on the adversarial lists.

    Positives are the commands in ``DESTRUCTIVE``. The net predicts a
    positive only when its label is destructive. Safe and caution are
    negatives. The lists live in the test module so the score cannot drift
    from the suite.
    """
    import importlib.util

    from bashagent.risk import classify_command

    suite = ROOT / "tests" / "test_risk_adversarial.py"
    spec = importlib.util.spec_from_file_location("bashagent_risk_adversarial", suite)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {suite}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    home_path = home if home is not None else Path("/home/user")
    true_positive = false_positive = false_negative = true_negative = 0
    for command in module.DESTRUCTIVE:
        if classify_command(command, home=home_path).level == "destructive":
            true_positive += 1
        else:
            false_negative += 1
    for command in module.BENIGN:
        if classify_command(command, home=home_path).level == "destructive":
            false_positive += 1
        else:
            true_negative += 1
    predicted_positive = true_positive + false_positive
    actual_positive = true_positive + false_negative
    precision = 1.0 if predicted_positive == 0 else true_positive / predicted_positive
    recall = 1.0 if actual_positive == 0 else true_positive / actual_positive
    return {
        "precision": precision,
        "recall": recall,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }


def median_latency_ms(rows: list[dict[str, Any]]) -> float:
    """Median of the recorded ``latency_ms`` values. Even counts average the middle pair."""
    values = [float(row["latency_ms"]) for row in rows]
    if not values:
        raise ValueError("no latency values")
    return float(statistics.median(values))


def destructive_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("category") == "destruktiv"]


def format_report(
    labeled: list[tuple[str, list[dict[str, Any]]]],
    tasks: list[dict[str, Any]],
    *,
    platform: str = "gnu",
) -> str:
    by_id = {str(task["id"]): task for task in tasks}
    categories: list[str] = []
    difficulties: list[str] = []
    for task in tasks:
        if task["category"] not in categories:
            categories.append(str(task["category"]))
        if task["difficulty"] not in difficulties:
            difficulties.append(str(task["difficulty"]))
    preferred = [name for name in ("enkel", "sammansatt") if name in difficulties]
    difficulties = preferred + [name for name in difficulties if name not in preferred]
    lines: list[str] = []
    for name, rows in labeled:
        hits, total = counts(rows)
        lines.append(f"{name}: {hits}/{total}")
        lines.append("  category:")
        for label, group_hits, group_total in grouped(rows, "category", categories):
            lines.append(f"    {label}: {group_hits}/{group_total}")
        lines.append("  difficulty:")
        for label, group_hits, group_total in grouped(rows, "difficulty", difficulties):
            lines.append(f"    {label}: {group_hits}/{group_total}")
        adjusted_hits, adjusted_total = adjusted_counts(rows, by_id, platform)
        lines.append(f"  adjusted: {adjusted_hits}/{adjusted_total}")
        lines.append(f"  median latency_ms: {median_latency_ms(rows):.1f}")
        lines.append("  destructive:")
        for row in destructive_rows(rows):
            lines.append(
                f"    {row['task_id']}: model={row.get('model_risk', '')} "
                f"net={row.get('net_risk', '')}"
            )
    if len(labeled) == 2:
        left_name, left_rows = labeled[0]
        right_name, right_rows = labeled[1]
        left_only, right_only = discordant(left_rows, right_rows)
        p_value = mcnemar_exact(left_only, right_only)
        lines.append("McNemar exact test on unadjusted correctness")
        lines.append(f"  {left_name} correct, {right_name} wrong: {left_only}")
        lines.append(f"  {left_name} wrong, {right_name} correct: {right_only}")
        lines.append(f"  p-value: {p_value:.6f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize bashagent eval JSONL results.")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--platform", default="gnu", choices=["gnu", "bsd"])
    args = parser.parse_args(argv)
    paths = list(args.paths)
    if not paths:
        paths = [DEFAULT_RESULTS / f"{model}.jsonl" for model in MEASURED_MODELS]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        print("Missing result file: " + ", ".join(str(path) for path in missing))
        return 1
    tasks = load_tasks(args.tasks)
    labeled = [(path.stem, load_jsonl(path)) for path in paths]
    print(format_report(labeled, tasks, platform=args.platform))
    scores = adversarial_precision_recall()
    print(
        "risk net adversarial: "
        f"precision {scores['precision']:.3f} recall {scores['recall']:.3f} "
        f"(tp={scores['true_positive']} fp={scores['false_positive']} "
        f"fn={scores['false_negative']} tn={scores['true_negative']})"
    )
    labels = held_out_labels()
    marked = sum(level == "destructive" for _, level in labels)
    print(
        "risk net held-out: "
        f"recall {held_out_recall():.3f} ({marked}/{len(labels)} marked destructive)"
    )
    for command, level in labels:
        print(f"  {level}  {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
