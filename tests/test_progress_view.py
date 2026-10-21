# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from PyQt6.QtWidgets import QLabel, QProgressBar, QProgressDialog

from kira import progress as prog
from kira.ui._progress_view import ProgressView


class Clock:
    def __init__(self) -> None:
        self.now = 500.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def row(qtbot):
    label = QLabel()
    bar = QProgressBar()
    qtbot.addWidget(label)
    qtbot.addWidget(bar)
    clock = Clock()
    view = ProgressView(bar, label.setText, "Whisper: ", clock=clock)
    return view, bar, label, clock


def test_busy_runs_the_bar_without_a_value(row):
    view, bar, label, _ = row
    view.busy("wird installiert …")
    assert (bar.minimum(), bar.maximum()) == (0, 0)
    assert label.text() == "Whisper: wird installiert …"


def test_bytes_show_amount_percent_and_start_text(row):
    view, bar, label, _ = row
    view.amount(1_200_000_000, 3_090_000_000)
    assert bar.maximum() == prog.SCALE
    assert bar.value() == 388
    assert label.text() == "Whisper: 1,2 von 3,1 GB · 38 % · startet …"


def test_rate_and_time_left_appear_after_enough_samples(row):
    view, _, label, clock = row
    done = 0
    for _ in range(10):
        view.amount(done, 3_090_000_000)
        clock.now += 1
        done += 12_000_000
    assert "12,0 MB/s" in label.text()
    assert label.text().endswith("noch etwa 4 Minuten")


def test_never_a_full_bar_while_the_download_finishes(row):
    view, bar, label, _ = row
    view.amount(3_090_000_000, 3_090_000_000)
    assert (bar.minimum(), bar.maximum()) == (0, 0)
    assert label.text() == f"Whisper: {prog.FINISHING}"


def test_finish_fills_and_idle_empties_the_bar(row):
    view, bar, label, _ = row
    view.finish("fertig")
    assert (bar.maximum(), bar.value()) == (1, 1)
    view.idle("abgebrochen")
    assert (bar.maximum(), bar.value()) == (1, 0)
    assert label.text() == "Whisper: abgebrochen"


def test_timer_switches_to_a_running_bar_when_no_bytes_arrive(row, qtbot):
    view, bar, label, clock = row
    view.amount(100_000_000, 3_090_000_000)
    assert view._timer.isActive()
    clock.now += 25
    view._render()
    assert (bar.minimum(), bar.maximum()) == (0, 0)
    assert label.text() == "Whisper: 0,1 von 3,1 GB · 3 % · läuft seit 0:25"
    view.amount(400_000_000, 3_090_000_000)
    assert bar.maximum() == prog.SCALE
    view.busy("Prüfsumme wird geprüft …")
    assert not view._timer.isActive()


def test_dialog_stays_open_at_full_bytes_and_ignores_updates_after_cancel(qtbot):
    dialog = QProgressDialog("Lade x\nstartet …", "Abbrechen", 0, 0)
    qtbot.addWidget(dialog)
    view = ProgressView(dialog, dialog.setLabelText, "Lade x\n")
    dialog.show()
    view.amount(5_000, 10_000)
    view.amount(10_000, 10_000)
    assert dialog.isVisible()
    assert not dialog.autoReset() and not dialog.autoClose()
    dialog.canceled.emit()
    assert dialog.wasCanceled()
    view.amount(6_000, 10_000)
    assert not dialog.isVisible()
    assert not view._timer.isActive()


def test_stop_keeps_a_closed_dialog_closed(qtbot):
    dialog = QProgressDialog("Lade x", "Abbrechen", 0, 0)
    qtbot.addWidget(dialog)
    view = ProgressView(dialog, dialog.setLabelText, "Lade x\n")
    dialog.show()
    view.amount(5_000, 10_000)
    view.stop()
    dialog.close()
    view.amount(7_000, 10_000)
    view._render()
    assert not dialog.isVisible()
    assert not view._timer.isActive()


def test_no_bytes_yet_show_size_and_runtime_with_a_running_bar(row):
    view, bar, label, clock = row
    view.amount(3_550_885, 3_090_835_702)
    assert (bar.minimum(), bar.maximum()) == (0, 0)
    assert label.text() == "Whisper: 3,1 GB · läuft seit 0:00"
    clock.now += 135
    view._render()
    assert label.text() == "Whisper: 3,1 GB · läuft seit 2:15"
    view.amount(256_000_000, 3_090_835_702)
    assert bar.maximum() == prog.SCALE
    assert label.text() == "Whisper: 0,3 von 3,1 GB · 8 % · läuft seit 2:15"


def test_audio_progress_counts_up_from_zero_without_the_size_form(qtbot):
    label = QLabel()
    bar = QProgressBar()
    qtbot.addWidget(label)
    qtbot.addWidget(bar)
    view = ProgressView(bar, label.setText, "", amount=prog.time_text, with_rate=False, total_only=None,
                        stall=None, clock=Clock())
    view.amount(0.0, 3480.0)
    assert label.text() == "0:00 von 58:00 · 0 % · startet …"
    assert bar.maximum() == prog.SCALE


def test_phase_set_while_the_dialog_handles_events_stays(qtbot):
    from PyQt6.QtCore import Qt, QTimer

    dialog = QProgressDialog("Lade x\nstartet …", "Abbrechen", 0, 0)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    qtbot.addWidget(dialog)
    view = ProgressView(dialog, dialog.setLabelText, "Lade x\n")
    dialog.show()
    view.amount(5_000, 10_000)
    QTimer.singleShot(0, lambda: view.busy("Prüfsumme wird geprüft …"))
    view.amount(9_800, 10_000)
    assert dialog.labelText() == "Lade x\nPrüfsumme wird geprüft …"
    assert (dialog.minimum(), dialog.maximum()) == (0, 0)


def test_idle_starts_the_next_measurement_from_zero(row):
    view, bar, label, clock = row
    view.amount(400_000_000, 3_090_835_702)
    clock.now += 100
    view.idle("abgebrochen")
    assert not view._timer.isActive()
    view.busy(prog.STARTING)
    view.amount(3_550_885, 3_090_835_702)
    assert label.text() == "Whisper: 3,1 GB · läuft seit 0:00"


def test_finish_starts_the_next_measurement_from_zero(row):
    view, bar, label, clock = row
    view.amount(400_000_000, 3_090_835_702)
    clock.now += 100
    view.finish("fertig")
    view.amount(3_550_885, 3_090_835_702)
    assert label.text() == "Whisper: 3,1 GB · läuft seit 0:00"
