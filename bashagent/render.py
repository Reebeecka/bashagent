"""Terminal rendering. The command is printed and never run."""

from __future__ import annotations

import json
import sys
from typing import TextIO

from rich.console import Console
from rich.panel import Panel

from bashagent.clipboard import ClipboardResult
from bashagent.schema import Suggestion

_RISK_STYLE = {"safe": "green", "caution": "yellow", "destructive": "red"}


def render_human(
    suggestion: Suggestion,
    *,
    resolved_platform: str,
    clipboard: ClipboardResult | None,
    console: Console | None = None,
) -> None:
    out = console or Console(soft_wrap=True, highlight=False)
    style = _RISK_STYLE[suggestion.risk]
    out.print(Panel(suggestion.command, title="Kommando", border_style=style))
    out.print(f"[bold]Förklaring[/bold]\n{suggestion.explanation}")
    out.print(f"[{style}]Risk: {suggestion.risk}[/{style}]")
    out.print(suggestion.risk_reason)
    if suggestion.platform_notes:
        out.print(f"[dim]Plattform ({resolved_platform}): {suggestion.platform_notes}[/dim]")
    out.print(
        "[dim]Kommandot kördes inte. Klistra in det i din egen terminal om du vill köra det.[/dim]"
    )
    if clipboard is None:
        return
    if clipboard.method == "osc52":
        out.print("[dim]Urklipp: ingen lokal urklippsbinär, skickar OSC 52.[/dim]")
    elif clipboard.ok:
        out.print(f"[dim]Kopierat till urklipp ({clipboard.method}). Inget Enter lades till.[/dim]")


def render_json(suggestion: Suggestion, *, stream: TextIO | None = None) -> None:
    target = stream or sys.stdout
    json.dump(suggestion.model_dump(), target, ensure_ascii=False, indent=2)
    target.write("\n")
