"""Check draft behavior references against the fixture.

Destructive commands are not run, not even in the container. Variant tasks
(git, network, processes, and the destructive set) are skipped. A green run
means the GNU reference produced the expected fixture result. It does not
make the draft a measurement.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bashagent.risk import classify_command

from eval.compare import normalize
from eval.docker_run import container_run, ensure_image
from eval.runner import DEFAULT_TASKS, load_tasks

DESTRUCTIVE_SKIP = "destruktivt kommando körs inte, inte ens i en container"
VARIANTS_SKIP = "method är variants; facit jämförs som sträng och körs inte"
NET_SKIP = "säkerhetsnätet klassar kommandot som destructive; det körs inte"


@dataclass(frozen=True)
class Executed:
    exit_code: int
    stdout: str
    stderr: str
    root: Path


def gnu_reference(task: dict[str, Any]) -> str:
    """The command validated on Debian. BSD-only text is never selected."""
    reference = task["reference"]
    if "gnu" in reference:
        return str(reference["gnu"])
    return str(reference["default"])


def skip_reason(task: dict[str, Any], command: str) -> str | None:
    """Why ``command`` must not be executed, or None when a container may run it."""
    if task.get("risk_label") == "destructive":
        return DESTRUCTIVE_SKIP
    if classify_command(command, home=Path("/home/user")).level == "destructive":
        return NET_SKIP
    if task.get("method") != "behavior":
        return VARIANTS_SKIP
    return None


def judge(task: dict[str, Any], executed: Executed) -> list[str]:
    """Compare one run with the task's expect block. Empty means it behaved."""
    expect = task.get("expect")
    if not isinstance(expect, dict):
        return ["behavior task has no expect block"]
    errors: list[str] = []
    want_exit = int(expect.get("exit", 0))
    if executed.exit_code != want_exit:
        detail = executed.stderr.strip().replace("\n", " ")[:240]
        errors.append(f"exit {executed.exit_code}, want {want_exit}: {detail}")
    if "lines" in expect:
        order = str(expect.get("stdout", "sorted"))
        actual = normalize(executed.stdout, order=order)
        wanted = normalize("\n".join(str(line) for line in expect["lines"]), order=order)
        if actual != wanted:
            errors.append(f"stdout mismatch\n--- actual\n{actual}\n--- want\n{wanted}")
    for rel, spec in (expect.get("paths") or {}).items():
        errors.extend(_check_path(executed.root, str(rel), spec))
    return errors


def validate(tasks_path: Path = DEFAULT_TASKS, *, build_image: bool = True) -> int:
    tasks = load_tasks(tasks_path)
    if build_image:
        ensure_image()
    ok = 0
    skipped = 0
    failed = 0
    print("authoring_model: none")
    print("draft: true")
    print("measurement: false")
    print("These references are a draft. A passing check is not a measurement.")
    for task in tasks:
        command = gnu_reference(task)
        reason = skip_reason(task, command)
        if reason is not None:
            skipped += 1
            print(f"skip  {task['id']}  {reason}")
            continue
        try:
            with container_run(command) as run:
                errors = judge(
                    task,
                    Executed(run.exit_code, run.stdout, run.stderr, run.root),
                )
        except Exception as exc:
            failed += 1
            print(f"fail  {task['id']}  {exc}")
            continue
        if errors:
            failed += 1
            print(f"fail  {task['id']}")
            for error in errors:
                print(error)
            continue
        ok += 1
        print(f"ok    {task['id']}")
    print(f"validated {ok}")
    print(f"skipped {skipped}")
    print(f"failed {failed}")
    print("Draft references only. Destructive commands were not executed.")
    return 1 if failed else 0


def _check_path(root: Path, rel: str, spec: dict[str, Any]) -> list[str]:
    path = root / rel
    exists = path.exists() or path.is_symlink()
    if spec.get("exists") is False:
        return [f"{rel} should be absent"] if exists else []
    if not exists:
        return [f"{rel} missing"]
    errors: list[str] = []
    if "mode" in spec:
        actual = path.lstat().st_mode & 0o777
        want = int(str(spec["mode"]), 8)
        if actual != want:
            errors.append(f"{rel} mode {actual:o} != {want:o}")
    if "text" in spec:
        actual_text = path.read_text(encoding="utf-8")
        if actual_text != spec["text"]:
            errors.append(f"{rel} text {actual_text!r} != {spec['text']!r}")
    if "min_size" in spec and path.stat().st_size < int(spec["min_size"]):
        errors.append(f"{rel} is smaller than {spec['min_size']} bytes")
    if "contains" in spec and spec["contains"].encode("utf-8") not in path.read_bytes():
        errors.append(f"{rel} does not contain {spec['contains']!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run draft behavior references in one container at a time."
    )
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    args = parser.parse_args(argv)
    return validate(args.tasks)


if __name__ == "__main__":
    raise SystemExit(main())
