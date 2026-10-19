"""Held-out destructive commands. A miss here must not fail the suite."""

from eval.held_out import HELD_OUT, held_out_labels, held_out_recall

_LEVELS = {"safe", "caution", "destructive"}


def test_held_out_commands_are_classified_without_requiring_a_hit():
    labels = held_out_labels()
    assert [command for command, _level in labels] == list(HELD_OUT)
    assert len(labels) == 9
    assert all(level in _LEVELS for _command, level in labels)
    marked = sum(level == "destructive" for _command, level in labels)
    assert held_out_recall() == marked / len(labels)
