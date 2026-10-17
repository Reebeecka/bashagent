from bashagent.prompt import build_prompts


def test_explain_level_and_platform_are_in_the_system_prompt():
    gnu_short, user = build_prompts("lista filer", platform="gnu", explain_level="kort")
    bsd_long, _user = build_prompts("lista filer", platform="bsd", explain_level="lång")
    assert user == "lista filer"
    assert "GNU" in gnu_short
    assert "en eller två meningar" in gnu_short
    assert "BSD" in bsd_long.split("Målplattform:", 1)[1].splitlines()[0]
    assert "varje flagga" in bsd_long
