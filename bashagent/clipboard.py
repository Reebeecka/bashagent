"""Copy a command string to the clipboard. Never execute it.

The string is written to a clipboard tool's standard input. It is not passed
as a shell command, and nothing in this module appends a newline, so pasting
does not press Enter. If no tool exists, the caller still prints the command
and can emit an OSC 52 sequence for terminals that support it.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass

Which = Callable[[str], str | None]
Run = Callable[[list[str], bytes], bool]


@dataclass(frozen=True)
class ClipboardResult:
    ok: bool
    method: str
    detail: str = ""
    osc52: str | None = None


def candidate_argv(
    system: str,
    env: Mapping[str, str],
    *,
    proc_version: str = "",
) -> list[tuple[str, list[str]]]:
    """Clipboard tools to try, most likely first. Existence is checked later."""
    mac = ("pbcopy", ["pbcopy"])
    wayland = ("wl-copy", ["wl-copy"])
    xclip = ("xclip", ["xclip", "-selection", "clipboard"])
    xsel = ("xsel", ["xsel", "--clipboard", "--input"])
    wsl = ("clip.exe", ["clip.exe"])
    graphical = [wayland, xclip, xsel]
    name = system.lower()
    if name == "darwin":
        return [mac, *graphical, wsl]
    if _is_wsl(env, proc_version):
        return [wsl, *graphical, mac]
    if env.get("WAYLAND_DISPLAY"):
        return [*graphical, wsl, mac]
    if env.get("DISPLAY"):
        return [xclip, xsel, wayland, wsl, mac]
    return [*graphical, wsl, mac]


def copy_text(
    text: str,
    *,
    system: str,
    env: Mapping[str, str],
    which: Which,
    run: Run,
    proc_version: str = "",
) -> ClipboardResult:
    """Try the fallback chain. ``run`` receives argv and the raw command bytes."""
    for method, argv in candidate_argv(system, env, proc_version=proc_version):
        if which(argv[0]) is None:
            continue
        if run(argv, text.encode("utf-8")):
            return ClipboardResult(ok=True, method=method, detail=f"Copied with {method}.")
    return ClipboardResult(
        ok=True,
        method="osc52",
        detail="No clipboard program found; falling back to OSC 52.",
        osc52=osc52(text),
    )


def osc52(text: str) -> str:
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"\033]52;c;{payload}\a"


def _is_wsl(env: Mapping[str, str], proc_version: str) -> bool:
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP"):
        return True
    return "microsoft" in proc_version.lower()
