import json
import re

from bashagent.cli import app
from bashagent.schema import Suggestion
from typer.testing import CliRunner

runner = CliRunner()
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def test_help_lists_the_platform_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # GitHub Actions forces color, which splits "--" from the option name.
    text = _ANSI.sub("", result.stdout)
    assert "--platform" in text
    assert "--no-clipboard" in text
    assert "--explain-level" in text


def test_happy_path_prints_command_explanation_and_risk():
    result = runner.invoke(
        app,
        [
            "hitta alla pdf:er större än 10 MB",
            "--provider",
            "fake",
            "--no-clipboard",
            "--platform",
            "gnu",
        ],
    )
    assert result.exit_code == 0
    assert "find . -type f -name '*.pdf' -size +10M" in result.stdout
    assert "Risk: safe" in result.stdout
    assert "Kommandot kördes inte" in result.stdout


def test_json_output_and_platform_switch():
    gnu = runner.invoke(
        app,
        [
            "ersätt foo med bar på plats i notes.txt",
            "--provider",
            "fake",
            "--no-clipboard",
            "--json",
            "--platform",
            "gnu",
        ],
    )
    bsd = runner.invoke(
        app,
        [
            "ersätt foo med bar på plats i notes.txt",
            "--provider",
            "fake",
            "--no-clipboard",
            "--json",
            "--platform",
            "bsd",
        ],
    )
    assert gnu.exit_code == 0
    assert bsd.exit_code == 0
    assert json.loads(gnu.stdout)["command"] == "sed -i 's/foo/bar/' notes.txt"
    assert json.loads(bsd.stdout)["command"] == "sed -i '' 's/foo/bar/' notes.txt"


def test_destructive_suggestion_is_printed_and_not_run():
    result = runner.invoke(
        app,
        [
            "ta bort alla .tmp-filer rekursivt",
            "--provider",
            "fake",
            "--no-clipboard",
            "--json",
            "--platform",
            "gnu",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["risk"] == "destructive"
    assert "-delete" in payload["command"]


def test_second_call_reuses_the_cache(tmp_path):
    args = [
        "hitta alla pdf:er större än 10 MB",
        "--provider",
        "fake",
        "--no-clipboard",
        "--json",
        "--platform",
        "gnu",
    ]
    first = runner.invoke(app, args)
    assert first.exit_code == 0
    files = list((tmp_path / "cache").glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    record["response"]["text"] = Suggestion(
        command="echo cached",
        explanation="Svaret kom från cachen.",
        risk="safe",
        risk_reason="Test.",
        platform_notes="",
    ).model_dump_json()
    files[0].write_text(json.dumps(record), encoding="utf-8")
    second = runner.invoke(app, args)
    assert second.exit_code == 0
    assert json.loads(second.stdout)["command"] == "echo cached"


def test_openai_without_a_key_refuses_to_start(monkeypatch):
    def fail_copy(command: str):
        raise AssertionError(command)

    monkeypatch.setattr("bashagent.cli._copy", fail_copy)
    result = runner.invoke(
        app,
        ["lista filer", "--provider", "openai", "--no-clipboard"],
    )
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.stderr


def test_no_clipboard_does_not_call_the_clipboard(monkeypatch):
    def fail_copy(command: str):
        raise AssertionError(command)

    monkeypatch.setattr("bashagent.cli._copy", fail_copy)
    result = runner.invoke(app, ["lista filer", "--provider", "fake", "--no-clipboard"])
    assert result.exit_code == 0
    assert "ls" in result.stdout
