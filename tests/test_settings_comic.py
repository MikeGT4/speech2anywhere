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


def test_tab_marks_focus_only_after_keyboard_navigation(dialog):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QFocusEvent
    from PyQt6.QtWidgets import QApplication

    def focus(kind, reason):
        QApplication.sendEvent(tab, QFocusEvent(kind, reason))
        return tab._keyboard_focus

    tab = dialog._tabs[1]
    assert tab.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert not focus(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason)
    dialog.setAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange)
    assert focus(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason)
    assert not focus(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason)
    assert not focus(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason)


def test_footer_shows_copyright_and_logo(dialog):
    from PyQt6.QtWidgets import QLabel
    notes = [label for label in dialog.findChildren(QLabel) if label.text() == "© 2026 Mike Pollow"]
    assert len(notes) == 1
    logos = [label for label in notes[0].parentWidget().findChildren(QLabel) if not label.pixmap().isNull()]
    assert len(logos) == 1
    assert "Fast alles wirkt nach einem kurzen Neustart." not in " ".join(
        label.text() for label in dialog.findChildren(QLabel)
    )


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


def test_language_choice_offers_the_measured_languages(dialog):
    codes = [dialog._language.itemData(i) for i in range(dialog._language.count())]
    assert codes == ["auto", "de", "en", "fr", "it", "nl", "pl", "pt", "es"]


def test_hand_set_language_is_shown_and_kept_when_saving(qtbot, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    cfg = Config()
    cfg.whisper.language = "sv"
    monkeypatch.setattr(sd, "load_config", lambda: cfg)
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
    monkeypatch.setattr(sd, "light_information", lambda *a, **k: None)
    monkeypatch.setattr(sd, "light_warning", lambda *a, **k: None)
    dlg = sd.SettingsDialog()
    qtbot.addWidget(dlg)
    assert dlg._language.currentData() == "sv"
    assert dlg._language.currentText() == "Andere (sv)"
    dlg._save()
    assert "language: sv" in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_toggle_switch_sits_on_a_page_and_starts_off(dialog):
    assert dialog._pages.isAncestorOf(dialog._toggle_mode)
    assert not dialog._toggle_mode.isChecked()


def test_toggle_mode_is_saved_and_asks_for_a_restart(dialog, monkeypatch, tmp_path):
    _message_after_save(dialog, monkeypatch)
    dialog._toggle_mode.setChecked(True)
    text = _message_after_save(dialog, monkeypatch)
    assert "mode: toggle" in (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "Neustart" in text


def test_microphone_hint_follows_the_key_mode(qtbot, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    cfg = Config()
    cfg.hotkey.mode = "toggle"
    monkeypatch.setattr(sd, "load_config", lambda: cfg)
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
    dlg = sd.SettingsDialog()
    qtbot.addWidget(dlg)
    from PyQt6.QtWidgets import QLabel
    texts = " ".join(label.text() for label in dlg.findChildren(QLabel))
    assert "gedrückt und sprich" not in texts
    assert "sprich und drück noch einmal" in texts
    assert dlg._toggle_mode.isChecked()


def test_interface_language_sits_on_a_page_and_starts_on_auto(dialog):
    assert dialog._pages.isAncestorOf(dialog._ui_language)
    assert dialog._ui_language.currentData() == "auto"
    assert [dialog._ui_language.itemData(i) for i in range(dialog._ui_language.count())] == ["auto", "de", "en"]


def test_interface_language_is_saved_and_asks_for_a_restart(dialog, monkeypatch, tmp_path):
    _message_after_save(dialog, monkeypatch)
    dialog._ui_language.setCurrentIndex(dialog._ui_language.findData("en"))
    text = _message_after_save(dialog, monkeypatch)
    assert "language: en" in (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "Neustart" in text


def test_unchanged_interface_language_is_not_written(dialog, monkeypatch, tmp_path):
    _message_after_save(dialog, monkeypatch)
    written = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "ui:" not in written or "language: auto" not in written.split("ui:")[-1]


@pytest.fixture
def restartable(qtbot, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "load_config", lambda: Config())
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
    seen = {"info": [], "warning": [], "asked": 0, "restarts": 0, "answer": False, "restart_ok": True}
    monkeypatch.setattr(sd, "light_information", lambda _parent, _title, text: seen["info"].append(text))
    monkeypatch.setattr(sd, "light_warning", lambda _parent, _title, text: seen["warning"].append(text))

    def ask(_parent):
        seen["asked"] += 1
        return seen["answer"]

    def restart():
        seen["restarts"] += 1
        return seen["restart_ok"]

    monkeypatch.setattr(sd, "_ask_restart", ask)
    dlg = sd.SettingsDialog(request_restart=restart)
    qtbot.addWidget(dlg)
    dlg._save()
    seen.update(info=[], warning=[], asked=0, restarts=0, answer=True)
    return dlg, seen


def test_restart_is_offered_when_a_setting_needs_it(restartable):
    dlg, seen = restartable
    dlg._gain.setValue(2.4)
    dlg._save()
    assert seen["asked"] == 1
    assert seen["restarts"] == 1
    assert seen["info"] == []
    assert seen["warning"] == []


def test_later_leaves_the_app_running(restartable):
    dlg, seen = restartable
    seen["answer"] = False
    dlg._gain.setValue(2.4)
    dlg._save()
    assert seen["asked"] == 1
    assert seen["restarts"] == 0
    assert seen["warning"] == []


def test_no_restart_question_when_the_change_works_right_away(restartable):
    dlg, seen = restartable
    dlg._hud_style.setCurrentIndex(dlg._hud_style.findData("klartext"))
    dlg._save()
    assert seen["asked"] == 0
    assert "ab dem nächsten Diktat" in seen["info"][-1]


def test_failed_restart_says_how_to_do_it_by_hand(restartable):
    dlg, seen = restartable
    seen["restart_ok"] = False
    dlg._gain.setValue(2.4)
    dlg._save()
    assert seen["restarts"] == 1
    assert "Beenden" in seen["warning"][-1]


def test_restart_question_has_two_plain_buttons(qtbot):
    import kira.ui.settings_dialog as sd
    box = sd._restart_question(None)
    qtbot.addWidget(box)
    assert {button.text() for button in box.buttons()} == {"Jetzt neu starten", "Später"}
    assert box.defaultButton().text() == "Jetzt neu starten"
    assert "Neustart" in box.text() + box.informativeText()


def test_restart_question_keeps_each_thought_on_its_own_line(qtbot):
    from PyQt6.QtWidgets import QLabel
    import kira.ui.settings_dialog as sd
    box = sd._restart_question(None)
    qtbot.addWidget(box)
    box.show()
    qtbot.waitExposed(box)
    label = box.findChild(QLabel, "qt_msgbox_informativelabel")
    lines = label.text().splitlines()
    assert len(lines) == 2
    assert label.width() >= max(label.fontMetrics().horizontalAdvance(line) for line in lines)


def _keys_page_texts(qtbot, tmp_path, monkeypatch, mode):
    import kira.ui.settings_dialog as sd
    from PyQt6.QtWidgets import QLabel, QWidget
    cfg = Config()
    cfg.hotkey.mode = mode
    monkeypatch.setattr(sd, "load_config", lambda: cfg)
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
    dlg = sd.SettingsDialog()
    qtbot.addWidget(dlg)
    labels = [label.text() for label in dlg.findChildren(QLabel)]
    tips = [widget.toolTip() for widget in dlg.findChildren(QWidget)]
    return " ".join(labels + tips)


def test_keys_page_describes_holding_in_hold_mode(qtbot, tmp_path, monkeypatch):
    texts = _keys_page_texts(qtbot, tmp_path, monkeypatch, "hold")
    assert "Gedrückt halten und sprechen." in texts
    assert "Halten, sagen, was anders werden soll." in texts


def test_keys_page_describes_pressing_twice_in_toggle_mode(qtbot, tmp_path, monkeypatch):
    texts = _keys_page_texts(qtbot, tmp_path, monkeypatch, "toggle")
    assert "Gedrückt halten und sprechen." not in texts
    assert "Halten, sagen, was anders werden soll." not in texts
    assert "die Bearbeiten-Taste halten" not in texts
    assert "Einmal drücken, sprechen, noch einmal drücken." in texts
    assert "Drücken, sagen, was anders werden soll, noch einmal drücken." in texts


def _labels_of_first_page(dialog):
    from PyQt6.QtWidgets import QLabel
    return [label.text() for label in dialog._pages.widget(0).findChildren(QLabel) if label.text()]


def _saved_text(tmp_path):
    path = tmp_path / "config.yaml"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_compute_switch_is_the_first_row_on_the_microphone_page(dialog):
    assert _labels_of_first_page(dialog)[1] == "Rechnen auf"
    assert [dialog._compute.itemData(i) for i in range(dialog._compute.count())] == ["cpu", "gpu"]
    assert dialog._compute.currentData() == "gpu"


def test_compute_help_button_opens_the_help_page(dialog, monkeypatch):
    from PyQt6.QtWidgets import QPushButton
    import kira.ui.compute_help_dialog as help_module
    opened = []
    monkeypatch.setattr(help_module.ComputeHelpDialog, "exec", lambda self: opened.append(self) or 0)
    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Was ist der Unterschied?")
    button.click()
    assert len(opened) == 1


def test_processor_mode_locks_the_fast_mode(dialog):
    dialog._compute.setCurrentIndex(dialog._compute.findData("cpu"))
    assert not dialog._fast_mode.isEnabled()
    dialog._compute.setCurrentIndex(dialog._compute.findData("gpu"))
    assert dialog._fast_mode.isEnabled()


def test_saving_processor_mode_writes_device_and_model(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    small = tmp_path / "faster-whisper-small"
    small.mkdir()
    (small / "model.bin").write_bytes(b"x")
    monkeypatch.setattr(sd, "_CPU_WHISPER_DIR", small)
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: True)
    dialog._compute.setCurrentIndex(dialog._compute.findData("cpu"))
    dialog._save()
    saved = _saved_text(tmp_path)
    assert "device: cpu" in saved
    assert f"cpu_model: {small.as_posix()}" in saved


def test_missing_processor_model_is_downloaded_before_saving(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    target = tmp_path / "faster-whisper-small"
    monkeypatch.setattr(sd, "_CPU_WHISPER_DIR", target)
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: True)
    downloads = []
    monkeypatch.setattr(dialog, "_whisper_download_blocking", lambda repo, where: downloads.append((repo, where)) or True)
    dialog._compute.setCurrentIndex(dialog._compute.findData("cpu"))
    dialog._save()
    assert downloads == [("Systran/faster-whisper-small", target)]
    assert "device: cpu" in _saved_text(tmp_path)


def test_cancelled_download_saves_nothing(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "_CPU_WHISPER_DIR", tmp_path / "faster-whisper-small")
    monkeypatch.setattr(dialog, "_whisper_download_blocking", lambda repo, where: False)
    dialog._compute.setCurrentIndex(dialog._compute.findData("cpu"))
    dialog._save()
    assert _saved_text(tmp_path) == ""


def test_graphics_card_without_nvidia_saves_nothing_and_warns(qtbot, tmp_path, monkeypatch):
    import kira.gpu_check as gpu_check
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "load_config", lambda: Config.model_validate({"whisper": {"device": "cpu"}}))
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
    warnings = []
    monkeypatch.setattr(sd, "light_warning", lambda *args, **kwargs: warnings.append(args[2]))
    monkeypatch.setattr(sd, "light_information", lambda *a, **k: None)
    monkeypatch.setattr(gpu_check, "detect_gpu", lambda: None)
    dlg = sd.SettingsDialog()
    qtbot.addWidget(dlg)
    dlg._compute.setCurrentIndex(dlg._compute.findData("gpu"))
    dlg._save()
    assert _saved_text(tmp_path) == ""
    assert "Keine NVIDIA-Grafikkarte gefunden." in warnings[0]
    assert dlg._compute.currentData() == "cpu"


def test_unchanged_compute_settings_add_nothing(dialog, tmp_path):
    dialog._save()
    saved = _saved_text(tmp_path)
    whisper = saved.split("whisper:")[1].split("styler:")[0]
    assert "device:" not in whisper
    assert "cpu_model:" not in whisper
    assert "enabled:" not in saved.split("styler:")[1].split("injector:")[0]


def test_polish_switch_is_saved(dialog, tmp_path):
    dialog._polish_enabled.setChecked(False)
    dialog._save()
    assert "enabled: false" in _saved_text(tmp_path).split("styler:")[1]


def test_only_absolute_paths_count_as_model_folders(tmp_path):
    import kira.ui.settings_dialog as sd
    assert sd._looks_like_path(str(tmp_path / "faster-whisper-small"))
    assert not sd._looks_like_path("Systran/faster-whisper-large-v3")
    assert not sd._looks_like_path("mlx-community/whisper-large-v3-turbo")
    assert not sd._looks_like_path("small")


def test_processor_switch_with_polish_off_still_loads_the_edit_model(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    small = tmp_path / "faster-whisper-small"
    small.mkdir()
    (small / "model.bin").write_bytes(b"x")
    monkeypatch.setattr(sd, "_CPU_WHISPER_DIR", small)
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: False)
    pulls = []
    monkeypatch.setattr(dialog, "_pull_blocking", lambda model: pulls.append(model) or True)
    monkeypatch.setattr(dialog, "_release_models", lambda old: None)
    dialog._polish_enabled.setChecked(False)
    dialog._compute.setCurrentIndex(dialog._compute.findData("cpu"))
    dialog._save()
    assert pulls == ["gemma4:e4b"]
    assert "device: cpu" in _saved_text(tmp_path)


def test_turning_polish_on_loads_a_missing_model(qtbot, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "load_config", lambda: Config.model_validate(
        {"styler": {"enabled": False, "model": "gemma4:12b"}}))
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
    monkeypatch.setattr(sd, "light_information", lambda *a, **k: None)
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: False)
    dlg = sd.SettingsDialog()
    qtbot.addWidget(dlg)
    pulls = []
    monkeypatch.setattr(dlg, "_pull_blocking", lambda model: pulls.append(model) or False)
    dlg._polish_enabled.setChecked(True)
    dlg._save()
    assert pulls == ["gemma4:12b"]
    assert _saved_text(tmp_path) == ""


def test_hand_set_processor_model_name_is_kept(qtbot, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "load_config", lambda: Config.model_validate({"whisper": {"cpu_model": "medium"}}))
    monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
    monkeypatch.setattr(sd, "light_information", lambda *a, **k: None)
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: True)
    dlg = sd.SettingsDialog()
    qtbot.addWidget(dlg)
    downloads = []
    monkeypatch.setattr(dlg, "_whisper_download_blocking", lambda repo, where: downloads.append(repo) or True)
    monkeypatch.setattr(dlg, "_release_models", lambda old: None)
    dlg._compute.setCurrentIndex(dlg._compute.findData("cpu"))
    dlg._save()
    assert downloads == []
    saved = _saved_text(tmp_path)
    assert "device: cpu" in saved
    assert "cpu_model:" not in saved


def test_switching_releases_the_models_of_the_old_mode(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    small = tmp_path / "faster-whisper-small"
    small.mkdir()
    (small / "model.bin").write_bytes(b"x")
    monkeypatch.setattr(sd, "_CPU_WHISPER_DIR", small)
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: True)
    released = []

    class FakeClient:
        def generate(self, model, keep_alive):
            released.append((model, keep_alive))

    monkeypatch.setattr(sd, "_ollama_client", lambda: FakeClient())
    dialog._compute.setCurrentIndex(dialog._compute.findData("cpu"))
    dialog._save()
    assert sorted(released) == [("gemma2:2b", 0), ("gemma4:e4b", 0)]


def test_processor_mode_locks_live_words_and_the_uncensored_model(dialog):
    dialog._compute.setCurrentIndex(dialog._compute.findData("cpu"))
    assert not dialog._hud_live_words.isEnabled()
    assert not dialog._uncensored_btn.isEnabled()
    dialog._compute.setCurrentIndex(dialog._compute.findData("gpu"))
    assert dialog._hud_live_words.isEnabled()
    assert dialog._uncensored_btn.isEnabled()


def test_hugging_face_button_opens_the_gguf_search(dialog, monkeypatch):
    from PyQt6.QtWidgets import QPushButton
    import kira.ui.settings_dialog as sd
    opened = []
    monkeypatch.setattr(sd.comic, "_open_url", opened.append)
    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Hugging Face…")
    button.click()
    assert opened == ["https://huggingface.co/models?library=gguf&sort=trending"]
    assert "hf.co/" in button.toolTip()


def test_new_model_name_is_loaded_before_saving(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: False)
    pulls = []
    monkeypatch.setattr(dialog, "_pull_blocking", lambda model: pulls.append(model) or True)
    name = "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M"
    dialog._styler_model.setText(name)
    dialog._save()
    assert pulls == [name]
    assert f"model: {name}" in _saved_text(tmp_path)


def test_failed_download_of_a_new_model_saves_nothing(dialog, tmp_path, monkeypatch):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "_ollama_model_installed", lambda model: False)
    monkeypatch.setattr(dialog, "_pull_blocking", lambda model: False)
    dialog._styler_model.setText("hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M")
    dialog._save()
    assert _saved_text(tmp_path) == ""
