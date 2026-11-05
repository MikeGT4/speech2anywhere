# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import ast
import re
import sys
from pathlib import Path
import pytest
from kira import texte
from kira.texte_en import EN

WURZEL = Path(__file__).resolve().parent.parent
QUELLEN = [p for p in sorted((WURZEL / "kira").rglob("*.py")) if p.name != "texte_en.py"]
DEUTSCHE_WOERTER = {"der", "die", "das", "und", "nicht", "ist", "mit", "für", "wird", "dein", "deine", "du", "bitte"}
FELD = re.compile(r"\{[^{}]*\}")


@pytest.fixture
def english():
    texte.set_language("en")
    yield
    texte.set_language("de")


def _marked_texts() -> set[str]:
    found = set()
    for pfad in QUELLEN:
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
                    and knoten.func.id in ("tr", "N_") and knoten.args
                    and isinstance(knoten.args[0], ast.Constant) and isinstance(knoten.args[0].value, str)):
                found.add(knoten.args[0].value)
    return found


def _all_literals() -> set[str]:
    found = set()
    for pfad in QUELLEN:
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
                found.add(knoten.value)
    return found


def _fields(text: str) -> list[str]:
    return sorted(FELD.findall(text.replace("{{", "").replace("}}", "")))


def test_every_marked_text_has_an_english_entry():
    missing = sorted(text for text in _marked_texts() if text not in EN)
    assert missing == []


def test_every_english_entry_belongs_to_a_text_in_the_program():
    literals = _all_literals()
    stale = sorted(text for text in EN if text not in literals)
    assert stale == []


def test_english_entries_keep_placeholders_separators_and_line_edges():
    wrong = []
    for german, english_text in EN.items():
        if _fields(german) != _fields(english_text):
            wrong.append(("Platzhalter", german))
        if german.count("|") != english_text.count("|"):
            wrong.append(("Trenner", german))
        if german.startswith("\n") != english_text.startswith("\n") or german.endswith("\n") != english_text.endswith("\n"):
            wrong.append(("Rand", german))
    assert wrong == []


def test_no_english_entry_repeats_its_german_text():
    assert [german for german, english_text in EN.items() if german == english_text] == []


def test_numbers_use_a_point_in_english_and_a_comma_in_german(english):
    from kira import progress
    assert progress._number(1.5, 1) == "1.5"
    texte.set_language("de")
    assert progress._number(1.5, 1) == "1,5"


def test_progress_phases_come_out_in_english(english):
    from kira import progress
    assert texte.tr(progress.PREPARING) == "preparing…"
    assert texte.tr(progress.PULL_PHASES["writing manifest"]) == "registering model…"


def test_a_word_can_read_differently_in_its_place(english):
    assert texte.tr("ZU NAH") == "TOO CLOSE"
    assert texte.tr("ZU NAH", "manga-streifen") == "CLOSE"
    assert texte.tr("blubb!") == "yada!"
    assert texte.tr("blubb!", "halloween") == "blub!"
    texte.set_language("de")
    assert texte.tr("ZU NAH", "manga-streifen") == "ZU NAH"


def test_place_specific_entries_belong_to_translated_texts():
    from kira.texte_en import EN_CONTEXT
    assert sorted(text for (_place, text) in EN_CONTEXT if text not in EN) == []
    assert sorted(text for (_place, text), english_text in EN_CONTEXT.items() if english_text == EN[text]) == []


def test_decimal_mark_follows_the_language(english):
    assert texte.decimal_mark() == "."
    texte.set_language("de")
    assert texte.decimal_mark() == ","


def test_progress_start_comes_out_in_english(english):
    from kira import progress
    meter = progress.RateMeter()
    meter.add(0)
    line = progress.describe(1, 100, meter, total_only=None)
    assert "startet" not in line
    assert line.endswith("starting…")


def test_gpu_verdict_comes_out_in_english(english, monkeypatch):
    from kira import gpu_check
    monkeypatch.setattr(gpu_check, "detect_gpu", lambda: gpu_check.GpuInfo(name="RTX 5090", vram_gb=32.0, cuda_available=True))
    comfortable = gpu_check.assess("large-v3", "gemma4:12b").message
    monkeypatch.setattr(gpu_check, "detect_gpu", lambda: gpu_check.GpuInfo(name="RTX 4070", vram_gb=12.0, cuda_available=True))
    tight = gpu_check.assess("large-v3", "gemma4:12b").message
    for message in (comfortable, tight):
        for german in ("Grafikspeicher", "Spracherkennung", "Sprachmodell", "Summe", "Reserve", "Knapp"):
            assert german not in message, (german, message)
    assert "Video memory: 32.0 GB" in comfortable


def test_update_reason_names_python_in_english(english):
    from kira.texte import tr
    assert tr("Python {} statt {}.").format("3.13", "3.12") == "Python 3.13 instead of 3.12."


if sys.platform == "win32":
    from PyQt6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit, QWidget

    def _visible_texts(root) -> set[str]:
        found = set()
        for widget in [root] + root.findChildren(QWidget):
            for value in (widget.windowTitle(), widget.toolTip(), widget.accessibleName(), widget.accessibleDescription()):
                if value:
                    found.add(value)
            if isinstance(widget, (QLabel, QAbstractButton)) and widget.text():
                found.add(widget.text())
            if isinstance(widget, QLineEdit) and widget.placeholderText():
                found.add(widget.placeholderText())
            if isinstance(widget, QComboBox):
                found.update(widget.itemText(i) for i in range(widget.count()))
        return found

    LATIN = re.compile(r"[A-Za-zÄÖÜäöüß]")
    NAMES = frozenset({
        "Speech2Anywhere", "Sound", "Version", "Deutsch", "English", "Comic", "Manga (Shōnen)", "Halloween", "Phosphor",
        "Gun Barrel", "Log:", "Whisper: ", "Ollama: ", "Gemma: ", "Setup", "Speech2Anywhere Setup",
        "Speech2Anywhere: Setup", "© 2026 Mike Pollow · Digitalroots", "USB Microphone", "Kubernetes", "Docker",
        "kuh bernetes", "doku", "auf kuh bernetes", "mit doku", "f8", "f9",
    })

    def _lettered(texts) -> set[str]:
        return {text for text in texts if len(LATIN.findall(text)) >= 2}

    def _table_texts(root) -> set[str]:
        from PyQt6.QtWidgets import QPlainTextEdit, QTableWidget, QTextEdit
        found = set()
        for table in root.findChildren(QTableWidget):
            for column in range(table.columnCount()):
                head = table.horizontalHeaderItem(column)
                if head is not None:
                    found.add(head.text())
                for row in range(table.rowCount()):
                    item = table.item(row, column)
                    if item is not None:
                        found.add(item.text())
        for edit in root.findChildren(QTextEdit) + root.findChildren(QPlainTextEdit):
            found.update(line for line in edit.toPlainText().splitlines() if line.strip())
        return found

    def _shared(build, qtbot) -> list[str]:
        shown = {}
        for code in ("de", "en"):
            texte.set_language(code)
            try:
                widget = build()
                qtbot.addWidget(widget)
                shown[code] = _lettered(_visible_texts(widget) | _table_texts(widget))
            finally:
                texte.set_language("de")
        same = (shown["de"] & shown["en"]) - NAMES
        return sorted(text for text in same if "github.com" not in text and "digitalroots.de" not in text)

    def test_yes_and_no_follow_the_language(qtbot):
        from PyQt6.QtWidgets import QMessageBox
        from kira.ui._dialog_style import apply_light_theme

        def labels():
            box = QMessageBox()
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            apply_light_theme(box)
            qtbot.addWidget(box)
            return [box.button(QMessageBox.StandardButton.Yes).text(), box.button(QMessageBox.StandardButton.No).text()]

        assert labels() == ["Ja", "Nein"]
        texte.set_language("en")
        try:
            assert labels() == ["Yes", "No"]
        finally:
            texte.set_language("de")

    def test_settings_share_only_names_between_the_languages(qtbot, tmp_path, monkeypatch):
        import kira.ui.settings_dialog as sd
        from kira.config import Config
        monkeypatch.setattr(sd, "load_config", lambda: Config())
        monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
        monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
        assert _shared(sd.SettingsDialog, qtbot) == []

    def test_about_shares_only_names_between_the_languages(qtbot, monkeypatch):
        import kira.config
        from kira.ui.about_dialog import AboutDialog
        monkeypatch.setattr(kira.config, "load_config", lambda: kira.config.Config())
        shared = _shared(AboutDialog, qtbot)
        technical = ("faster-whisper", "(ollama)", "Version ")
        assert [text for text in shared if not any(mark in text for mark in technical)] == []

    def test_setup_hint_shares_only_names_between_the_languages(qtbot):
        from kira.ui.setup_hint_dialog import SetupHintDialog
        assert _shared(lambda: SetupHintDialog(mic_ok=False, ollama_ok=False), qtbot) == []

    def test_learned_words_share_only_names_between_the_languages(qtbot, tmp_path):
        from kira.ui.learned_words_dialog import LearnedWordsDialog
        from tests.test_learned_words_dialog import FakeService, _lexicon
        folders = iter((tmp_path / "de", tmp_path / "en"))

        def build():
            folder = next(folders)
            folder.mkdir()
            return LearnedWordsDialog(FakeService(_lexicon(folder)))

        assert _shared(build, qtbot) == []

    def test_correction_rate_uses_a_point_in_english(english):
        from kira.ui.learned_words_dialog import format_rate
        assert format_rate((3, 176)) == "1.7 % (3 of 176)"

    def test_first_run_wizard_reports_in_both_languages(qtbot, tmp_path):
        from kira.setup_wizard import DownloadPage

        def build():
            page = DownloadPage(tmp_path / "whisper", tmp_path / "OllamaSetup.exe")
            page._on_whisper_finished(tmp_path / "faster-whisper-large-v3")
            page._on_ollama_error("kaputt")
            page._mark_aborted()
            return page

        shared = _shared(build, qtbot)
        assert [text for text in shared if not text.startswith(("[Whisper] OK", "[Ollama", "[Pipeline"))] == []

    def test_first_run_wizard_status_words_are_english(qtbot, tmp_path, english):
        from kira.setup_wizard import DownloadPage
        page = DownloadPage(tmp_path / "whisper", tmp_path / "OllamaSetup.exe")
        qtbot.addWidget(page)
        page._on_whisper_finished(tmp_path / "faster-whisper-large-v3")
        page._on_ollama_error("kaputt")
        page._mark_aborted()
        texts = _visible_texts(page) | _table_texts(page)
        assert "Whisper: done (faster-whisper-large-v3)" in texts
        assert "Ollama: ERROR" in texts
        assert "Gemma: cancelled" in texts
        assert any(text.startswith("[Ollama ERROR]") for text in texts)

    def test_english_lookups_find_their_texts(qtbot, tmp_path, monkeypatch, english):
        import kira.ui.settings_dialog as sd
        from kira.config import Config
        from kira.setup_wizard import SetupWizard
        from kira.ui.about_dialog import AboutDialog
        from kira.ui.tray_win import KiraTray

        class Recording(dict):
            missed: list[str] = []

            def get(self, key, default=None):
                if key not in self:
                    self.missed.append(key)
                return super().get(key, default)

        table = Recording(EN)
        table.missed = []
        monkeypatch.setattr(texte, "EN", table)
        monkeypatch.setattr(sd, "load_config", lambda: Config())
        monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
        monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
        for build in (sd.SettingsDialog, AboutDialog, lambda: SetupWizard(tmp_path / "whisper", tmp_path / "OllamaSetup.exe")):
            qtbot.addWidget(build())
        KiraTray(on_quit=lambda: None)._build_menu()
        assert sorted(_lettered(table.missed) - NAMES) == []

    def _german_left(texts: set[str], allowed: set[str] = frozenset()) -> list[str]:
        left = []
        for text in sorted(texts - set(allowed)):
            words = set(re.findall(r"[a-zäöüß]+", text.lower()))
            if text in EN or (len(words) >= 3 and words & DEUTSCHE_WOERTER):
                left.append(text)
        return left

    @pytest.fixture
    def settings(qtbot, tmp_path, monkeypatch, english):
        import kira.ui.settings_dialog as sd
        from kira.config import Config
        monkeypatch.setattr(sd, "load_config", lambda: Config())
        monkeypatch.setattr(sd, "default_config_path", lambda: tmp_path / "config.yaml")
        monkeypatch.setattr(sd.SettingsDialog, "_query_input_devices", lambda self: [(3, "USB Microphone")])
        dialog = sd.SettingsDialog()
        qtbot.addWidget(dialog)
        return dialog

    def test_settings_show_no_german_in_english(settings):
        assert _german_left(_visible_texts(settings), allowed={"Deutsch"}) == []

    def test_settings_tabs_are_english(settings):
        assert [tab.text() for tab in settings._tabs] == [
            "Microphone", "Clean-up", "Keys", "Indicator", "Sound", "Learning", "About",
        ]

    def test_interface_language_names_itself_in_its_own_language(settings):
        labels = [settings._ui_language.itemText(i) for i in range(settings._ui_language.count())]
        assert labels == ["Same as Windows", "Deutsch", "English"]

    def test_dictation_languages_are_named_in_english(settings):
        labels = [settings._language.itemText(i) for i in range(settings._language.count())]
        assert labels == [
            "Detect automatically", "German", "English", "French", "Italian", "Dutch", "Polish", "Portuguese", "Spanish",
        ]

    def test_indicator_styles_are_named_in_english(settings):
        labels = [settings._hud_style.itemText(i) for i in range(settings._hud_style.count())]
        assert "Christmas (Winter Night)" in labels
        assert "Weihnachten (Winternacht)" not in labels

    @pytest.mark.parametrize("as_help", [True, False])
    def test_welcome_and_guide_show_no_german_in_english(qtbot, english, as_help):
        import kira.ui.welcome_dialog as welcome
        dialog = welcome.WelcomeDialog(as_help=as_help)
        qtbot.addWidget(dialog)
        assert _german_left(_visible_texts(dialog)) == []
        from PyQt6.QtWidgets import QTextBrowser
        html = dialog.findChild(QTextBrowser).toPlainText()
        assert "local speech-to-text helper" in html
        assert "Sprache-zu-Text" not in html

    def test_german_guide_stays_german():
        import kira.ui.welcome_dialog as welcome
        assert welcome._guide_html() is welcome._GUIDE_HTML

    def test_both_guides_have_the_same_shape():
        import kira.ui.welcome_dialog as welcome
        for tag in ("<h3>", "<code>", "<li>", "<pre>"):
            assert welcome._GUIDE_HTML.count(tag) == welcome._GUIDE_HTML_EN.count(tag), tag
        assert welcome._NEWS_HTML.count("{version}") == welcome._NEWS_HTML_EN.count("{version}") == 1

    def test_about_shows_no_german_in_english(qtbot, english):
        from kira.ui.about_dialog import AboutDialog
        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        texts = _visible_texts(dialog)
        assert _german_left(texts) == []
        assert any(text.startswith("Hold ") for text in texts)

    def test_setup_hint_shows_no_german_in_english(qtbot, english):
        from kira.ui.setup_hint_dialog import SetupHintDialog
        dialog = SetupHintDialog(mic_ok=False, ollama_ok=False)
        qtbot.addWidget(dialog)
        assert _german_left(_visible_texts(dialog)) == []

    def test_first_run_wizard_shows_no_german_in_english(qtbot, tmp_path, english):
        from kira.setup_wizard import SetupWizard
        wizard = SetupWizard(tmp_path / "whisper", tmp_path / "OllamaSetup.exe")
        qtbot.addWidget(wizard)
        assert _german_left(_visible_texts(wizard)) == []

    def test_learned_words_show_no_german_in_english(qtbot, tmp_path, english):
        from kira.ui.learned_words_dialog import LearnedWordsDialog
        from tests.test_learned_words_dialog import FakeService, _lexicon
        dialog = LearnedWordsDialog(FakeService(_lexicon(tmp_path)))
        qtbot.addWidget(dialog)
        assert _german_left(_visible_texts(dialog)) == []

    def test_tray_menu_is_english_and_keeps_its_icons(english):
        from kira.ui.tray_win import KiraTray, _menu_icon_kind
        tray = KiraTray(on_quit=lambda: None)
        labels = [str(item.text) for item in tray._build_menu().items if getattr(item, "text", None)]
        assert "Settings…" in labels
        assert "Quit" in labels
        assert [label for label in labels if label in EN] == []
        assert _menu_icon_kind("Settings…") == "gear"
        assert _menu_icon_kind("Install update to v0.6.0…") == "retry"
        assert _menu_icon_kind("Learned Words (2 new)…") == "wand"

    def test_tray_menu_icons_keep_working_in_german():
        from kira.ui.tray_win import _menu_icon_kind
        assert _menu_icon_kind("Einstellungen…") == "gear"
        assert _menu_icon_kind("Update auf v0.6.0 installieren…") == "retry"
        assert _menu_icon_kind("Gelernte Wörter (2 neu)…") == "wand"

    def test_every_menu_entry_with_an_icon_has_an_english_name():
        from kira.ui.tray_win import _MENU_ICONS
        assert [label for label in _MENU_ICONS if label not in EN] == []
