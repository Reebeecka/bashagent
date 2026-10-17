"""Clipboard fallback without touching a real clipboard."""

from bashagent.clipboard import candidate_argv, copy_text


def test_darwin_uses_pbcopy_stdin_and_does_not_append_a_newline():
    calls: list[tuple[list[str], bytes]] = []

    def which(name: str) -> str | None:
        return "/usr/bin/pbcopy" if name == "pbcopy" else None

    def run(argv: list[str], data: bytes) -> bool:
        calls.append((argv, data))
        return True

    result = copy_text(
        "find . -name '*.pdf'",
        system="Darwin",
        env={},
        which=which,
        run=run,
    )
    assert result.method == "pbcopy"
    assert calls == [(["pbcopy"], b"find . -name '*.pdf'")]


def test_missing_tools_fall_back_to_osc52_without_running_anything():
    def which(name: str) -> str | None:
        return None

    def run(argv: list[str], data: bytes) -> bool:
        raise AssertionError(f"should not run {argv}")

    result = copy_text("ls", system="Linux", env={}, which=which, run=run)
    assert result.method == "osc52"
    assert result.osc52 is not None
    assert "bH" in result.osc52 or result.osc52.startswith("\033]52;c;")


def test_linux_wayland_prefers_wl_copy_and_skips_a_failing_tool():
    calls: list[str] = []

    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in {"wl-copy", "xclip"} else None

    def run(argv: list[str], data: bytes) -> bool:
        calls.append(argv[0])
        return argv[0] == "xclip"

    result = copy_text(
        "pwd",
        system="Linux",
        env={"WAYLAND_DISPLAY": "wayland-0"},
        which=which,
        run=run,
    )
    assert calls == ["wl-copy", "xclip"]
    assert result.method == "xclip"
    assert result.osc52 is None


def test_display_without_wayland_tries_xclip_before_wl_copy():
    order = [name for name, _argv in candidate_argv("Linux", {"DISPLAY": ":0"})]
    assert order.index("xclip") < order.index("wl-copy")


def test_wsl_tries_clip_exe_first():
    order = [name for name, _argv in candidate_argv("Linux", {"WSL_DISTRO_NAME": "Ubuntu"})]
    assert order[0] == "clip.exe"
    proc_order = [
        name
        for name, _argv in candidate_argv(
            "Linux", {}, proc_version="Linux version 5.15.0-microsoft-standard"
        )
    ]
    assert proc_order[0] == "clip.exe"
