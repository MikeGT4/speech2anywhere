from __future__ import annotations
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)


def test_is_first_run_returns_true_when_marker_missing(tmp_path, monkeypatch):
    from kira.ui import welcome_dialog
    fake_marker = tmp_path / "Kira" / ".welcomed"
    monkeypatch.setattr(welcome_dialog, "_WELCOME_MARKER", fake_marker)
    assert welcome_dialog.is_first_run() is True


def test_mark_welcomed_creates_marker_with_current_version(tmp_path, monkeypatch):
    from kira import __version__
    from kira.ui import welcome_dialog
    fake_marker = tmp_path / "Kira" / ".welcomed"
    monkeypatch.setattr(welcome_dialog, "_WELCOME_MARKER", fake_marker)
    welcome_dialog.mark_welcomed()
    assert fake_marker.exists()
    assert fake_marker.read_text(encoding="utf-8") == __version__


def test_is_first_run_returns_false_after_mark(tmp_path, monkeypatch):
    from kira.ui import welcome_dialog
    fake_marker = tmp_path / "Kira" / ".welcomed"
    monkeypatch.setattr(welcome_dialog, "_WELCOME_MARKER", fake_marker)
    assert welcome_dialog.is_first_run() is True
    welcome_dialog.mark_welcomed()
    assert welcome_dialog.is_first_run() is False


def test_is_first_run_returns_true_for_old_style_marker(tmp_path, monkeypatch):
    from kira.ui import welcome_dialog
    fake_marker = tmp_path / "Kira" / ".welcomed"
    fake_marker.parent.mkdir(parents=True)
    fake_marker.write_text("welcomed", encoding="utf-8")
    monkeypatch.setattr(welcome_dialog, "_WELCOME_MARKER", fake_marker)
    assert welcome_dialog.is_first_run() is True


def test_is_first_run_returns_true_when_marker_version_older(tmp_path, monkeypatch):
    from kira.ui import welcome_dialog
    fake_marker = tmp_path / "Kira" / ".welcomed"
    fake_marker.parent.mkdir(parents=True)
    fake_marker.write_text("0.0.1", encoding="utf-8")
    monkeypatch.setattr(welcome_dialog, "_WELCOME_MARKER", fake_marker)
    assert welcome_dialog.is_first_run() is True


def test_is_first_run_returns_false_when_marker_version_equal(tmp_path, monkeypatch):
    from kira import __version__
    from kira.ui import welcome_dialog
    fake_marker = tmp_path / "Kira" / ".welcomed"
    fake_marker.parent.mkdir(parents=True)
    fake_marker.write_text(__version__, encoding="utf-8")
    monkeypatch.setattr(welcome_dialog, "_WELCOME_MARKER", fake_marker)
    assert welcome_dialog.is_first_run() is False


def test_is_first_run_returns_false_when_marker_version_newer(tmp_path, monkeypatch):
    from kira.ui import welcome_dialog
    fake_marker = tmp_path / "Kira" / ".welcomed"
    fake_marker.parent.mkdir(parents=True)
    fake_marker.write_text("99.0.0", encoding="utf-8")
    monkeypatch.setattr(welcome_dialog, "_WELCOME_MARKER", fake_marker)
    assert welcome_dialog.is_first_run() is False
