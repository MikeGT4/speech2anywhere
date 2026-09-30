# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from PyQt6.QtCore import Qt

from kira.config import Config


@pytest.fixture
def dialog(qtbot, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "load_config", lambda: Config())
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(
        sd.SettingsDialog, "_query_input_devices",
        lambda self: [(3, "USB Microphone"), (5, "Mikrofon (Realtek Audio)")],
    )
    monkeypatch.setattr(sd, "light_information", lambda *a, **k: None)
    monkeypatch.setattr(sd, "light_warning", lambda *a, **k: None)
    dlg = sd.SettingsDialog()
    qtbot.addWidget(dlg)
    return dlg


def test_tabs_follow_the_six_pages(dialog, qtbot):
    assert [t.text() for t in dialog._tabs] == ["Mikrofon", "Politur", "Tasten", "Anzeige", "Lernen", "Über"]
    assert dialog._pages.count() == 6
    for index, tab in enumerate(dialog._tabs):
        qtbot.mouseClick(tab, Qt.MouseButton.LeftButton)
        assert dialog._pages.currentIndex() == index
        assert tab.isChecked()
        assert sum(t.isChecked() for t in dialog._tabs) == 1


@pytest.mark.parametrize("name", [
    "_gain", "_device", "_language", "_learning_enabled", "_styler_model", "_fast_mode",
    "_styler_timeout", "_hotkey", "_edit_enabled", "_edit_hotkey", "_restore_ms", "_hud_style",
])
def test_every_setting_sits_on_a_page(dialog, name):
    assert dialog._pages.isAncestorOf(getattr(dialog, name))


def test_save_writes_language_code_not_label(dialog, tmp_path):
    dialog._language.setCurrentIndex(dialog._language.findData("de"))
    assert dialog._language.currentText() == "Deutsch"
    dialog._save()
    assert "language: de" in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_gain_slider_and_field_stay_in_sync(dialog):
    dialog._gain.setValue(2.4)
    assert dialog._gain_slider.value() == 24
    dialog._gain_slider.setValue(13)
    assert dialog._gain.value() == pytest.approx(1.3)


def test_gain_above_slider_range_keeps_field_value(dialog):
    dialog._gain.setValue(12.0)
    assert dialog._gain_slider.value() == dialog._gain_slider.maximum()
    assert dialog._gain.value() == pytest.approx(12.0)


def test_edit_toggle_greys_out_command_key(dialog):
    dialog._edit_enabled.setChecked(False)
    assert not dialog._edit_hotkey.isEnabled()
    dialog._edit_enabled.setChecked(True)
    assert dialog._edit_hotkey.isEnabled()


def test_toggle_switch_flips_on_click(qtbot):
    from kira.ui._comic import ToggleSwitch
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    switch.resize(switch.sizeHint())
    with qtbot.waitSignal(switch.toggled, timeout=1000):
        qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)
    assert switch.isChecked()


def test_brand_fonts_register(qtbot):
    from kira.ui._comic import load_fonts
    families = load_fonts()
    assert set(families) == {600, 700, 800}
    assert all("Baloo" in name for name in families.values())


def test_wordmark_svg_loads(qtbot):
    from kira.ui._comic import Wordmark
    mark = Wordmark("dunkel", 54)
    qtbot.addWidget(mark)
    assert mark._renderer.isValid()
    assert mark.height() == 54 and mark.width() > 5 * 54


def test_about_page_shows_the_digitalroots_logo_not_the_word(dialog):
    from PyQt6.QtWidgets import QLabel
    import kira.ui._comic as comic
    bubble = dialog._pages.widget(5).findChild(comic.HintBubble)
    labels = bubble.findChildren(QLabel)
    assert not any("Digitalroots" in label.text() for label in labels)
    assert any(label.pixmap() is not None and not label.pixmap().isNull() for label in labels)


def _message_after_save(dialog, monkeypatch) -> str:
    import kira.ui.settings_dialog as sd
    shown = []
    monkeypatch.setattr(sd, "light_information", lambda parent, title, text: shown.append(text))
    dialog._save()
    return shown[-1]


def test_display_style_alone_needs_no_restart(dialog, monkeypatch):
    _message_after_save(dialog, monkeypatch)
    dialog._hud_style.setCurrentIndex(dialog._hud_style.findData("klartext"))
    text = _message_after_save(dialog, monkeypatch)
    assert "nach dem Neustart" not in text
    assert "ab dem nächsten Diktat" in text


def test_other_settings_still_ask_for_restart_via_beenden(dialog, monkeypatch):
    _message_after_save(dialog, monkeypatch)
    dialog._gain.setValue(2.4)
    text = _message_after_save(dialog, monkeypatch)
    assert "Neustart" in text
    assert "Beenden" in text
    assert "Quit" not in text


def test_hints_sound_friendly(dialog):
    from PyQt6.QtWidgets import QLabel
    texte = " ".join(label.text() for label in dialog.findChildren(QLabel))
    for amtlich in ("Die meisten Änderungen gelten nach dem Neustart", "Neue Tasten gelten nach dem Neustart",
                    "Das Lernen beginnt nach dem Neustart", "Gilt ab dem nächsten Diktat, ohne Neustart",
                    "Satzzeichen, Großschreibung, Füllwörter.", "Danach wird der Rohtext eingefügt."):
        assert amtlich not in texte
    assert "Fast alles wirkt nach einem kurzen Neustart." in texte


def test_uncensored_model_message_has_real_umlauts(dialog, monkeypatch):
    import kira.ui.settings_dialog as sd
    shown = []
    monkeypatch.setattr(sd, "light_information", lambda parent, title, text: shown.append(text))
    dialog._fast_mode.setChecked(True)
    dialog._apply_uncensored_model()
    for ersatz in ("Qualitaets", "Aenderung", "uebernommen", "\u2014"):
        assert ersatz not in shown[-1]


def test_unsupported_hotkey_is_rejected_on_save(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    gewarnt = []
    monkeypatch.setattr(sd, "light_warning", lambda parent, title, text: gewarnt.append(text))
    dialog._hotkey.setText("ctrl+shift+space")
    dialog._save()
    assert gewarnt and "F8" in gewarnt[0]
    assert not (tmp_path / "config.yaml").exists()
    assert "ctrl" not in dialog._hotkey.toolTip() and "ctrl" not in dialog._hotkey.placeholderText()


def _slider(qtbot):
    from kira.ui._comic import ComicSlider
    slider = ComicSlider()
    slider.setRange(1, 50)
    slider.resize(341, 40)
    qtbot.addWidget(slider)
    slider.show()
    return slider


def test_click_on_knob_keeps_value(qtbot):
    from PyQt6.QtCore import QPoint
    slider = _slider(qtbot)
    slider.setValue(50)
    mitte = slider._knob_x() + slider.KNOB / 2
    qtbot.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(int(mitte - 8), slider.height() // 2))
    assert slider.value() == 50


def test_drag_from_knob_moves_relative(qtbot):
    from PyQt6.QtCore import QPoint
    slider = _slider(qtbot)
    slider.setValue(30)
    mitte = slider._knob_x() + slider.KNOB / 2
    y = slider.height() // 2
    qtbot.mousePress(slider, Qt.MouseButton.LeftButton, pos=QPoint(int(mitte - 8), y))
    qtbot.mouseMove(slider, QPoint(int(mitte - 8 - 64), y))
    qtbot.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=QPoint(int(mitte - 8 - 64), y))
    assert 19 <= slider.value() <= 21


def test_click_on_track_still_jumps(qtbot):
    from PyQt6.QtCore import QPoint
    slider = _slider(qtbot)
    slider.setValue(50)
    qtbot.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(20, slider.height() // 2))
    assert slider.value() <= 3


def test_gain_above_five_survives_click_on_knob(dialog, qtbot):
    from PyQt6.QtCore import QPoint
    dialog._gain.setValue(12.0)
    dialog.show()
    slider = dialog._gain_slider
    mitte = slider._knob_x() + slider.KNOB / 2
    qtbot.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(int(mitte - 6), slider.height() // 2))
    assert dialog._gain.value() == 12.0


def test_rows_name_their_controls_for_screen_readers(dialog):
    from PyQt6.QtWidgets import QAbstractButton, QComboBox, QLineEdit, QSlider, QAbstractSpinBox
    unbenannt = [
        w for w in dialog.findChildren((QComboBox, QLineEdit, QSlider, QAbstractSpinBox, QAbstractButton))
        if not w.accessibleName() and not getattr(w, "text", lambda: "")() and w.isVisibleTo(dialog)
    ]
    assert unbenannt == []


def test_edit_feature_is_named_like_on_the_website(dialog):
    from PyQt6.QtWidgets import QLabel
    texte = [w.text() for w in dialog.findChildren(QLabel)]
    assert "Bearbeiten" in texte and "Bearbeiten-Taste" in texte
