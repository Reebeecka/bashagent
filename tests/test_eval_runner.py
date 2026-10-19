from pathlib import Path

from eval.runner import main, run_eval


def test_fake_provider_parses_the_draft_set(tmp_path, capsys):
    assert run_eval(provider_name="fake", platform_mode="gnu", cache_dir=tmp_path / "gnu") == 0
    gnu = capsys.readouterr().out
    assert "Not a measurement" in gnu
    assert "No commands were executed." in gnu
    assert run_eval(provider_name="fake", platform_mode="bsd", cache_dir=tmp_path / "bsd") == 0


def test_unpriced_model_is_refused(capsys):
    code = main(["--provider", "openai", "--model", "not-a-priced-model", "--smoke"])
    assert code == 1
    assert "No price" in capsys.readouterr().out


def test_product_and_eval_do_not_shell_out():
    roots = [Path("bashagent"), Path("eval")]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "shell=True" not in text
            assert "os.system" not in text


def test_string_eval_does_not_call_docker():
    source = Path("eval/runner.py").read_text(encoding="utf-8")
    assert "docker" not in source
