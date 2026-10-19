"""Compare provider output with the draft references.

The fake provider is string-only and executes nothing. An OpenAI run uses the
disk cache, stops when the paid total passes the cap, and compares reading
tasks by running them. Destructive commands are never executed.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import yaml
from bashagent.cache import CallIdentity, DiskCache
from bashagent.config import load_dotenv
from bashagent.platform import resolve_platform
from bashagent.prompt import PROMPT_VERSION, TEMPERATURE, build_prompts
from bashagent.providers import CompletionRequest, ProviderError, get_provider
from bashagent.risk import apply_risk_net
from bashagent.schema import SUGGESTION_JSON_SCHEMA, SchemaError, parse_suggestion

from eval.behavior import compare_reading, is_reading_task, prepare_containers
from eval.compare import variant_match
from eval.cost import (
    DEFAULT_CAP_USD,
    Ledger,
    RunCostExceeded,
    UnpricedModelError,
    cost_usd,
    refuse_reason,
)
from eval.fixtures import EXPECTED_404_COUNT, count_404_lines, generate

ROOT = Path(__file__).resolve().parent
DEFAULT_TASKS = ROOT / "tasks.yaml"
DEFAULT_CACHE = ROOT / "cache"
FAKE_MODEL = "fake"

_CATEGORIES = frozenset(
    {
        "filsökning",
        "textbearbetning",
        "katalog- och diskanalys",
        "behörigheter",
        "arkiv",
        "processer",
        "git",
        "nätverk",
        "destruktiv",
    }
)
_METHODS = frozenset({"behavior", "variants"})
_RISKS = frozenset({"safe", "caution", "destructive"})
_DIFFICULTIES = frozenset({"enkel", "sammansatt"})
_REFERENCE_KEYS = frozenset({"default", "gnu", "bsd", "status"})


def build_result(
    task: dict[str, Any],
    *,
    command: str,
    correct: bool,
    model_risk: str,
    net_risk: str,
    input_tokens: int,
    output_tokens: int,
    cost: float | None,
    latency_ms: float,
) -> dict[str, Any]:
    """One JSON object for ``rapport/results/<model>.jsonl``.

    ``correct`` is the unadjusted comparison: the command held and the net's
    label matches the task. Token counts, cost, and latency come from the
    stored response. Cost is null when the model has no price row.
    """
    return {
        "task_id": str(task["id"]),
        "category": str(task["category"]),
        "difficulty": str(task["difficulty"]),
        "command": command,
        "correct": correct,
        "model_risk": model_risk,
        "net_risk": net_risk,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tokens": input_tokens + output_tokens,
        "cost_usd": cost,
        "latency_ms": latency_ms,
    }


def write_results(directory: Path, model: str, records: list[dict[str, Any]]) -> Path:
    """Replace ``directory/<model>.jsonl`` with one object per task."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{model}.jsonl"
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    path.write_text(text, encoding="utf-8")
    return path


def _priced(model: str, input_tokens: int, output_tokens: int) -> float | None:
    try:
        return cost_usd(model, input_tokens, output_tokens)
    except UnpricedModelError:
        return None


def load_tasks(path: Path) -> list[dict[str, Any]]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} does not contain a tasks list")
    if loaded.get("authoring_model") != "none":
        raise ValueError("authoring_model must be none; this draft was not written by a model")
    if loaded.get("draft") is not True or loaded.get("measurement") is not False:
        raise ValueError("tasks.yaml is a draft and must not be marked as a measurement")
    tasks = loaded.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"{path} does not contain a tasks list")
    required = {
        "id",
        "prompt_sv",
        "category",
        "difficulty",
        "method",
        "risk_label",
        "reference",
        "draft",
        "measurement",
    }
    seen: set[str] = set()
    for task in tasks:
        missing = required - set(task)
        if missing:
            raise ValueError(f"task {task.get('id', '?')} is missing {sorted(missing)}")
        task_id = str(task["id"])
        if task_id in seen:
            raise ValueError(f"duplicate task id {task_id}")
        seen.add(task_id)
        if task["draft"] is not True or task["measurement"] is not False:
            raise ValueError(f"task {task_id} must stay a draft and must not be a measurement")
        if task.get("authoring_model") not in (None, "none"):
            raise ValueError(f"task {task_id} must not name a model under evaluation")
        if task["category"] not in _CATEGORIES:
            raise ValueError(f"task {task_id} has unknown category {task['category']}")
        if task["difficulty"] not in _DIFFICULTIES:
            raise ValueError(f"task {task_id} has unknown difficulty")
        if task["method"] not in _METHODS:
            raise ValueError(f"task {task_id} has unknown method")
        if task["risk_label"] not in _RISKS:
            raise ValueError(f"task {task_id} has unknown risk_label")
        if task["risk_label"] == "destructive" and task["method"] != "variants":
            raise ValueError(f"task {task_id} is destructive and must use method variants")
        reference = task["reference"]
        if not isinstance(reference, dict) or "default" not in reference:
            raise ValueError(f"task {task_id} has no reference.default")
        extra = set(reference) - _REFERENCE_KEYS
        if extra:
            raise ValueError(f"task {task_id} has unexpected reference keys {sorted(extra)}")
        if reference.get("status") != "draft":
            raise ValueError(f"task {task_id} reference must be marked status: draft")
        if "bsd" in reference:
            gnu = reference.get("gnu", reference["default"])
            if reference["bsd"] == gnu:
                raise ValueError(f"task {task_id} repeats the same command for bsd and gnu")
        if task["method"] == "behavior" and not isinstance(task.get("expect"), dict):
            raise ValueError(f"task {task_id} is missing expect")
    return tasks


def run_eval(
    *,
    tasks_path: Path = DEFAULT_TASKS,
    provider_name: str = "fake",
    platform_mode: str = "gnu",
    cache_dir: Path = DEFAULT_CACHE,
    smoke_only: bool = False,
    no_cache: bool = False,
    model: str = FAKE_MODEL,
    max_run_cost_usd: float = DEFAULT_CAP_USD,
    execute_reading: bool | None = None,
    cache_only: bool = False,
    results_dir: Path | None = None,
) -> int:
    tasks = load_tasks(tasks_path)
    if smoke_only:
        tasks = [task for task in tasks if task.get("smoke")]
    if not tasks:
        print("No tasks selected.")
        return 1
    blocked = refuse_reason(model)
    if blocked is not None:
        print(blocked)
        return 1
    if provider_name == "openai":
        try:
            cost_usd(model, 0, 0)
        except UnpricedModelError as exc:
            print(exc)
            return 1
    resolved = resolve_platform(platform_mode)
    _check_fixture()
    live = provider_name == "openai"
    compare_reads = live if execute_reading is None else execute_reading
    provider = None
    if not cache_only:
        try:
            provider = get_provider(provider_name, model=model)
        except ProviderError as exc:
            print(exc)
            return 1
    if compare_reads and any(is_reading_task(task) for task in tasks):
        try:
            prepare_containers()
        except Exception as exc:
            print(f"Container image is not ready: {exc}")
            return 1
    cache = DiskCache(cache_dir)
    ledger = Ledger(cap_usd=max_run_cost_usd)
    rows: list[tuple[str, str, str]] = []
    records: list[dict[str, Any]] = []
    failures = 0
    for task in tasks:
        if live and ledger.paid_calls and ledger.paid_usd >= ledger.cap_usd:
            print(
                f"Stopped: paid {ledger.paid_usd:.6f} USD has reached "
                f"the {ledger.cap_usd:.2f} USD cap."
            )
            _print_report(rows, resolved, ledger, live=live)
            return 2
        system_prompt, user_prompt = build_prompts(
            task["prompt_sv"],
            platform=resolved,
            explain_level="kort",
        )
        identity = CallIdentity(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=PROMPT_VERSION,
            model_id=model,
            temperature=TEMPERATURE,
            max_output_tokens=400,
            platform_mode=platform_mode,
            json_schema=SUGGESTION_JSON_SCHEMA,
            provider=provider_name,
        )
        cached = None if no_cache else cache.get(identity)
        paid = cached is None
        if cached is None:
            if cache_only or provider is None:
                print(f"No cached response for {task['id']} ({model}).")
                _print_report(rows, resolved, ledger, live=live)
                return 1
            try:
                response = provider.complete(
                    CompletionRequest(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=model,
                        temperature=TEMPERATURE,
                        max_output_tokens=400,
                        json_schema=SUGGESTION_JSON_SCHEMA,
                    )
                )
            except ProviderError as exc:
                print(exc)
                _print_report(rows, resolved, ledger, live=live)
                return 1
            if not no_cache:
                cache.put(identity, response)
        else:
            response = cached
        if live:
            try:
                ledger.note(
                    model,
                    response.input_tokens,
                    response.output_tokens,
                    paid=paid,
                )
            except RunCostExceeded as exc:
                print(exc)
                _print_report(rows, resolved, ledger, live=live)
                return 2
        price = _priced(model, response.input_tokens, response.output_tokens)
        try:
            parsed = parse_suggestion(response.text)
        except SchemaError:
            rows.append((task["id"], "-", "unparseable"))
            records.append(
                build_result(
                    task,
                    command="",
                    correct=False,
                    model_risk="",
                    net_risk="",
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost=price,
                    latency_ms=response.latency_ms,
                )
            )
            failures += 1
            continue
        suggestion = apply_risk_net(parsed)
        outcome = _outcome(task, suggestion.command, suggestion.risk, resolved, compare_reads)
        rows.append((task["id"], suggestion.risk, outcome))
        records.append(
            build_result(
                task,
                command=suggestion.command,
                correct=outcome == "match",
                model_risk=parsed.risk,
                net_risk=suggestion.risk,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost=price,
                latency_ms=response.latency_ms,
            )
        )
    _print_report(rows, resolved, ledger, live=live)
    if results_dir is not None:
        written = write_results(results_dir, model, records)
        print(f"results: {written}")
    return 1 if failures else 0


def _outcome(
    task: dict[str, Any],
    command: str,
    risk: str,
    platform: str,
    compare_reads: bool,
) -> str:
    if compare_reads and is_reading_task(task):
        command_outcome = compare_reading(task, command)
    else:
        command_outcome = "match" if variant_match(command, task, platform) else "mismatch"
    if risk == task["risk_label"]:
        return command_outcome
    if command_outcome == "match":
        return "risk"
    return f"{command_outcome}/risk"


def _check_fixture() -> None:
    with tempfile.TemporaryDirectory(prefix="bashagent-fixture-") as directory:
        root = generate(Path(directory) / "fixture")
        found = count_404_lines(root)
        if found != EXPECTED_404_COUNT:
            raise RuntimeError(
                f"fixture access.log has {found} 404 lines, expected {EXPECTED_404_COUNT}"
            )


def _print_report(
    rows: list[tuple[str, str, str]],
    platform: str,
    ledger: Ledger,
    *,
    live: bool,
) -> None:
    width = max((len(task_id) for task_id, _, _ in rows), default=2)
    print(f"platform: {platform}")
    print(f"{'id':<{width}}  {'risk':<14} outcome")
    for task_id, risk, outcome in rows:
        print(f"{task_id:<{width}}  {risk:<14} {outcome}")
    matched = sum(1 for _, _, outcome in rows if outcome == "match")
    if live:
        print(f"{matched}/{len(rows)} held on the compared field. Not a measurement.")
        print("Destructive commands were not executed.")
        print(f"paid_calls: {ledger.paid_calls}")
        print(f"cache_hits: {ledger.cache_hits}")
        print(f"input_tokens: {ledger.input_tokens}")
        print(f"output_tokens: {ledger.output_tokens}")
        print(f"paid_usd: {ledger.paid_usd:.6f}")
        print(f"cached_usd: {ledger.cached_usd:.6f}")
        print(f"cap_usd: {ledger.cap_usd:.2f}")
    else:
        print(f"{matched}/{len(rows)} string-matched against the fake provider. Not a measurement.")
        print("No commands were executed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bashagent eval tasks.")
    parser.add_argument("--provider", default="fake", choices=["fake", "openai"])
    parser.add_argument("--platform", default="gnu", choices=["auto", "bsd", "gnu"])
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--model", default=FAKE_MODEL)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--max-run-cost-usd", type=float, default=DEFAULT_CAP_USD)
    parser.add_argument(
        "--results-dir",
        type=Path,
        help="Write one JSON object per task to <model>.jsonl in this directory.",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Use the disk cache and do not call the provider.",
    )
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    blocked = refuse_reason(args.model)
    if blocked is not None:
        print(blocked)
        return 1
    if args.max_run_cost_usd <= 0:
        print("max-run-cost-usd must be positive.")
        return 1
    return run_eval(
        tasks_path=args.tasks,
        provider_name=args.provider,
        platform_mode=args.platform,
        cache_dir=args.cache_dir,
        smoke_only=args.smoke,
        no_cache=args.no_cache,
        model=args.model,
        max_run_cost_usd=args.max_run_cost_usd,
        cache_only=args.cache_only,
        results_dir=args.results_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
