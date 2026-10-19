"""Command-line entry point.

The generated command is printed and, unless ``--no-clipboard`` is set, copied.
No code path in this module executes that command.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from bashagent.cache import CallIdentity, DiskCache
from bashagent.clipboard import ClipboardResult, copy_text
from bashagent.config import Settings, load_dotenv, load_settings
from bashagent.platform import resolve_platform
from bashagent.prompt import PROMPT_VERSION, build_prompts
from bashagent.providers import (
    CompletionRequest,
    MissingAPIKeyError,
    ProviderError,
    RawResponse,
    get_provider,
)
from bashagent.render import render_human, render_json
from bashagent.risk import apply_risk_net
from bashagent.schema import SUGGESTION_JSON_SCHEMA, SchemaError, parse_suggestion

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help=(
        "Translate a plain-language request into one bash command, "
        "an explanation, and a risk label. The command is never executed."
    ),
)


def main() -> None:
    load_dotenv()
    app()


@app.command()
def translate(
    description: Annotated[
        str,
        typer.Argument(help="What you want the command to do, in plain language."),
    ],
    model: Annotated[str | None, typer.Option("--model", help="Model id.")] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="fake (default) or openai."),
    ] = None,
    no_clipboard: Annotated[
        bool,
        typer.Option("--no-clipboard", help="Print the command and do not copy it."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the suggestion as JSON."),
    ] = False,
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="auto, bsd, or gnu."),
    ] = None,
    explain_level: Annotated[
        str | None,
        typer.Option("--explain-level", help="kort or lång."),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Ignore the response cache for this call."),
    ] = False,
) -> None:
    """Print a command, an explanation, and a risk label."""
    try:
        settings = load_settings(
            provider=provider,
            model=model,
            platform=platform,
            explain_level=explain_level,
            no_clipboard=no_clipboard,
            json_output=json_output,
            no_cache=no_cache,
        )
    except ValueError as exc:
        _error(str(exc))
        raise typer.Exit(code=1) from exc
    code = run(description, settings)
    raise typer.Exit(code=code)


def run(description: str, settings: Settings, *, home: Path | None = None) -> int:
    """Run one translation. The returned command is printed, never executed."""
    stdout = Console(soft_wrap=True, highlight=False)
    stderr = Console(stderr=True, soft_wrap=True, highlight=False)
    try:
        resolved = resolve_platform(settings.platform)
    except ValueError as exc:
        _error(str(exc), console=stderr)
        return 1
    system_prompt, user_prompt = build_prompts(
        description,
        platform=resolved,
        explain_level=settings.explain_level,
    )
    identity = CallIdentity(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_version=PROMPT_VERSION,
        model_id=settings.model,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        platform_mode=settings.platform,
        json_schema=SUGGESTION_JSON_SCHEMA,
        provider=settings.provider,
    )
    cache = DiskCache(settings.cache_dir)
    response: RawResponse | None = None
    if not settings.no_cache:
        response = cache.get(identity)
    if response is None:
        try:
            provider = get_provider(settings.provider, model=settings.model)
            response = provider.complete(
                CompletionRequest(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=settings.model,
                    temperature=settings.temperature,
                    max_output_tokens=settings.max_output_tokens,
                    json_schema=SUGGESTION_JSON_SCHEMA,
                )
            )
        except MissingAPIKeyError as exc:
            _error(str(exc), console=stderr)
            return 1
        except ProviderError as exc:
            _error(str(exc), console=stderr)
            return 1
        if not settings.no_cache:
            cache.put(identity, response)
    try:
        suggestion = parse_suggestion(response.text)
    except SchemaError as exc:
        _error(str(exc), console=stderr)
        return 2
    suggestion = apply_risk_net(suggestion, home=home)
    clipboard: ClipboardResult | None = None
    if not settings.no_clipboard:
        clipboard = _copy(suggestion.command)
        if clipboard.osc52 and not settings.json_output:
            sys.stdout.write(clipboard.osc52)
    if settings.json_output:
        render_json(suggestion)
        if clipboard is not None:
            stderr.print(f"[dim]{clipboard.detail}[/dim]")
    else:
        render_human(
            suggestion,
            resolved_platform=resolved,
            clipboard=clipboard,
            console=stdout,
        )
    return 0


def _copy(command: str) -> ClipboardResult:
    proc_version = ""
    proc_path = Path("/proc/version")
    if proc_path.is_file():
        proc_version = proc_path.read_text(encoding="utf-8", errors="replace")
    return copy_text(
        command,
        system=platform.system(),
        env=os.environ,
        which=shutil.which,
        run=_run_clipboard,
        proc_version=proc_version,
    )


def _run_clipboard(argv: list[str], data: bytes) -> bool:
    """Run a clipboard program. ``argv`` is a fixed tool, ``data`` is the command text."""
    try:
        completed = subprocess.run(argv, input=data, capture_output=True, check=False)
    except OSError:
        return False
    return completed.returncode == 0


def _error(message: str, *, console: Console | None = None) -> None:
    (console or Console(stderr=True)).print(message, style="red")
