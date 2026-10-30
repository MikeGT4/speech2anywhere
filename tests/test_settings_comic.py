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


def test_tabs_follow_the_seven_pages(dialog, qtbot):
    assert [t.text() for t in dialog._tabs] == ["Mikrofon", "Politur", "Tasten", "Anzeige", "Sound", "Lernen", "Über"]
    assert dialog._pages.count() == 7
    for index, tab in enumerate(dialog._tabs):
        qtbot.mouseClick(tab, Qt.MouseButton.LeftButton)
        assert dialog._pages.currentIndex() == index
        assert tab.isChecked()
        assert sum(t.isChecked() for t in dialog._tabs) == 1


@pytest.mark.parametrize("name", [
    "_gain", "_device", "_language", "_learning_enabled", "_styler_model", "_fast_mode",
    "_styler_timeout", "_hotkey", "_edit_enabled", "_edit_hotkey", "_restore_ms", "_hud_style",
    "_hud_live_words", "_sound_feedback",
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
    bubble = dialog._pages.widget(dialog._PAGE_TITLES.index("Über")).findChild(comic.HintBubble)
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


def test_live_words_switch_is_on_by_default_and_saves_without_restart(dialog, monkeypatch, tmp_path):
    assert dialog._hud_live_words.isChecked()
    _message_after_save(dialog, monkeypatch)
    dialog._hud_live_words.setChecked(False)
    text = _message_after_save(dialog, monkeypatch)
    assert "hud_live_words: false" in (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "ab dem nächsten Diktat" in text


def test_sound_switch_is_off_by_default_and_saves_without_restart(dialog, monkeypatch, tmp_path):
    assert not dialog._sound_feedback.isChecked()
    _message_after_save(dialog, monkeypatch)
    dialog._sound_feedback.setChecked(True)
    text = _message_after_save(dialog, monkeypatch)
    assert "sound_feedback: true" in (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "ab dem nächsten Diktat" in text


def test_sound_switches_and_previews_have_their_own_page(dialog):
    sound = dialog._pages.widget(dialog._PAGE_TITLES.index("Sound"))
    display = dialog._pages.widget(dialog._PAGE_TITLES.index("Anzeige"))
    assert list(dialog._sound_events) == ["start", "stopp", "fertig", "fehler"]
    assert list(dialog._sound_previews) == ["start", "stopp", "fertig", "fehler"]
    widgets = [dialog._sound_feedback, *dialog._sound_events.values(), *dialog._sound_previews.values()]
    for widget in widgets:
        assert sound.isAncestorOf(widget)
        assert not display.isAncestorOf(widget)


def test_moment_switches_start_from_the_config_and_save_as_list(dialog, monkeypatch, tmp_path):
    assert [event for event, switch in dialog._sound_events.items() if switch.isChecked()] == ["stopp", "fertig", "fehler"]
    _message_after_save(dialog, monkeypatch)
    dialog._sound_feedback.setChecked(True)
    dialog._sound_events["start"].setChecked(True)
    dialog._sound_events["stopp"].setChecked(False)
    text = _message_after_save(dialog, monkeypatch)
    import yaml
    ui = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))["ui"]
    assert ui["sound_events"] == ["start", "fertig", "fehler"]
    assert ui["sound_feedback"] is True
    assert "ab dem nächsten Diktat" in text


def test_start_switch_warns_about_loudspeakers(dialog):
    assert "Lautsprecher" in dialog._sound_events["start"].toolTip()


def test_guide_names_the_sound_tab():
    from kira.ui.welcome_dialog import _GUIDE_HTML
    assert "Anzeige,\nSound, Lernen und Über" in _GUIDE_HTML


def test_moment_switches_follow_the_main_switch_but_previews_stay_usable(dialog):
    assert not dialog._sound_feedback.isChecked()
    assert not any(switch.isEnabled() for switch in dialog._sound_events.values())
    assert all(button.isEnabled() for button in dialog._sound_previews.values())
    dialog._sound_feedback.setChecked(True)
    assert all(switch.isEnabled() for switch in dialog._sound_events.values())


def test_each_preview_plays_its_own_moment(dialog, qtbot, monkeypatch):
    played = []
    monkeypatch.setattr(dialog._sound_player, "_play", played.append)
    monkeypatch.setattr(dialog._sound_player, "_choose", lambda paths: paths[-1])
    dialog._hud_style.setCurrentIndex(dialog._hud_style.findData("weihnachten"))
    for event in ("start", "fehler"):
        qtbot.mouseClick(dialog._sound_previews[event], Qt.MouseButton.LeftButton)
    assert [(p.parent.name, p.name) for p in played] == [("weihnachten", "start.wav"), ("weihnachten", "fehler-3.wav")]


def test_sound_preview_plays_the_style_picked_in_the_dialog(dialog, qtbot, monkeypatch):
    played = []
    monkeypatch.setattr(dialog._sound_player, "_play", played.append)
    dialog._hud_style.setCurrentIndex(dialog._hud_style.findData("manga"))
    qtbot.mouseClick(dialog._sound_previews["fertig"], Qt.MouseButton.LeftButton)
    assert [(p.parent.name, p.stem) for p in played] == [("manga", "fertig")]


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


def _reference_dot_grid(width, height):
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QColor, QImage, QPainter
    from kira.ui import _comic
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(image)
    p.fillRect(0, 0, width, height, QColor(_comic.CREAM))
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    dot = QColor(_comic.INK)
    dot.setAlphaF(0.035)
    p.setBrush(dot)
    for y in range(7, height, 14):
        for x in range(7, width, 14):
            p.drawEllipse(QPointF(x, y), 0.9, 0.9)
    p.end()
    return image


def test_dot_background_draws_the_same_grid_from_a_cached_tile(qtbot):
    from PyQt6.QtGui import QImage
    from kira.ui import _comic
    widget = _comic.DotBackground()
    qtbot.addWidget(widget)
    widget.resize(97, 61)
    drawn = widget.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    reference = _reference_dot_grid(97, 61)
    worst = max(
        abs(a - b)
        for y in range(61) for x in range(97)
        for a, b in zip(drawn.pixelColor(x, y).getRgb(), reference.pixelColor(x, y).getRgb())
    )
    assert worst <= 1
    assert _comic.DotBackground._tile(1.0) is _comic.DotBackground._tile(1.0)


def test_preview_sits_under_the_style_choice_on_the_display_page(dialog):
    page = dialog._pages.widget(dialog._PAGE_TITLES.index("Anzeige"))
    assert page.isAncestorOf(dialog._hud_preview)
    assert dialog._hud_preview.driver.key == dialog._hud_style.currentData()


def test_style_choice_and_word_switch_drive_the_preview(dialog):
    dialog._hud_style.setCurrentIndex(dialog._hud_style.findData("phosphor"))
    assert dialog._hud_preview.driver.key == "phosphor"
    assert dialog._hud_preview.driver.style.key == "phosphor"
    dialog._hud_live_words.setChecked(False)
    assert dialog._hud_preview.driver.live_words is False
    dialog._hud_live_words.setChecked(True)
    assert dialog._hud_preview.driver.live_words is True


def test_word_switch_tooltip_names_exactly_the_styles_with_fragments(dialog):
    from kira.ui.hud import STYLE_LABELS, create_style
    tip = dialog._hud_live_words.toolTip()
    for key, label in STYLE_LABELS.items():
        assert (f"„{label.split(' (')[0]}" in tip) is create_style(key).live_words, key


def test_preview_runs_only_on_its_own_page(dialog, qtbot):
    dialog.show()
    qtbot.waitExposed(dialog)
    assert not dialog._hud_preview.running
    dialog._tabs[dialog._PAGE_TITLES.index("Anzeige")].click()
    assert dialog._hud_preview.running
    dialog._tabs[0].click()
    assert not dialog._hud_preview.running


def test_display_page_with_preview_stays_shorter_than_polish(dialog):
    heights = {title: dialog._pages.widget(i).sizeHint().height() for i, title in enumerate(dialog._PAGE_TITLES)}
    assert heights["Anzeige"] < heights["Politur"]
    assert max(heights, key=heights.get) == "Politur"


def test_cancel_reaches_a_running_model_pull_in_the_settings(dialog, qtbot, monkeypatch):
    import time

    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QProgressDialog

    import kira.ui.settings_dialog as sd

    seen = []

    class _SlowPull(QObject):
        progress = pyqtSignal(str, 'qint64', 'qint64')
        finished = pyqtSignal(bool, str)

        def __init__(self, model):
            super().__init__()
            self._cancelled = False

        def cancel(self):
            self._cancelled = True

        def run(self):
            t0 = time.monotonic()
            while not self._cancelled and time.monotonic() - t0 < 3:
                time.sleep(0.02)
            seen.append(self._cancelled)
            self.finished.emit(False, "Abgebrochen.")

    monkeypatch.setattr(sd, "_PullWorker", _SlowPull)
    monkeypatch.setattr(sd, "light_critical", lambda *a, **k: None)
    dialog._start_model_pull("gemma4:e4b", "Test")
    dialog.findChild(QProgressDialog).canceled.emit()
    qtbot.waitUntil(lambda: bool(seen), timeout=5000)
    assert seen == [True]


@pytest.mark.parametrize("checked", [0, 18_000_000_000])
def test_model_pull_window_stays_through_the_check_and_names_it(dialog, qtbot, monkeypatch, checked):
    import threading

    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QProgressDialog

    import kira.ui.settings_dialog as sd

    labels = []
    original = QProgressDialog.setLabelText

    def record(self, text):
        labels.append(text)
        original(self, text)

    monkeypatch.setattr(QProgressDialog, "setLabelText", record)
    gate = threading.Event()
    total = 18_000_000_000

    class _Pull(QObject):
        progress = pyqtSignal(str, 'qint64', 'qint64')
        finished = pyqtSignal(bool, str)

        def __init__(self, model):
            super().__init__()
            self._cancelled = False

        def cancel(self):
            self._cancelled = True
            gate.set()

        def run(self):
            self.progress.emit("pulling manifest", 0, 0)
            self.progress.emit("pulling 2dd70431afed", 3_600_000_000, total)
            self.progress.emit("pulling 2dd70431afed", total, total)
            self.progress.emit("verifying sha256 digest", checked, checked)
            gate.wait(5)
            self.finished.emit(False, "Abgebrochen.")

    monkeypatch.setattr(sd, "_PullWorker", _Pull)
    monkeypatch.setattr(sd, "light_critical", lambda *a, **k: None)
    dialog._start_model_pull("gemma4:26b-a4b-it-qat", "Test")
    progress = dialog.findChild(QProgressDialog)
    head = "Lade gemma4:26b-a4b-it-qat\n"
    qtbot.waitUntil(lambda: labels[-1:] == [f"{head}Prüfsumme wird geprüft …"], timeout=5000)
    assert f"{head}3,6 von 18,0 GB · 20 % · startet …" in labels
    assert f"{head}wird abgeschlossen …" in labels
    assert not any("pulling" in text for text in labels)
    assert progress.isVisible()
    assert (progress.minimum(), progress.maximum()) == (0, 0)
    progress.canceled.emit()
    qtbot.waitUntil(lambda: not progress.isVisible(), timeout=5000)
