# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys
from datetime import datetime, timedelta, timezone
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)

from PyQt6.QtCore import Qt
from kira.lexicon import STATUS_REJECTED, Lexicon

T0 = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


class FakeService:
    def __init__(self, lexicon):
        self.lexicon = lexicon

    def metrics(self):
        return {"this_week": (3, 176), "last_week": None, "baseline": (17, 976),
                "coverage": (176, 214)}


def _lexicon(tmp_path):
    lex = Lexicon(tmp_path / "learned.json")
    lex.observe("kuh bernetes", "Kubernetes", kind="replacement", vocab=True,
                example="auf kuh bernetes", when=T0)
    for day in (1, 2):
        lex.observe("doku", "Docker", kind="replacement", vocab=True,
                    example="mit doku", when=T0 + timedelta(days=day))
    return lex


def test_format_rate():
    from kira.ui.learned_words_dialog import format_rate
    assert format_rate((3, 176)) == "1,7 % (3 von 176)"
    assert format_rate(None) == "noch keine Daten"


def test_tables_show_pending_and_active(qtbot, tmp_path):
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    dlg = LearnedWordsDialog(FakeService(_lexicon(tmp_path)))
    qtbot.addWidget(dlg)
    assert dlg.pending_table.rowCount() == 1
    assert dlg.active_table.rowCount() == 1
    assert dlg.pending_table.item(0, 1).text() == "Kubernetes"
    assert "1,7 %" in dlg.metrics_label.text()
    assert "Zuordnung diese Woche: 82,2 % (176 von 214)" in dlg.metrics_label.text()


def test_accept_moves_entry_to_active_and_saves(qtbot, tmp_path):
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    dlg = LearnedWordsDialog(FakeService(_lexicon(tmp_path)))
    qtbot.addWidget(dlg)
    dlg.pending_table.selectRow(0)
    dlg.accept_button.click()
    assert dlg.pending_table.rowCount() == 0
    assert dlg.active_table.rowCount() == 2
    assert (tmp_path / "learned.json").exists()


def test_delete_rejects_active_entry(qtbot, tmp_path):
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    lex = _lexicon(tmp_path)
    dlg = LearnedWordsDialog(FakeService(lex))
    qtbot.addWidget(dlg)
    dlg.active_table.selectRow(0)
    dlg.delete_button.click()
    assert dlg.active_table.rowCount() == 0
    assert [e.status for e in lex.entries() if e.right == "Docker"] == [STATUS_REJECTED]


def test_hint_without_learning_sources(qtbot, tmp_path):
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    service = FakeService(_lexicon(tmp_path))
    service.has_sources = False
    dlg = LearnedWordsDialog(service)
    qtbot.addWidget(dlg)
    lines = dlg.metrics_label.text().split("\n")
    assert lines[-1] == ("Keine Lernquellen eingetragen (learning.sources in der Rohconfig). "
                         "Speech2Anywhere schreibt nur den Verlauf.")


@pytest.mark.parametrize("has_sources", [True, None])
def test_no_hint_with_sources_or_without_the_attribute(qtbot, tmp_path, has_sources):
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    service = FakeService(_lexicon(tmp_path))
    if has_sources is not None:
        service.has_sources = has_sources
    dlg = LearnedWordsDialog(service)
    qtbot.addWidget(dlg)
    assert "Lernquellen" not in dlg.metrics_label.text()


def test_footer_sounds_friendly(qtbot, tmp_path):
    from PyQt6.QtWidgets import QLabel
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    dlg = LearnedWordsDialog(FakeService(_lexicon(tmp_path)))
    qtbot.addWidget(dlg)
    texte = [label.text() for label in dlg.findChildren(QLabel)]
    assert "Jede Entscheidung gilt sofort." not in texte
    assert "Ein Klick, und es wirkt sofort." in texte


def test_fits_1080p_at_125_percent(qtbot, tmp_path):
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    dlg = LearnedWordsDialog(FakeService(_lexicon(tmp_path)))
    qtbot.addWidget(dlg)
    assert dlg.minimumSizeHint().height() <= 780


def _many(tmp_path, pending=3):
    lex = Lexicon(tmp_path / "learned.json")
    for i in range(pending):
        lex.observe(f"wort{i}", f"Wort{i}", kind="glossary", vocab=True,
                    example=f"mit wort{i}", when=T0 + timedelta(minutes=i))
    return lex


@pytest.fixture
def shown(qtbot):
    from kira.ui.learned_words_dialog import LearnedWordsDialog
    dialogs = []

    def make(lexicon):
        dlg = LearnedWordsDialog(FakeService(lexicon))
        qtbot.addWidget(dlg)
        dialogs.append(dlg)
        dlg.show()
        qtbot.waitExposed(dlg)
        dlg.resize(dlg.width(), dlg.sizeHint().height())
        return dlg

    yield make
    for dlg in dialogs:
        dlg.close()


def _click_row(qtbot, table, row):
    rect = table.visualItemRect(table.item(row, 0))
    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def _selected(table):
    return [index.row() for index in table.selectionModel().selectedRows()]


def test_accept_click_works_without_picking_a_row_first(qtbot, tmp_path, shown):
    dlg = shown(_many(tmp_path))
    assert _selected(dlg.pending_table) == [0]
    qtbot.mouseClick(dlg.accept_button, Qt.MouseButton.LeftButton)
    assert dlg.pending_table.rowCount() == 2
    assert [dlg.active_table.item(row, 1).text() for row in range(dlg.active_table.rowCount())] == ["Wort0"]


def test_next_entry_is_selected_after_a_decision(qtbot, tmp_path, shown):
    dlg = shown(_many(tmp_path))
    _click_row(qtbot, dlg.pending_table, 1)
    qtbot.mouseClick(dlg.reject_button, Qt.MouseButton.LeftButton)
    assert _selected(dlg.pending_table) == [1]
    assert dlg.pending_table.item(1, 1).text() == "Wort2"
    qtbot.mouseClick(dlg.accept_button, Qt.MouseButton.LeftButton)
    assert _selected(dlg.pending_table) == [0]
    assert dlg.pending_table.item(0, 1).text() == "Wort0"


def test_accepting_the_last_entry_disables_the_buttons(qtbot, tmp_path, shown):
    dlg = shown(_many(tmp_path, pending=1))
    qtbot.mouseClick(dlg.accept_button, Qt.MouseButton.LeftButton)
    assert dlg.pending_table.rowCount() == 0
    assert not dlg.accept_button.isEnabled()
    assert not dlg.reject_button.isEnabled()


def test_buttons_are_disabled_when_nothing_can_be_decided(qtbot, tmp_path, shown):
    dlg = shown(Lexicon(tmp_path / "learned.json"))
    assert not dlg.accept_button.isEnabled()
    assert not dlg.reject_button.isEnabled()
    assert not dlg.delete_button.isEnabled()


def test_delete_needs_a_chosen_active_row(qtbot, tmp_path, shown):
    dlg = shown(_lexicon(tmp_path))
    assert not dlg.delete_button.isEnabled()
    _click_row(qtbot, dlg.active_table, 0)
    assert dlg.delete_button.isEnabled()
    qtbot.mouseClick(dlg.delete_button, Qt.MouseButton.LeftButton)
    assert dlg.active_table.rowCount() == 0
    assert not dlg.delete_button.isEnabled()
