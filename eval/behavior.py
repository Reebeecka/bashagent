"""Compare a reading command with its reference, one container at a time.

Only a safe stdout task is executed. Destructive commands, variant tasks, and
commands the risk net does not call safe are left as strings.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bashagent.risk import classify_command

from eval.compare import normalize
from eval.docker_run import container_run, ensure_image


@dataclass(frozen=True)
class Capture:
    exit_code: int
    stdout: str
    stderr: str


def is_reading_task(task: dict[str, Any]) -> bool:
    return (
        task.get("method") == "behavior"
        and task.get("compare") == "stdout"
        and task.get("risk_label") == "safe"
    )


def may_execute(task: dict[str, Any], command: str) -> bool:
    """True only for a safe read whose text the risk net also calls safe."""
    if not is_reading_task(task):
        return False
    return classify_command(command, home=Path("/home/user")).level == "safe"


def _gnu_reference(task: dict[str, Any]) -> str:
    reference = task["reference"]
    if "gnu" in reference:
        return str(reference["gnu"])
    return str(reference["default"])


def prepare_containers() -> None:
    ensure_image()


def compare_reading(task: dict[str, Any], command: str) -> str:
    """Run the reference and ``command`` in separate containers and compare stdout.

    Returns ``match``, ``mismatch``, ``error``, ``timeout``, or ``blocked``.
    ``blocked`` means the command was not executed.
    """
    reference = _gnu_reference(task)
    if not may_execute(task, command) or not may_execute(task, reference):
        return "blocked"
    try:
        reference_run = _capture(reference)
        model_run = _capture(command)
    except subprocess.TimeoutExpired:
        return "timeout"
    except (subprocess.CalledProcessError, OSError, RuntimeError):
        return "error"
    if reference_run.exit_code == 0 and model_run.exit_code != 0:
        return "error"
    if reference_run.exit_code != model_run.exit_code:
        return "mismatch"
    order = str((task.get("expect") or {}).get("stdout", "sorted"))
    actual = normalize(model_run.stdout, order=order)
    wanted = normalize(reference_run.stdout, order=order)
    if actual == wanted:
        return "match"
    return "mismatch"


def _capture(command: str) -> Capture:
    with container_run(command) as run:
        return Capture(exit_code=run.exit_code, stdout=run.stdout, stderr=run.stderr)
