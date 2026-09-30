# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QDialog, QLabel, QMessageBox, QProgressBar, QProgressDialog, QPushButton, QWizard,
)

from kira.config import Config

YELLOW = "#FFC400"
RED = "#E5484D"
INK = "#111111"
TRACK = "#EFE9D6"
WHITE = "#FFFFFF"


def _near(color: QColor, expected: str, tolerance: int = 10) -> bool:
    want = QColor(expected)
    return all(abs(a - b) <= tolerance for a, b in (
        (color.red(), want.red()), (color.green(), want.green()), (color.blue(), want.blue()),
    ))


def _render(widget) -> None:
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    widget.show()
    QApplication.processEvents()


def _texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def _yes_no_box() -> QMessageBox:
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Question)
    box.setText("Version v0.5.0 ist verfügbar.")
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.Yes)
    return box


def test_message_puts_first_paragraph_in_headline(qtbot):
    from kira.ui._dialog_style import _build_message
    box = _build_message(None, QMessageBox.Icon.Critical, "Speech2Anywhere",
                         "Update-Suche fehlgeschlagen.\n\nHTTP 503: Service Unavailable\nbitte später")
    qtbot.addWidget(box)
    assert box.text() == "Update-Suche fehlgeschlagen."
    assert box.informativeText() == "HTTP 503: Service Unavailable\nbitte später"


def test_message_without_blank_line_has_no_detail(qtbot):
    from kira.ui._dialog_style import _build_message
    box = _build_message(None, QMessageBox.Icon.Information, "Speech2Anywhere",
                         "Speech2Anywhere ist aktuell (v0.4.3).")
    qtbot.addWidget(box)
    assert box.text() == "Speech2Anywhere ist aktuell (v0.4.3)."
    assert box.informativeText() == ""


def test_standard_buttons_speak_german(qtbot):
    from kira.ui._dialog_style import apply_light_theme
    box = _yes_no_box()
    qtbot.addWidget(box)
    apply_light_theme(box)
    assert box.button(QMessageBox.StandardButton.Yes).text() == "Ja"
    assert box.button(QMessageBox.StandardButton.No).text() == "Nein"


def test_own_button_texts_stay(qtbot):
    from kira.ui._dialog_style import apply_light_theme
    box = _yes_no_box()
    qtbot.addWidget(box)
    box.button(QMessageBox.StandardButton.Yes).setText("Trotzdem laden")
    apply_light_theme(box)
    assert box.button(QMessageBox.StandardButton.Yes).text() == "Trotzdem laden"
    assert box.button(QMessageBox.StandardButton.No).text() == "Nein"


def test_default_button_is_yellow_the_other_white(qtbot):
    from kira.ui._dialog_style import apply_light_theme
    box = _yes_no_box()
    qtbot.addWidget(box)
    apply_light_theme(box)
    _render(box)
    yes = box.button(QMessageBox.StandardButton.Yes).grab().toImage()
    no = box.button(QMessageBox.StandardButton.No).grab().toImage()
    assert _near(yes.pixelColor(8, yes.height() // 2), YELLOW)
    assert _near(no.pixelColor(8, no.height() // 2), WHITE)


@pytest.mark.parametrize("kind", [QMessageBox.Icon.Information, QMessageBox.Icon.Question])
def test_info_and_question_show_the_mascot_not_the_windows_symbol(qtbot, kind):
    from kira.ui._dialog_style import apply_light_theme
    box = QMessageBox()
    qtbot.addWidget(box)
    box.setIcon(kind)
    windows_symbol = box.iconPixmap().toImage()
    apply_light_theme(box)
    shown = box.iconPixmap()
    assert not shown.isNull()
    assert shown.toImage() != windows_symbol


@pytest.mark.parametrize(("kind", "spot", "color"), [
    (QMessageBox.Icon.Warning, (0.3, 0.78), YELLOW),
    (QMessageBox.Icon.Critical, (0.25, 0.47), RED),
])
def test_warning_and_critical_show_comic_symbols(qtbot, kind, spot, color):
    from kira.ui._dialog_style import apply_light_theme
    box = QMessageBox()
    qtbot.addWidget(box)
    box.setIcon(kind)
    windows_symbol = box.iconPixmap().toImage()
    apply_light_theme(box)
    image = box.iconPixmap().toImage()
    assert image != windows_symbol
    assert _near(image.pixelColor(round(image.width() * spot[0]), round(image.height() * spot[1])), color)


def test_titlebar_turns_ink_once_on_first_show(qtbot, monkeypatch):
    import kira.ui._comic as comic
    from kira.ui._dialog_style import apply_light_theme
    calls = []
    monkeypatch.setattr(comic, "dark_titlebar", calls.append)
    dialog = QDialog()
    qtbot.addWidget(dialog)
    apply_light_theme(dialog)
    assert calls == []
    _render(dialog)
    dialog.hide()
    _render(dialog)
    assert calls == [dialog]


def test_progress_bar_fills_yellow_on_track(qtbot):
    from kira.ui._dialog_style import apply_light_theme
    dialog = QProgressDialog("Lade Update-Bundle...", "Abbrechen", 0, 100)
    qtbot.addWidget(dialog)
    dialog.setAutoClose(False)
    apply_light_theme(dialog)
    dialog.setValue(50)
    _render(dialog)
    bar = dialog.findChild(QProgressBar).grab().toImage()
    middle = bar.height() // 2
    assert _near(bar.pixelColor(round(bar.width() * 0.2), middle), YELLOW)
    assert _near(bar.pixelColor(round(bar.width() * 0.85), middle), TRACK)


@pytest.fixture
def wizard(qtbot, tmp_path):
    from kira.setup_wizard import SetupWizard
    w = SetupWizard(tmp_path / "whisper", tmp_path / "OllamaSetup.exe")
    qtbot.addWidget(w)
    return w


def test_wizard_buttons_speak_german(wizard):
    assert wizard.buttonText(QWizard.WizardButton.NextButton) == "Weiter"
    assert wizard.buttonText(QWizard.WizardButton.BackButton) == "Zurück"
    assert wizard.buttonText(QWizard.WizardButton.CancelButton) == "Abbrechen"
    assert wizard.buttonText(QWizard.WizardButton.FinishButton) == "Fertigstellen"
    assert wizard.buttonText(QWizard.WizardButton.CommitButton) == "Weiter"


def test_wizard_header_is_ink(wizard):
    _render(wizard)
    image = wizard.grab().toImage()
    assert _near(image.pixelColor(6, 6), INK)


def test_dialog_header_shows_title_as_active_tab(qtbot):
    import kira.ui._comic as comic
    header = comic.dialog_header("Über")
    qtbot.addWidget(header)
    tab = header.findChild(comic.BubbleTab)
    assert tab.text() == "Über"
    assert tab.isChecked()
    _render(header)
    qtbot.mouseClick(tab, Qt.MouseButton.LeftButton)
    assert tab.isChecked()


def test_setup_hint_lists_only_what_is_missing(qtbot):
    from kira.ui.setup_hint_dialog import SetupHintDialog
    dialog = SetupHintDialog(mic_ok=True, ollama_ok=False)
    qtbot.addWidget(dialog)
    texts = " ".join(_texts(dialog))
    assert "Ollama nicht erreichbar" in texts
    assert "Mikrofon-Zugriff fehlt" not in texts
    assert "Mikrofon-Einstellungen öffnen" not in [b.text() for b in dialog.findChildren(QPushButton)]


def test_setup_hint_mic_button_opens_settings(qtbot):
    from kira.ui.setup_hint_dialog import SetupHintDialog
    dialog = SetupHintDialog(mic_ok=False, ollama_ok=True)
    qtbot.addWidget(dialog)
    assert "Mikrofon-Zugriff fehlt" in " ".join(_texts(dialog))
    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Mikrofon-Einstellungen öffnen")
    _render(dialog)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert dialog.user_clicked_open_mic_settings is True
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_about_shows_the_configured_setup(qtbot, monkeypatch):
    from kira import __version__
    import kira.ui.about_dialog as about
    cfg = Config()
    cfg.audio.input_device = "USB Microphone"
    cfg.styler.model = "gemma4:26b-a4b-it-qat"
    monkeypatch.setattr(about, "_safe_load_config", lambda: cfg)
    dialog = about.AboutDialog()
    qtbot.addWidget(dialog)
    texts = " ".join(_texts(dialog))
    assert __version__ in texts
    assert "USB Microphone" in texts
    assert "gemma4:26b-a4b-it-qat" in texts
    assert "F8 halten" in texts


def test_welcome_accept_writes_marker_only_in_welcome_mode(qtbot, tmp_path, monkeypatch):
    import kira.ui.welcome_dialog as welcome
    marker = tmp_path / "Kira" / ".welcomed"
    monkeypatch.setattr(welcome, "_WELCOME_MARKER", marker)
    helper = welcome.WelcomeDialog(as_help=True)
    qtbot.addWidget(helper)
    helper.accept()
    assert not marker.exists()
    dialog = welcome.WelcomeDialog(as_help=False)
    qtbot.addWidget(dialog)
    assert dialog.cb_dont_show.isChecked()
    dialog.accept()
    assert marker.exists()


def test_gpu_scan_animates_only_between_start_and_finish(qtbot):
    from kira.ui._gpu_scan_dialog import GpuScanDialog
    dialog = GpuScanDialog()
    qtbot.addWidget(dialog)
    dialog.start()
    qtbot.waitUntil(lambda: dialog._scan._phase > 0, timeout=1000)
    dialog.finish()
    frozen = dialog._scan._phase
    qtbot.wait(120)
    assert dialog._scan._phase == frozen
    assert not dialog.isVisible()


def test_about_bubble_shows_the_digitalroots_logo(qtbot, monkeypatch):
    import kira.ui.about_dialog as about
    import kira.ui._comic as comic
    monkeypatch.setattr(about, "_safe_load_config", Config)
    dialog = about.AboutDialog()
    qtbot.addWidget(dialog)
    labels = dialog.findChild(comic.HintBubble).findChildren(QLabel)
    assert not any("Digitalroots" in label.text() for label in labels)
    assert any(label.pixmap() is not None and not label.pixmap().isNull() for label in labels)


def _record_dwm(monkeypatch) -> dict:
    import ctypes
    asked = {}

    def fake(hwnd, attribute, data, size):
        asked[attribute.value] = data._obj.value
        return 0

    monkeypatch.setattr(ctypes.windll.dwmapi, "DwmSetWindowAttribute", fake, raising=False)
    return asked


def test_gpu_scan_asks_windows_for_no_border(qtbot, monkeypatch):
    from kira.ui._gpu_scan_dialog import GpuScanDialog
    asked = _record_dwm(monkeypatch)
    dialog = GpuScanDialog()
    qtbot.addWidget(dialog)
    dialog.start()
    assert asked == {2: 1, 33: 1, 34: 0xFFFFFFFE}
    dialog.finish()


def test_comic_menu_asks_windows_for_no_border(qtbot, monkeypatch):
    import kira.ui._comic as comic
    from PyQt6.QtCore import QPoint
    asked = _record_dwm(monkeypatch)
    menu = comic.ComicMenu()
    qtbot.addWidget(menu)
    menu.addAction("Einstellungen…")
    menu.popup(QPoint(10, 10))
    assert asked.get(34) == 0xFFFFFFFE and asked.get(33) == 1


def test_brand_logo_opens_digitalroots_by_click_and_key(qtbot, monkeypatch):
    import kira.ui._comic as comic
    geoeffnet = []
    monkeypatch.setattr(comic, "_open_url", geoeffnet.append)
    logo = comic.brand_logo(20)
    qtbot.addWidget(logo)
    qtbot.mouseClick(logo, Qt.MouseButton.LeftButton)
    assert geoeffnet == ["https://www.digitalroots.de/"]
    assert logo.cursor().shape() == Qt.CursorShape.PointingHandCursor
    logo.setFocus()
    qtbot.keyClick(logo, Qt.Key.Key_Return)
    assert geoeffnet == ["https://www.digitalroots.de/"] * 2
    assert logo.accessibleName()


def test_text_areas_use_16px():
    import re
    import kira.ui._comic as comic
    regel = re.search(r"QTextEdit, QPlainTextEdit \{(.*?)\}", comic.dialog_qss(), re.S).group(1)
    assert "font-size: 16px" in regel


def test_guide_uses_current_names():
    import kira.ui.welcome_dialog as welcome
    for alt in ("AI-Editing", "Polish-LLM", "Settings →", "No-Op"):
        assert alt not in welcome._GUIDE_HTML, alt


def test_about_fits_small_screens(qtbot, monkeypatch):
    import kira.ui.about_dialog as about
    monkeypatch.setattr(about, "_safe_load_config", Config)
    dialog = about.AboutDialog()
    qtbot.addWidget(dialog)
    assert dialog.minimumSizeHint().height() <= 690
