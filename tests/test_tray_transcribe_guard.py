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


def _record_labels(monkeypatch):
    from PyQt6.QtWidgets import QProgressDialog
    labels = []
    original = QProgressDialog.setLabelText

    def record(self, text):
        labels.append(text)
        original(self, text)

    monkeypatch.setattr(QProgressDialog, "setLabelText", record)
    return labels


def test_transcription_names_loading_reading_and_audio_progress(tray, monkeypatch, qapp, tmp_path):
    import time
    from types import SimpleNamespace

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QFileDialog

    from kira.ui.tray_win import LOADING, READING

    audio = tmp_path / "vortrag.mp3"
    audio.write_bytes(b"")
    infos = []
    monkeypatch.setattr("kira.ui._dialog_style.light_information", lambda *a, **k: infos.append(a[2]))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(audio), "")))
    labels = _record_labels(monkeypatch)

    def transcribe_file(path, on_progress=None, cancelled=None):
        on_progress(0.0, 0.0)
        time.sleep(0.05)
        on_progress(0.0, 3480.0)
        time.sleep(0.25)
        on_progress(750.0, 3480.0)
        time.sleep(0.05)
        return SimpleNamespace(text="Hallo", language="de")

    tray._show_transcribe_file_dialog(SimpleNamespace(model_loaded=False, transcribe_file=transcribe_file))
    deadline = time.monotonic() + 5
    while not infos and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    head = "Transkribiere vortrag.mp3\n"
    assert infos and infos[0].startswith("Fertig.")
    assert f"{head}{LOADING}" in labels
    assert f"{head}{READING}" in labels
    assert f"{head}0:00 von 58:00 · 0 % · startet …" in labels
    assert f"{head}12:30 von 58:00 · 21 % · startet …" in labels


def test_cancel_stops_a_running_transcription(tray, monkeypatch, qapp, tmp_path):
    import time
    from types import SimpleNamespace

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QFileDialog

    from kira.progress import Cancelled

    audio = tmp_path / "lang.wav"
    audio.write_bytes(b"")
    shown = []
    monkeypatch.setattr("kira.ui._dialog_style.light_information", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr("kira.ui._dialog_style.light_critical", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(audio), "")))
    stopped = []

    def transcribe_file(path, on_progress=None, cancelled=None):
        for second in range(500):
            if cancelled():
                stopped.append(second)
                raise Cancelled(path)
            on_progress(float(second), 500.0)
            time.sleep(0.01)
        return SimpleNamespace(text="zu lang", language="de")

    tray._show_transcribe_file_dialog(SimpleNamespace(model_loaded=True, transcribe_file=transcribe_file))
    progress = tray._transcribe_progress
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    progress.canceled.emit()
    deadline = time.monotonic() + 5
    while tray._transcribe_thread is not None and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert stopped and stopped[0] < 400
    assert tray._transcribe_thread is None
    assert shown == []
    assert not (tmp_path / "lang.txt").exists()


def test_cancel_after_the_last_chunk_writes_no_file(tray, monkeypatch, qapp, tmp_path):
    import threading
    import time
    from types import SimpleNamespace

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QFileDialog

    audio = tmp_path / "kurz.wav"
    audio.write_bytes(b"")
    shown = []
    monkeypatch.setattr("kira.ui._dialog_style.light_information", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr("kira.ui._dialog_style.light_critical", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(audio), "")))
    last_chunk = threading.Event()
    seen_cancel = threading.Event()

    def transcribe_file(path, on_progress=None, cancelled=None):
        last_chunk.set()
        deadline = time.monotonic() + 5
        while not cancelled() and time.monotonic() < deadline:
            time.sleep(0.01)
        seen_cancel.set()
        return SimpleNamespace(text="Hallo Welt", language="de")

    tray._show_transcribe_file_dialog(SimpleNamespace(model_loaded=True, transcribe_file=transcribe_file))
    assert last_chunk.wait(5)
    tray._transcribe_progress.canceled.emit()
    deadline = time.monotonic() + 5
    while tray._transcribe_thread is not None and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert seen_cancel.is_set()
    assert tray._transcribe_thread is None
    assert not (tmp_path / "kurz.txt").exists()
    assert shown == []


def test_a_transcript_written_despite_a_late_cancel_is_reported(tray, monkeypatch, qapp, tmp_path):
    import time
    from types import SimpleNamespace

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QFileDialog

    import kira.ui.tray_win as tray_win

    audio = tmp_path / "spaet.wav"
    audio.write_bytes(b"")
    shown = []
    monkeypatch.setattr("kira.ui._dialog_style.light_information", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr("kira.ui._dialog_style.light_critical", lambda *a, **k: shown.append(a[2]))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(audio), "")))
    real_path = tray_win.free_transcript_path

    def path_while_cancelled(src):
        tray._transcribe_progress.canceled.emit()
        return real_path(src)

    monkeypatch.setattr(tray_win, "free_transcript_path", path_while_cancelled)
    transcriber = SimpleNamespace(
        model_loaded=True,
        transcribe_file=lambda path, on_progress=None, cancelled=None: SimpleNamespace(text="Hallo", language="de"),
    )

    tray._show_transcribe_file_dialog(transcriber)
    deadline = time.monotonic() + 5
    while tray._transcribe_thread is not None and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert (tmp_path / "spaet.txt").read_text(encoding="utf-8") == "Hallo"
    assert len(shown) == 1 and shown[0].startswith("Fertig.")
    assert str(tmp_path / "spaet.txt") in shown[0]
