from eval.compare import normalize_command, variant_match


def test_normalize_collapses_space_quotes_and_short_flags():
    assert normalize_command('ls  -lh   "file"') == normalize_command("ls -hl 'file'")


def test_variant_match_uses_the_platform_reference():
    task = {
        "reference": {
            "default": "sed -i 's/a/b/' file",
            "gnu": "sed -i 's/a/b/' file",
            "bsd": "sed -i '' 's/a/b/' file",
        },
        "accepted_variants": ["sed -i 's/a/b/' file"],
    }
    assert variant_match("sed -i 's/a/b/' file", task, "gnu")
    assert variant_match("sed -i '' 's/a/b/' file", task, "bsd")
    assert not variant_match("rm file", task, "gnu")
