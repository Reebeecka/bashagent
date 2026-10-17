"""Deterministic fixture tree for the eval suite.

The tree is small on purpose. ``large.pdf`` is a sparse file: ``find -size``
sees the logical size, while ``du`` counts allocated blocks and will report
almost nothing. Directory-size tasks must use the real bytes in the text
files, not the sparse file. Timestamps are fixed so two generations match.
"""

from __future__ import annotations

import gzip
import io
import os
import tarfile
from pathlib import Path

SEED = 40
EXPECTED_404_COUNT = 7
LARGE_PDF_BYTES = 12 * 1024 * 1024
MTIME_OLD = 1_700_000_000
MTIME_NEW = 1_760_000_000


def generate(root: Path, *, seed: int = SEED) -> Path:
    """Create the fixture under ``root``. Refuses to write into a non-empty directory."""
    del seed  # The tree is fixed; the parameter reserves the seed the full set will use.
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise FileExistsError(f"{root} is not empty")

    _write(root / "docs" / "readme.txt", "notes\n", mtime=MTIME_OLD)
    _write(root / "docs" / "mina anteckningar.txt", "hej\n", mtime=MTIME_OLD)
    _write(root / "docs" / "rapport åäö.txt", "åäö\n", mtime=MTIME_NEW)
    _write(root / "logs" / "access.log", _access_log(), mtime=MTIME_OLD)
    _write(root / "src" / "app.sh", "#!/bin/sh\necho app\n", mode=0o644, mtime=MTIME_OLD)
    _write(root / "src" / "my script.sh", "#!/bin/sh\necho hi\n", mode=0o644, mtime=MTIME_OLD)
    _write(root / "tmp" / "cache.tmp", "temp\n", mtime=MTIME_OLD)
    _write(root / "tmp" / "old file.tmp", "temp\n", mtime=MTIME_OLD)
    _write(root / "notes.txt", "foo and more foo\n", mtime=MTIME_NEW)
    _write(root / "big" / "small.pdf", b"%PDF-1.4\n" + b"x" * 128, mtime=MTIME_OLD)
    _write_sparse_pdf(root / "big" / "large.pdf")
    _write_archive(root / "archives" / "sample.tar.gz")
    (root / "empty").mkdir()
    link = root / "docs" / "readme-link.txt"
    link.symlink_to("readme.txt")
    return root


def manifest(root: Path) -> list[str]:
    """Stable description of the tree, for the determinism test."""
    rows: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows.append(f"link {rel} -> {os.readlink(path)}")
        elif path.is_dir():
            rows.append(f"dir {rel}")
        elif path.is_file():
            stat = path.stat()
            rows.append(
                f"file {rel} size={stat.st_size} "
                f"mode={stat.st_mode & 0o777} mtime={int(stat.st_mtime)}"
            )
    return rows


def count_404_lines(root: Path) -> int:
    log = (root / "logs" / "access.log").read_text(encoding="utf-8")
    return sum(1 for line in log.splitlines() if " 404 " in line)


def _access_log() -> str:
    lines: list[str] = []
    for index in range(20):
        status = 404 if index % 3 == 0 else 200
        lines.append(
            "192.168.0.1 - - "
            f"[01/Jan/2026:00:00:{index:02d} +0000] "
            f'"GET /item/{index} HTTP/1.1" {status} 12'
        )
    return "\n".join(lines) + "\n"


def _write(
    path: Path,
    data: str | bytes,
    *,
    mode: int = 0o644,
    mtime: int = MTIME_OLD,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    path.chmod(mode)
    os.utime(path, (mtime, mtime))


def _write_sparse_pdf(path: Path) -> None:
    """Logical size is 12 MiB. The hole is not filled with real bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
    try:
        os.write(fd, b"%PDF-1.4\n")
        os.ftruncate(fd, LARGE_PDF_BYTES)
    finally:
        os.close(fd)
    path.chmod(0o644)
    os.utime(path, (MTIME_OLD, MTIME_OLD))


def _write_archive(path: Path) -> None:
    payload = b"sample\n"
    info = tarfile.TarInfo(name="sample.txt")
    info.size = len(payload)
    info.mtime = MTIME_OLD
    info.mode = 0o644
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        archive.addfile(info, io.BytesIO(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(buffer.getvalue(), mtime=MTIME_OLD))
    path.chmod(0o644)
    os.utime(path, (MTIME_OLD, MTIME_OLD))
