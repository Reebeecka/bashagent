"""Run one hand-written reference in a disposable Debian container.

The product never calls this module. Destructive commands are refused by
``eval.validate`` before they get here. One container at a time, on the
container's normal writable layer: no tmpfs, no bind mount.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from eval.fixtures import generate

IMAGE = "bashagent-eval:bookworm"
KEEPALIVE_SECONDS = "180"
COMMAND_TIMEOUT_SECONDS = 10
TRANSFER_TIMEOUT_SECONDS = 60

_GATE = threading.Lock()
_DOCKER: list[str] | None = None


@dataclass(frozen=True)
class ContainerRun:
    exit_code: int
    stdout: str
    stderr: str
    root: Path


def create_argv(name: str, *, docker: list[str] | None = None) -> list[str]:
    """Argv for the task container. No mount and no tmpfs."""
    base = ["docker"] if docker is None else list(docker)
    argv = [
        *base,
        "create",
        "--name",
        name,
        "--memory=512m",
        "--pids-limit=256",
        "--cpus=1",
        "--network=none",
        IMAGE,
        "sleep",
        KEEPALIVE_SECONDS,
    ]
    if "--tmpfs" in argv or "-v" in argv or "--mount" in argv:
        raise RuntimeError("the fixture must stay on the container's writable layer")
    return argv


def docker_argv() -> list[str]:
    """``docker`` or ``sudo docker``, depending on who can talk to the daemon."""
    global _DOCKER
    if _DOCKER is not None:
        return list(_DOCKER)
    override = os.environ.get("BASHAGENT_DOCKER", "").strip()
    if override:
        _DOCKER = override.split()
        return list(_DOCKER)
    probe = subprocess.run(["docker", "info"], capture_output=True)
    _DOCKER = ["docker"] if probe.returncode == 0 else ["sudo", "docker"]
    return list(_DOCKER)


def ensure_image() -> None:
    """Build the eval image. Docker's own log stays out of the task report."""
    base = docker_argv()
    dockerfile = Path(__file__).resolve().parent / "Dockerfile"
    completed = subprocess.run(
        [*base, "build", "-t", IMAGE, "-f", str(dockerfile), str(dockerfile.parent)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(detail or "docker build failed")


def pack_tree(root: Path) -> bytes:
    """Tar a fixture. Symlinks stay symlinks; mtimes and modes stay put."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        paths = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        for path in paths:
            archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
    return buffer.getvalue()


def unpack_tree(payload: bytes, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        archive.extractall(root, filter="fully_trusted")


@contextmanager
def container_run(
    command: str,
    *,
    timeout: float = COMMAND_TIMEOUT_SECONDS,
) -> Iterator[ContainerRun]:
    """Generate a fixture, run ``command`` in a fresh container, yield the result.

    The result directory is deleted when the caller leaves the ``with`` block.
    """
    if not _GATE.acquire(blocking=False):
        raise RuntimeError("Refusing to start a second container. One at a time.")
    name = f"bashagent-val-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    host = Path(tempfile.mkdtemp(prefix="bashagent-host-"))
    result = Path(tempfile.mkdtemp(prefix="bashagent-out-"))
    try:
        fixture = host / "fixture"
        generate(fixture)
        payload = pack_tree(fixture)
        base = docker_argv()
        subprocess.run(create_argv(name, docker=base), check=True, capture_output=True)
        subprocess.run([*base, "start", name], check=True, capture_output=True)
        _transfer(
            [*base, "exec", "-i", name, "tar", "-xf", "-", "-C", "/work"],
            payload,
        )
        completed = subprocess.run(
            [
                *base,
                "exec",
                "-w",
                "/work",
                "-e",
                "LC_ALL=C.UTF-8",
                name,
                "sh",
                "-c",
                command,
            ],
            capture_output=True,
            timeout=timeout,
        )
        packed = _transfer(
            [*base, "exec", name, "tar", "-cf", "-", "-C", "/work", "."],
            b"",
        )
        unpack_tree(packed, result)
        yield ContainerRun(
            exit_code=completed.returncode,
            stdout=completed.stdout.decode("utf-8"),
            stderr=completed.stderr.decode("utf-8"),
            root=result,
        )
    finally:
        subprocess.run(
            [*docker_argv(), "rm", "-f", name],
            capture_output=True,
        )
        shutil.rmtree(host, ignore_errors=True)
        shutil.rmtree(result, ignore_errors=True)
        _GATE.release()


def _transfer(argv: list[str], payload: bytes) -> bytes:
    completed = subprocess.run(
        argv,
        input=payload,
        capture_output=True,
        check=True,
        timeout=TRANSFER_TIMEOUT_SECONDS,
    )
    return completed.stdout
