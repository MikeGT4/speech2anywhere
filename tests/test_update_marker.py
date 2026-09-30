from __future__ import annotations

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("update-marker module is Windows-only", allow_module_level=True)

from kira._update_marker import (
    UPDATE_DECLINED_MARKER_NAME,
    _kira_appdata_dir,
    is_update_declined,
    mark_update_declined,
)


def _pin_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    kira_dir = tmp_path / "Kira"
    kira_dir.mkdir(exist_ok=True)
    return kira_dir


def test_not_declined_when_marker_absent(tmp_path, monkeypatch):
    _pin_appdata(tmp_path, monkeypatch)
    assert is_update_declined("0.3.0") is False


def test_declined_true_for_exact_version(tmp_path, monkeypatch):
    kira_dir = _pin_appdata(tmp_path, monkeypatch)
    (kira_dir / UPDATE_DECLINED_MARKER_NAME).write_text("0.3.0\n", encoding="utf-8")
    assert is_update_declined("0.3.0") is True


def test_declined_false_for_different_version(tmp_path, monkeypatch):
    kira_dir = _pin_appdata(tmp_path, monkeypatch)
    (kira_dir / UPDATE_DECLINED_MARKER_NAME).write_text("0.3.0\n", encoding="utf-8")
    assert is_update_declined("0.4.0") is False


def test_declined_ignores_surrounding_whitespace(tmp_path, monkeypatch):
    kira_dir = _pin_appdata(tmp_path, monkeypatch)
    (kira_dir / UPDATE_DECLINED_MARKER_NAME).write_text(
        "  0.3.0  \n", encoding="utf-8",
    )
    assert is_update_declined(" 0.3.0 ") is True


def test_mark_creates_marker_with_version(tmp_path, monkeypatch):
    kira_dir = _pin_appdata(tmp_path, monkeypatch)
    mark_update_declined("0.3.0")
    marker = kira_dir / UPDATE_DECLINED_MARKER_NAME
    assert marker.exists()
    assert marker.read_text(encoding="utf-8").strip() == "0.3.0"


def test_mark_creates_kira_dir_if_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    mark_update_declined("0.3.0")
    assert (tmp_path / "Kira" / UPDATE_DECLINED_MARKER_NAME).exists()


def test_mark_overwrites_previous_version(tmp_path, monkeypatch):
    kira_dir = _pin_appdata(tmp_path, monkeypatch)
    mark_update_declined("0.3.0")
    mark_update_declined("0.4.0")
    marker = kira_dir / UPDATE_DECLINED_MARKER_NAME
    assert marker.read_text(encoding="utf-8").strip() == "0.4.0"
    assert is_update_declined("0.3.0") is False
    assert is_update_declined("0.4.0") is True


def test_mark_then_is_declined_roundtrip(tmp_path, monkeypatch):
    _pin_appdata(tmp_path, monkeypatch)
    assert is_update_declined("0.3.0") is False
    mark_update_declined("0.3.0")
    assert is_update_declined("0.3.0") is True


def test_is_declined_returns_false_on_env_error(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    assert is_update_declined("0.3.0") is False


def test_mark_swallows_env_error(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    mark_update_declined("0.3.0")


def test_kira_appdata_dir_rejects_appdata_outside_userprofile(tmp_path, monkeypatch):
    user_profile = tmp_path / "UserHome"
    user_profile.mkdir()
    fake_appdata = tmp_path / "OutsideHome" / "Roaming"
    fake_appdata.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(user_profile))
    monkeypatch.setenv("APPDATA", str(fake_appdata))
    with pytest.raises(EnvironmentError):
        _kira_appdata_dir()


def test_environment_error_is_oserror_subclass():
    assert issubclass(EnvironmentError, OSError)
