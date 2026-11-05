# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QLabel

from kira.ui import _comic as comic


def _label(card, text: str) -> QLabel:
    return next(label for label in card.findChildren(QLabel) if label.text() == text)


def _card_with_switch(qtbot):
    card = comic.ComicCard("Anzeige")
    switch = comic.ToggleSwitch()
    card.add_row("Wortfetzen", "Fetzen deiner Wörter beim Sprechen.", switch)
    qtbot.addWidget(card)
    card.show()
    return card, switch


def test_click_on_switch_label_toggles_the_switch(qtbot):
    card, switch = _card_with_switch(qtbot)
    qtbot.mouseClick(_label(card, "Wortfetzen"), Qt.MouseButton.LeftButton)
    assert switch.isChecked()
    qtbot.mouseClick(_label(card, "Wortfetzen"), Qt.MouseButton.LeftButton)
    assert not switch.isChecked()


def test_click_on_switch_description_toggles_the_switch(qtbot):
    card, switch = _card_with_switch(qtbot)
    qtbot.mouseClick(_label(card, "Fetzen deiner Wörter beim Sprechen."), Qt.MouseButton.LeftButton)
    assert switch.isChecked()


def test_switch_label_shows_a_pointing_hand(qtbot):
    card, _switch = _card_with_switch(qtbot)
    assert _label(card, "Wortfetzen").cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_disabled_switch_ignores_label_clicks(qtbot):
    card, switch = _card_with_switch(qtbot)
    switch.setEnabled(False)
    qtbot.mouseClick(_label(card, "Wortfetzen"), Qt.MouseButton.LeftButton)
    assert not switch.isChecked()


def test_right_click_on_label_does_not_toggle(qtbot):
    card, switch = _card_with_switch(qtbot)
    qtbot.mouseClick(_label(card, "Wortfetzen"), Qt.MouseButton.RightButton)
    assert not switch.isChecked()


def test_labels_of_other_controls_stay_plain(qtbot):
    card = comic.ComicCard("Anzeige")
    combo = QComboBox()
    combo.addItems(["Comic", "Manga"])
    card.add_row("Stil", "So sieht die Anzeige aus.", combo)
    qtbot.addWidget(card)
    card.show()
    qtbot.mouseClick(_label(card, "Stil"), Qt.MouseButton.LeftButton)
    assert combo.currentIndex() == 0
    assert _label(card, "Stil").cursor().shape() != Qt.CursorShape.PointingHandCursor
