# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)


def _tray(marshalled):
    from kira.ui.tray_win import KiraTray
    tray = KiraTray(on_quit=lambda: None)
    tray._marshal_to_qt = lambda func, label: marshalled.append(func)
    return tray


def test_open_log_opens_speech2anywhere_log(tmp_path, monkeypatch):
    import kira.ui.tray_win as tray_win
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    opened = []
    monkeypatch.setattr(tray_win.subprocess, "Popen", lambda args: opened.append(args))
    _tray([])._open_log(None, None)
    assert opened == [["notepad.exe", str(tmp_path / "Kira" / "speech2anywhere.log")]]


def test_open_log_fallback_shows_the_error_later(tmp_path, monkeypatch):
    import kira.ui.tray_win as tray_win
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def fail(args):
        raise OSError("kein notepad")

    monkeypatch.setattr(tray_win.subprocess, "Popen", fail)
    shown = []
    monkeypatch.setattr(tray_win.KiraTray, "_show_notepad_fallback",
                        staticmethod(lambda path, msg: shown.append((path, msg))))
    marshalled = []
    _tray(marshalled)._open_log(None, None)
    marshalled[0]()
    assert shown == [(str(tmp_path / "Kira" / "speech2anywhere.log"), "kein notepad")]
