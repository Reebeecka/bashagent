import pytest
from bashagent.platform import detect_platform, resolve_platform


def test_darwin_is_bsd_and_linux_is_gnu():
    assert detect_platform(system="Darwin") == "bsd"
    assert detect_platform(system="Linux") == "gnu"
    assert detect_platform(system="linux") == "gnu"


def test_auto_uses_detection_and_flags_force_a_family():
    assert resolve_platform("auto", system="Darwin") == "bsd"
    assert resolve_platform("auto", system="Linux") == "gnu"
    assert resolve_platform("bsd", system="Linux") == "bsd"
    assert resolve_platform("gnu", system="Darwin") == "gnu"


def test_unknown_choice_is_rejected():
    with pytest.raises(ValueError):
        resolve_platform("windows")
