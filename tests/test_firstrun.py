from __future__ import annotations

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("First-run module is Windows-only", allow_module_level=True)

from kira.firstrun import (
    is_first_run,
    mark_first_run_complete,
    FIRST_RUN_MARKER_NAME,
    _kira_appdata_dir,
)


def test_first_run_true_when_marker_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    kira_dir = tmp_path / "Kira"
    kira_dir.mkdir()
    assert is_first_run() is True


def test_first_run_false_when_marker_present(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    kira_dir = tmp_path / "Kira"
    kira_dir.mkdir()
    (kira_dir / FIRST_RUN_MARKER_NAME).write_text("done")
    assert is_first_run() is False


def test_mark_first_run_complete_creates_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    kira_dir = tmp_path / "Kira"
    kira_dir.mkdir()
    mark_first_run_complete()
    assert (kira_dir / FIRST_RUN_MARKER_NAME).exists()


def test_mark_first_run_creates_kira_dir_if_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    mark_first_run_complete()
    assert (tmp_path / "Kira" / FIRST_RUN_MARKER_NAME).exists()


def test_kira_appdata_dir_raises_environment_error_when_appdata_missing(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    with pytest.raises(EnvironmentError):
        _kira_appdata_dir()


def test_environment_error_is_oserror_subclass():
    assert issubclass(EnvironmentError, OSError)


def test_kira_appdata_dir_rejects_appdata_outside_userprofile(tmp_path, monkeypatch):
    user_profile = tmp_path / "UserHome"
    user_profile.mkdir()
    fake_appdata = tmp_path / "OutsideHome" / "Roaming"
    fake_appdata.mkdir(parents=True)

    monkeypatch.setenv("USERPROFILE", str(user_profile))
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    with pytest.raises(EnvironmentError) as exc_info:
        _kira_appdata_dir()

    msg = str(exc_info.value)
    assert "USERPROFILE" in msg or "user scope" in msg


def test_kira_appdata_dir_accepts_appdata_under_userprofile(tmp_path, monkeypatch):
    user_profile = tmp_path / "UserHome"
    user_profile.mkdir()
    appdata = user_profile / "AppData" / "Roaming"
    appdata.mkdir(parents=True)

    monkeypatch.setenv("USERPROFILE", str(user_profile))
    monkeypatch.setenv("APPDATA", str(appdata))

    result = _kira_appdata_dir()
    assert result == appdata / "Kira"


def test_kira_appdata_dir_accepts_when_userprofile_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("USERPROFILE", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    result = _kira_appdata_dir()
    assert result == tmp_path / "Kira"
