from eval.compare import normalize
from eval.docker_run import pack_tree, unpack_tree
from eval.fixtures import LARGE_PDF_BYTES, MTIME_NEW, generate
from eval.validate import Executed, judge


def test_normalize_sorts_and_strips_dot_slash():
    assert normalize("./b\n./a\n") == "a\nb"
    assert normalize("     13 200\n   7 404\n") == "13 200\n7 404"
    assert normalize("./docs/readme.txt\n", order="exact") == "docs/readme.txt"


def test_normalize_keeps_head_order():
    text = "second\nfirst\n"
    assert normalize(text, order="exact") == "second\nfirst"
    assert normalize(text, order="sorted") == "first\nsecond"


def test_judge_accepts_sorted_stdout_and_text(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_text("y", encoding="utf-8")
    task = {
        "expect": {
            "exit": 0,
            "stdout": "sorted",
            "lines": ["./docs/b.txt", "docs/a.txt"],
            "paths": {"docs/a.txt": {"text": "y"}},
        }
    }
    errors = judge(task, Executed(0, "./docs/b.txt\n./docs/a.txt\n", "", tmp_path))
    assert errors == []


def test_judge_reports_a_stdout_mismatch(tmp_path):
    task = {"expect": {"exit": 0, "stdout": "exact", "lines": ["7"]}}
    errors = judge(task, Executed(0, "8\n", "", tmp_path))
    assert errors
    assert "stdout mismatch" in errors[0]


def test_pack_roundtrip_keeps_symlink_size_and_mtime(tmp_path):
    source = generate(tmp_path / "src")
    destination = tmp_path / "dest"
    unpack_tree(pack_tree(source), destination)
    assert (destination / "docs" / "readme-link.txt").is_symlink()
    assert (destination / "big" / "large.pdf").stat().st_size == LARGE_PDF_BYTES
    assert (destination / "empty").is_dir()
    assert (destination / "data" / "empty.dat").stat().st_size == 0
    assert int((destination / "notes.txt").stat().st_mtime) == MTIME_NEW
    assert (destination / "docs" / "rapport åäö.txt").is_file()
