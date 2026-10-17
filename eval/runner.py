"""Run the example tasks against a provider. Does not execute commands.

Behavior comparison in a container is not part of this skeleton. Every task is
scored by string match against its reference. The fixture tree is generated
only so the harness can check that the generator still builds.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any

import yaml
from bashagent.cache import CallIdentity, DiskCache
from bashagent.platform import resolve_platform
from bashagent.prompt import PROMPT_VERSION, TEMPERATURE, build_prompts
from bashagent.providers import CompletionRequest, get_provider
from bashagent.risk import apply_risk_net
from bashagent.schema import SUGGESTION_JSON_SCHEMA, SchemaError, parse_suggestion

from eval.compare import variant_match
from eval.fixtures import EXPECTED_404_COUNT, count_404_lines, generate

ROOT = Path(__file__).resolve().parent
DEFAULT_TASKS = ROOT / "tasks.yaml"
DEFAULT_CACHE = ROOT / "cache"
FAKE_MODEL = "fake"


def load_tasks(path: Path) -> list[dict[str, Any]]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    tasks = loaded.get("tasks") if isinstance(loaded, dict) else None
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"{path} does not contain a tasks list")
    required = {"id", "prompt_sv", "category", "method", "risk_label", "reference"}
    for task in tasks:
        missing = required - set(task)
        if missing:
            raise ValueError(f"task {task.get('id', '?')} is missing {sorted(missing)}")
        if "default" not in task["reference"]:
            raise ValueError(f"task {task['id']} has no reference.default")
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
) -> int:
    tasks = load_tasks(tasks_path)
    if smoke_only:
        tasks = [task for task in tasks if task.get("smoke")]
    if provider_name != "fake":
        raise RuntimeError("This skeleton only runs the fake provider. No live model call is made.")
    resolved = resolve_platform(platform_mode)
    _check_fixture()
    provider = get_provider(provider_name, model=model)
    cache = DiskCache(cache_dir)
    rows: list[tuple[str, str, str]] = []
    failures = 0
    for task in tasks:
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
        )
        response = None if no_cache else cache.get(identity)
        if response is None:
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
            if not no_cache:
                cache.put(identity, response)
        try:
            suggestion = apply_risk_net(parse_suggestion(response.text))
        except SchemaError:
            rows.append((task["id"], "-", "unparseable"))
            failures += 1
            continue
        matched = variant_match(suggestion.command, task, resolved)
        outcome = "match" if matched else "mismatch"
        if suggestion.risk != task["risk_label"]:
            outcome = f"{outcome}/risk"
            failures += 1
        elif not matched:
            failures += 1
        rows.append((task["id"], suggestion.risk, outcome))
    _print_report(rows, resolved)
    return 1 if failures else 0


def _check_fixture() -> None:
    with tempfile.TemporaryDirectory(prefix="bashagent-fixture-") as directory:
        root = generate(Path(directory) / "fixture")
        found = count_404_lines(root)
        if found != EXPECTED_404_COUNT:
            raise RuntimeError(
                f"fixture access.log has {found} 404 lines, expected {EXPECTED_404_COUNT}"
            )


def _print_report(rows: list[tuple[str, str, str]], platform: str) -> None:
    print(f"platform: {platform}")
    print(f"{'id':<28} {'risk':<14} outcome")
    for task_id, risk, outcome in rows:
        print(f"{task_id:<28} {risk:<14} {outcome}")
    matched = sum(1 for _, _, outcome in rows if outcome == "match")
    print(f"{matched}/{len(rows)} matched. No commands were executed.")
    print("Behavior comparison in a container is not part of this skeleton.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bashagent eval tasks. Executes nothing.")
    parser.add_argument("--provider", default="fake", choices=["fake", "openai"])
    parser.add_argument("--platform", default="gnu", choices=["auto", "bsd", "gnu"])
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--model", default=FAKE_MODEL)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)
    if args.provider == "openai":
        print("Refusing --provider openai in this skeleton. No live model call is made.")
        return 1
    return run_eval(
        tasks_path=args.tasks,
        provider_name=args.provider,
        platform_mode=args.platform,
        cache_dir=args.cache_dir,
        smoke_only=args.smoke,
        no_cache=args.no_cache,
        model=args.model,
    )


if __name__ == "__main__":
    raise SystemExit(main())
