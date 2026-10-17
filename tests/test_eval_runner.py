from eval.runner import main, run_eval


def test_fake_provider_matches_the_example_tasks(tmp_path):
    code = run_eval(provider_name="fake", platform_mode="gnu", cache_dir=tmp_path / "gnu")
    assert code == 0
    code_bsd = run_eval(provider_name="fake", platform_mode="bsd", cache_dir=tmp_path / "bsd")
    assert code_bsd == 0


def test_runner_refuses_a_live_provider():
    assert main(["--provider", "openai"]) == 1


def test_product_and_eval_do_not_shell_out():
    from pathlib import Path

    roots = [Path("bashagent"), Path("eval")]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "shell=True" not in text
            assert "os.system" not in text
