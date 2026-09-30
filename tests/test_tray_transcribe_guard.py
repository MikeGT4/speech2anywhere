from __future__ import annotations
import sys
from unittest.mock import MagicMock

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)


@pytest.fixture
def tray():
    from kira.ui.tray_win import KiraTray
    return KiraTray(on_quit=lambda: None)


def test_transcribe_anchors_start_none(tray):
    assert tray._transcribe_thread is None
    assert tray._transcribe_worker is None
    assert tray._transcribe_progress is None


def test_second_transcription_while_running_shows_hint(tray, monkeypatch):
    running = MagicMock()
    running.isRunning.return_value = True
    tray._transcribe_thread = running

    infos = []
    monkeypatch.setattr(
        "kira.ui._dialog_style.light_information",
        lambda *a, **k: infos.append(a),
    )
    from PyQt6.QtWidgets import QFileDialog
    opened = []
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (opened.append(1), ("", ""))[1]),
    )

    tray._show_transcribe_file_dialog(transcriber=MagicMock())

    assert infos, "Hinweis-Dialog muss erscheinen"
    assert not opened, "kein File-Dialog waehrend laufendem Job"
    assert tray._transcribe_thread is running


def test_finished_thread_does_not_block_new_transcription(tray, monkeypatch):
    finished = MagicMock()
    finished.isRunning.return_value = False
    tray._transcribe_thread = finished

    infos = []
    monkeypatch.setattr(
        "kira.ui._dialog_style.light_information",
        lambda *a, **k: infos.append(a),
    )
    from PyQt6.QtWidgets import QFileDialog
    opened = []
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (opened.append(1), ("", ""))[1]),
    )

    tray._show_transcribe_file_dialog(transcriber=MagicMock())

    assert opened, "File-Dialog muss aufgehen"
    assert not infos, "kein Blockier-Hinweis"
