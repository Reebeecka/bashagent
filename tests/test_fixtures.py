import pytest
from eval.fixtures import EXPECTED_404_COUNT, LARGE_PDF_BYTES, count_404_lines, generate, manifest


def test_two_generations_match(tmp_path):
    first = generate(tmp_path / "a")
    second = generate(tmp_path / "b")
    assert manifest(first) == manifest(second)
    assert (first / "big" / "large.pdf").stat().st_size == LARGE_PDF_BYTES
    assert count_404_lines(first) == EXPECTED_404_COUNT
    assert (first / "docs" / "rapport åäö.txt").is_file()
    assert (first / "docs" / "mina anteckningar.txt").is_file()
    assert (first / "empty").is_dir()
    assert (first / "docs" / "readme-link.txt").is_symlink()
    assert (first / "src" / "app.sh").stat().st_mode & 0o111 == 0
    assert (first / "data" / "empty.dat").stat().st_size == 0
    assert (first / "data" / "words.txt").read_text(encoding="utf-8").splitlines() == [
        "beta",
        "alpha",
        "beta",
        "alpha",
        "gamma",
    ]


def test_refuses_a_non_empty_directory(tmp_path):
    root = tmp_path / "filled"
    root.mkdir()
    (root / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generate(root)
    assert (root / "keep.txt").read_text(encoding="utf-8") == "keep"
