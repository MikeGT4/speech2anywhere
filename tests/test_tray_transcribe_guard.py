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


def test_finished_transcription_reports_the_file(tray, monkeypatch, qapp, tmp_path):
    import time
    from types import SimpleNamespace

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QFileDialog

    audio = tmp_path / "aufnahme.wav"
    audio.write_bytes(b"")
    infos = []
    monkeypatch.setattr("kira.ui._dialog_style.light_information", lambda *a, **k: infos.append(a[2]))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(audio), "")))
    transcriber = MagicMock()
    transcriber.transcribe_file.return_value = SimpleNamespace(text="Hallo Welt", language="de")

    tray._show_transcribe_file_dialog(transcriber=transcriber)
    deadline = time.monotonic() + 5
    while not infos and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert infos and infos[0].startswith("Fertig.")
    assert (tmp_path / "aufnahme.txt").read_text(encoding="utf-8") == "Hallo Welt"


def test_transcript_never_overwrites_an_existing_text_file(tmp_path):
    from pathlib import Path as _Path
    from kira.ui.tray_win import free_transcript_path
    src = tmp_path / "Vortrag.mp4"
    assert free_transcript_path(src) == tmp_path / "Vortrag.txt"
    (tmp_path / "Vortrag.txt").write_text("Notizen", encoding="utf-8")
    assert free_transcript_path(src) == tmp_path / "Vortrag (2).txt"
    (tmp_path / "Vortrag (2).txt").write_text("x", encoding="utf-8")
    assert free_transcript_path(_Path(src)) == tmp_path / "Vortrag (3).txt"
