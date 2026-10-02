from __future__ import annotations
import logging
import subprocess

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QProgressDialog, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from kira.ui import _comic as comic
from kira.ui._dialog_style import (
    apply_light_theme,
    light_critical,
    light_information,
    light_warning,
)

from kira import __version__, UPDATE_REPO
from kira.config import default_config_path, effective_hotkey, load_config
from kira.hotkey_win import SUPPORTED_COMBOS
from kira.config_writer import update_scalars
from kira.ui.hud import STYLE_LABELS

log = logging.getLogger(__name__)
from kira._resources import assets_dir as _assets_dir  # noqa: E402
_ASSETS = _assets_dir()

_DEVICE_DEFAULT_LABEL = "Windows-Standard (automatisch)"

_UNCENSORED_MODEL = "huihui_ai/Qwen3.6-abliterated:27b"

_LANGUAGES = (("auto", "Automatisch erkennen"), ("de", "Deutsch"), ("en", "Englisch"))

_GAIN_SLIDER_MAX = 50


def _ollama_client():
    import ollama
    from kira.ollama_host import client_host
    host = client_host()
    return ollama if host is None else ollama.Client(host=host)


def _ollama_model_installed(model: str) -> bool:
    try:
        result = _ollama_client().list()
        models = getattr(result, "models", None)
        if models is None and isinstance(result, dict):
            models = result.get("models", [])
        names: list[str] = []
        for m in (models or []):
            name = (
                getattr(m, "model", None)
                or getattr(m, "name", None)
                or (m.get("model") if isinstance(m, dict) else None)
                or (m.get("name") if isinstance(m, dict) else None)
                or ""
            )
            if name:
                names.append(str(name))
        if model in names:
            return True
        return any(n.startswith(model) for n in names)
    except Exception:
        log.exception("ollama.list() failed during model-installed check")
        return False


_orphan_pull_threads: list = []


_PROGRESS_SCALE = 1000


def _progress_scale(completed: int, total: int) -> tuple[int, int]:
    if total <= 0:
        return (0, 0)
    safe = max(0, min(completed, total))
    return (_PROGRESS_SCALE, round(safe / total * _PROGRESS_SCALE))


class _PullWorker(QObject):
    progress = pyqtSignal(str, 'qint64', 'qint64')
    finished = pyqtSignal(bool, str)

    def __init__(self, model_name: str) -> None:
        super().__init__()
        self._model = model_name
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            import ollama
        except Exception as e:
            self.finished.emit(False, f"ollama-Library nicht verfügbar: {e}")
            return
        try:
            for event in _ollama_client().pull(self._model, stream=True):
                if self._cancelled:
                    self.finished.emit(False, "Abgebrochen.")
                    return
                status = getattr(event, "status", None) or (
                    event.get("status", "") if isinstance(event, dict) else ""
                )
                completed = (
                    getattr(event, "completed", None)
                    or (event.get("completed", 0) if isinstance(event, dict) else 0)
                    or 0
                )
                total = (
                    getattr(event, "total", None)
                    or (event.get("total", 0) if isinstance(event, dict) else 0)
                    or 0
                )
                self.progress.emit(str(status), int(completed), int(total))
            if self._cancelled:
                self.finished.emit(False, "Abgebrochen.")
                return
            self.finished.emit(True, f"{self._model} ist auf dem aktuellen Stand.")
        except Exception as e:
            log.exception("ollama.pull failed")
            self.finished.emit(False, f"Das Modell-Update hat nicht geklappt: {e}")


class _GpuCheckWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, whisper_model: str, polish_model: str) -> None:
        super().__init__()
        self._whisper_model = whisper_model
        self._polish_model = polish_model

    def run(self) -> None:
        try:
            from kira.gpu_check import assess
            result = assess(
                whisper_model=self._whisper_model,
                polish_model=self._polish_model,
            )
            self.finished.emit(result)
        except Exception as exc:
            log.exception("GPU-Check fehlgeschlagen")
            self.failed.emit(str(exc))


_MINIMAL_CONFIG = """\
# Speech2Anywhere config, written by the settings dialog.
# Open this file directly for advanced fields (initial_prompt,
# context_modes, whisper.model path, replacements, styler.modes).
audio:
  input_gain: 1.0
  input_device: null
whisper:
  language: auto
styler:
  model: gemma4:12b
  timeout_seconds: 30.0
injector:
  restore_clipboard_after_ms: 500
hotkey:
  combo: f8
  edit_combo: f9
"""


class SettingsDialog(QDialog):
    _PAGE_TITLES = ("Mikrofon", "Politur", "Tasten", "Anzeige", "Lernen", "Über")

    def __init__(self, open_learned_words=None) -> None:
        super().__init__()
        self.setWindowTitle("Speech2Anywhere: Einstellungen")
        icon_path = _ASSETS / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setModal(True)
        apply_light_theme(self)
        self.setMinimumWidth(840)

        self._cfg = load_config()
        self._cfg_path = default_config_path()
        self._pull_thread: QThread | None = None
        self._pull_worker: _PullWorker | None = None
        self._gpu_thread: QThread | None = None
        self._gpu_worker: _GpuCheckWorker | None = None
        self._open_learned_words = open_learned_words
        self._mascot = comic.mascot_pixmap(32)

        self._pages = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        body = comic.DotBackground()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(30, 26, 30, 18)
        body_lay.setSpacing(16)
        body_lay.addWidget(self._pages, 1)
        body_lay.addLayout(self._build_footer())
        root.addWidget(body, 1)

        for build in (self._page_mikrofon, self._page_politur, self._page_tasten,
                      self._page_anzeige, self._page_lernen, self._page_ueber):
            self._pages.addWidget(build())
        self._tabs[0].setChecked(True)
        self._pages.setCurrentIndex(0)

    def _build_header(self) -> QWidget:
        header = comic.DarkHeader()
        lay = QVBoxLayout(header)
        lay.setContentsMargins(28, 14, 28, 0)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(16)
        logo = QLabel()
        pix = comic.mascot_pixmap(64)
        if pix is not None:
            logo.setPixmap(pix)
        top.addWidget(logo)
        top.addWidget(comic.Wordmark("dunkel", 54), 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch()
        lay.addLayout(top)

        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tabs: list[comic.BubbleTab] = []
        for index, title in enumerate(self._PAGE_TITLES):
            tab = comic.BubbleTab(title)
            self._tab_group.addButton(tab, index)
            tabs.addWidget(tab, 0, Qt.AlignmentFlag.AlignBottom)
            self._tabs.append(tab)
        tabs.addStretch()
        self._tab_group.idClicked.connect(self._pages.setCurrentIndex)
        lay.addLayout(tabs)
        return header

    def _build_footer(self) -> QHBoxLayout:
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Speichern")
        save.setObjectName("comicPrimary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        return comic.footer_row("Fast alles wirkt nach einem kurzen Neustart.", cancel, save)

    def _card(self, title: str) -> comic.ComicCard:
        return comic.ComicCard(title, self._mascot)

    @staticmethod
    def _page(card: comic.ComicCard, hint: QWidget | None) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(card)
        if hint is not None:
            indent = QHBoxLayout()
            indent.setContentsMargins(8, 0, 0, 0)
            indent.addWidget(hint)
            lay.addLayout(indent)
        lay.addStretch()
        return page

    @staticmethod
    def _left(widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(widget)
        row.addStretch()
        return row

    def _page_mikrofon(self) -> QWidget:
        card = self._card("Mikrofon")

        mic_box = QVBoxLayout()
        mic_box.setSpacing(6)
        mic_row = QHBoxLayout()
        mic_row.setSpacing(10)
        self._device = comic.style_combo(QComboBox())
        self._device.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self._device.setMinimumContentsLength(16)
        self._device.setToolTip(
            "Mikrofon-Auswahl. Gespeichert wird der Name (Substring-Match),\n"
            "auch nach USB-Neustecken wird derselbe Eintrag wiedererkannt,\n"
            "selbst wenn der PortAudio-Index sich ändert.\n"
            "'Windows-Standard' lässt Windows entscheiden und kann durch\n"
            "Noise-Cancel-Filter (ASUS, Nahimic) laufen, die Whisper stören."
        )
        mic_row.addWidget(self._device, 1)
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.setToolTip(
            "Geräte neu abfragen, wenn ein Mikrofon eingesteckt wurde,\n"
            "während dieses Fenster offen ist."
        )
        refresh_btn.clicked.connect(self._refresh_devices)
        mic_row.addWidget(refresh_btn)
        mic_box.addLayout(mic_row)
        self._device_hint = QLabel("")
        self._device_hint.setObjectName("comicWarn")
        self._device_hint.setWordWrap(True)
        self._device_hint.setVisible(False)
        mic_box.addWidget(self._device_hint)
        self._populate_device_combo(self._cfg.audio.input_device)
        card.add_row("Eingabegerät", "Dieses Mikrofon hört zu.", mic_box)

        gain_row = QHBoxLayout()
        gain_row.setSpacing(14)
        self._gain_slider = comic.ComicSlider()
        self._gain_slider.setRange(1, _GAIN_SLIDER_MAX)
        self._gain = QDoubleSpinBox()
        self._gain.setObjectName("comicChip")
        self._gain.setRange(0.1, 200.0)
        self._gain.setSingleStep(0.1)
        self._gain.setDecimals(1)
        self._gain.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self._gain.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gain.setFixedWidth(76)
        self._gain.setToolTip(
            "Software-Verstärkung auf das rohe Mikrofonsignal.\n"
            "Zielbereich: peak 0,3 bis 0,9, rms 0,05 bis 0,15 (siehe Protokoll).\n"
            "Der Regler reicht bis 5,0, das Zahlenfeld bis 200."
        )
        self._gain.valueChanged.connect(self._gain_to_slider)
        self._gain_slider.valueChanged.connect(self._slider_to_gain)
        self._gain.setValue(self._cfg.audio.input_gain)
        self._gain_to_slider(self._gain.value())
        gain_row.addWidget(self._gain_slider, 1)
        gain_row.addWidget(self._gain)
        card.add_row("Verstärkung", "Bei leiser Stimme höher stellen.", gain_row)

        self._language = comic.style_combo(QComboBox())
        for code, label in _LANGUAGES:
            self._language.addItem(label, userData=code)
        self._language.setCurrentIndex(max(0, self._language.findData(self._cfg.whisper.language)))
        self._language.setToolTip(
            "Automatisch: Whisper erkennt die Sprache je Aufnahme.\n"
            "Fest eingestellt ist die Erkennung bei einsprachigem Diktat etwas genauer."
        )
        card.add_row("Sprache", "Sprache, in der du diktierst.", self._language)

        key = effective_hotkey(self._cfg.hotkey.combo).upper()
        hint = comic.HintBubble(
            ["Halte", comic.Keycap(key), "gedrückt und sprich, der Text erscheint am Cursor."],
        )
        return self._page(card, hint)

    def _gain_to_slider(self, value: float) -> None:
        self._gain_slider.blockSignals(True)
        self._gain_slider.setValue(max(1, min(_GAIN_SLIDER_MAX, round(value * 10))))
        self._gain_slider.blockSignals(False)

    def _slider_to_gain(self, position: int) -> None:
        self._gain.setValue(position / 10)

    def _page_politur(self) -> QWidget:
        card = self._card("Politur")

        model_row = QHBoxLayout()
        model_row.setSpacing(10)
        self._styler_model = QLineEdit()
        self._styler_model.setText(self._cfg.styler.model)
        self._styler_model.setPlaceholderText("z. B. gemma4:12b, qwen3:8b")
        model_row.addWidget(self._styler_model, 1)
        update_btn = QPushButton("Aktualisieren")
        update_btn.setToolTip(
            "Lädt das eingetragene Modell per ollama pull neu,\n"
            "etwa wenn die Ollama-Bibliothek eine neue Fassung hat."
        )
        update_btn.clicked.connect(self._update_polish_model)
        model_row.addWidget(update_btn)
        card.add_row("Modell", "Setzt Satzzeichen, schreibt groß und fegt die Ähms raus.", model_row)

        self._fast_mode = comic.ToggleSwitch()
        self._fast_mode.setChecked(self._cfg.styler.fast_mode)
        self._fast_mode.setToolTip(
            "Poliert mit dem schnellen Modell statt mit dem Qualitätsmodell.\n"
            "Sinnvoll, wenn der Grafikspeicher knapp ist (Browser, Outlook, RDP\n"
            "gleichzeitig offen); sonst rutscht das große Modell teils auf die CPU.\n\n"
            "Satzzeichen, Großschreibung, Füllwörter: praktisch gleich.\n"
            "Bearbeiten (F9) und lange Texte: etwas schwächer.\n\n"
            "Beim ersten Einschalten wird das Modell bei Bedarf geladen (~3 GB).\n"
            "Einträge in styler.modes haben weiter Vorrang."
        )
        card.add_row(
            "Schneller Modus",
            f"{self._cfg.styler.fast_model}, spart Grafikspeicher.",
            self._fast_mode,
        )

        self._styler_timeout = QDoubleSpinBox()
        self._styler_timeout.setRange(1.0, 120.0)
        self._styler_timeout.setSingleStep(1.0)
        self._styler_timeout.setDecimals(1)
        self._styler_timeout.setSuffix(" s")
        self._styler_timeout.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self._styler_timeout.setFixedWidth(120)
        self._styler_timeout.setValue(self._cfg.styler.timeout_seconds)
        self._styler_timeout.setToolTip(
            "Zeitlimit für die Politur. 30 s reichen für große Modelle beim\n"
            "Kaltstart, 5 s für warm gehaltene kleine Modelle."
        )
        card.add_row("Zeitlimit", "Dauert es länger, kommt der Text unpoliert.", self._styler_timeout)

        uncensored_row = QHBoxLayout()
        uncensored_row.setSpacing(12)
        uncensored_btn = QPushButton("Laden…")
        uncensored_btn.setToolTip(
            f"Lädt das unzensierte Modell ({_UNCENSORED_MODEL}, ~17 GB)\n"
            "per ollama pull und trägt es als Qualitätsmodell ein. Vorher läuft\n"
            "ein GPU-Check: das 27B-Modell braucht ~16 GB Grafikspeicher und\n"
            "passt auf 16-GB-Karten nicht neben Whisper."
        )
        uncensored_btn.clicked.connect(self._offer_uncensored_model)
        uncensored_row.addWidget(uncensored_btn)
        badge = QLabel("18+")
        badge.setObjectName("comicBadge")
        badge.setFixedHeight(24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        uncensored_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        uncensored_row.addStretch()
        card.add_row("Unzensiert", "Ohne Inhaltsfilter, rund 17 GB.", uncensored_row)
        warning = QLabel(
            "Die Inhaltsfilter des Modells sind entfernt. Es lehnt keine "
            "Eingaben ab und gibt ungefilterte Ausgaben zurück."
        )
        warning.setObjectName("comicWarn")
        warning.setWordWrap(True)
        warning.setContentsMargins(0, 0, 0, 10)
        card.add_note(warning)

        hint = comic.HintBubble([
            "Der schnelle Modus poliert fast gleich gut, nur das Bearbeiten und lange Texte werden etwas schwächer.",
        ])
        return self._page(card, hint)

    def _page_tasten(self) -> QWidget:
        card = self._card("Tasten")

        self._hotkey = QLineEdit()
        self._hotkey.setObjectName("comicKey")
        self._hotkey.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hotkey.setFixedWidth(200)
        self._hotkey.setText(effective_hotkey(self._cfg.hotkey.combo))
        self._hotkey.setPlaceholderText("f8")
        self._hotkey.setToolTip("Diktat-Taste: f8 oder f9. Wirkt nach einem kurzen Neustart.")
        card.add_row("Diktat", "Gedrückt halten und sprechen.", self._hotkey)

        edit_enabled = self._cfg.hotkey.edit_combo is not None
        self._edit_enabled = comic.ToggleSwitch()
        self._edit_enabled.setChecked(edit_enabled)
        self._edit_enabled.setToolTip(
            "Text in der App markieren, die Bearbeiten-Taste halten, einen Befehl\n"
            "sprechen („mach das förmlich“, „übersetz ins Englische“), loslassen:\n"
            "das Sprachmodell überarbeitet die Markierung. Wirkt nach einem kurzen Neustart."
        )
        card.add_row("Bearbeiten", "Markierten Text per Zuruf umschreiben.", self._edit_enabled)

        self._edit_hotkey = QLineEdit()
        self._edit_hotkey.setObjectName("comicKey")
        self._edit_hotkey.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._edit_hotkey.setFixedWidth(200)
        self._edit_hotkey.setText(self._cfg.hotkey.edit_combo or "f9")
        self._edit_hotkey.setPlaceholderText("f9")
        self._edit_hotkey.setEnabled(edit_enabled)
        self._edit_hotkey.setToolTip("Taste zum Bearbeiten: f8 oder f9 (Standard: f9).")
        self._edit_enabled.toggled.connect(self._on_edit_toggle)
        card.add_row("Bearbeiten-Taste", "Halten, sagen, was anders werden soll.", self._edit_hotkey)

        self._restore_ms = QSpinBox()
        self._restore_ms.setRange(100, 5000)
        self._restore_ms.setSingleStep(100)
        self._restore_ms.setSuffix(" ms")
        self._restore_ms.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._restore_ms.setFixedWidth(140)
        self._restore_ms.setValue(self._cfg.injector.restore_clipboard_after_ms)
        self._restore_ms.setToolTip(
            "Mindestwartezeit, bevor die Zwischenablage wiederhergestellt wird.\n"
            "Lange Diktate verlängern sie selbst (~2 ms je Zeichen ab 80 Zeichen)."
        )
        card.add_row("Zwischenablage", "So lange wartet sie, bevor ihr alter Inhalt zurückkommt.", self._restore_ms)

        return self._page(card, comic.HintBubble(["Neue Tasten wirken nach einem kurzen Neustart."]))

    def _on_edit_toggle(self, checked: bool) -> None:
        self._edit_hotkey.setEnabled(checked)
        if checked and not self._edit_hotkey.text().strip():
            self._edit_hotkey.setText("f9")

    def _page_anzeige(self) -> QWidget:
        card = self._card("Aufnahme-Anzeige")
        self._hud_style = comic.style_combo(QComboBox())
        for key, label in STYLE_LABELS.items():
            self._hud_style.addItem(label, userData=key)
        index = self._hud_style.findData(self._cfg.ui.hud_style)
        self._hud_style.setCurrentIndex(max(0, index))
        self._hud_style.setToolTip(
            "Wie die Anzeige am Mauszeiger aussieht, solange die Diktat-Taste\n"
            "gehalten wird."
        )
        card.add_row("Stil", "So sieht die Anzeige beim Diktieren aus.", self._hud_style)
        self._hud_live_words = comic.ToggleSwitch()
        self._hud_live_words.setChecked(self._cfg.ui.hud_live_words)
        self._hud_live_words.setToolTip(
            "Im Stil „Comic (Bla-Bla)“ fliegen beim Sprechen Fetzen der erkannten Wörter.\n"
            "Sie sind am Bildschirm zu sehen, auch bei einer Bildschirmfreigabe."
        )
        card.add_row("Wortfetzen", "Fetzen deiner Wörter beim Sprechen.", self._hud_live_words)
        hint = comic.HintBubble([
            "Wirkt schon beim nächsten Diktat. Die Größe stellst du in der Rohconfig ein (ui.hud_scale).",
        ])
        return self._page(card, hint)

    def _page_lernen(self) -> QWidget:
        card = self._card("Lernen")
        self._learning_enabled = comic.ToggleSwitch()
        self._learning_enabled.setChecked(self._cfg.learning.enabled)
        self._learning_enabled.setToolTip(
            "Merkt sich Wörter, die du nach dem Diktieren korrigierst. Legt nach einem kurzen Neustart los."
        )
        card.add_row(
            "Aus Korrekturen lernen",
            "Merkt sich korrigierte Wörter.",
            self._learning_enabled,
        )
        if self._open_learned_words is not None:
            learned_button = QPushButton("Anzeigen…")
            learned_button.clicked.connect(self._open_learned_words)
            card.add_row("Gelernte Wörter", "Liste ansehen und Einträge freigeben.", self._left(learned_button))
        return self._page(card, comic.HintBubble(["Nach dem nächsten Neustart legt das Lernen los."]))

    def _page_ueber(self) -> QWidget:
        card = self._card("Über")
        version = QLabel(f"v{__version__}")
        version.setObjectName("comicValue")
        card.add_row("Version", "", version)
        repo = QLabel(
            f"<a href='https://github.com/{UPDATE_REPO}' style='color: {comic.INK};'>"
            f"github.com/{UPDATE_REPO}</a>"
        )
        repo.setObjectName("comicValue")
        repo.setOpenExternalLinks(True)
        card.add_row("Quelle", "", repo)

        tools = QHBoxLayout()
        tools.setSpacing(10)
        help_btn = QPushButton("Anleitung…")
        help_btn.setToolTip("Bedienungsanleitung: Diktat, Bearbeiten, Datei-Transkription, Modi, Updates.")
        help_btn.clicked.connect(self._open_help_from_settings)
        tools.addWidget(help_btn)
        gpu_btn = QPushButton("GPU prüfen")
        gpu_btn.setToolTip(
            "Prüft, ob der Grafikspeicher für Whisper und das eingetragene\n"
            "Politur-Modell reicht: Karte, Speicher, geschätzter Bedarf, Reserve."
        )
        gpu_btn.clicked.connect(self._run_gpu_check)
        tools.addWidget(gpu_btn)
        update_btn = QPushButton("Updates suchen…")
        update_btn.setToolTip(
            f"Holt die neueste Version von github.com/{UPDATE_REPO}, prüft die\n"
            "SHA256-Summen und startet das Setup. Speech2Anywhere beendet sich dafür kurz."
        )
        update_btn.clicked.connect(self._run_update_check)
        tools.addWidget(update_btn)
        tools.addStretch()
        card.add_row("Werkzeuge", "Hilfe, Grafikspeicher, neue Version.", tools)

        raw_btn = QPushButton("Rohconfig öffnen…")
        raw_btn.setToolTip("Öffnet config.yaml im Editor, für Felder, die hier fehlen.")
        raw_btn.clicked.connect(self._open_raw)
        card.add_row("Rohconfig", "Weitere Felder direkt in der config.yaml.", self._left(raw_btn))

        hint = comic.HintBubble([
            "Speech2Anywhere von", comic.brand_logo(20), "· Einstellungen in %APPDATA%\\Kira\\config.yaml",
        ])
        return self._page(card, hint)

    @staticmethod
    def _resolve_edit_combo(enabled: bool, text: str) -> str | None:
        if not enabled:
            return None
        return text.strip() or None

    @staticmethod
    def _uncensored_gpu_blocks(status: str) -> bool:
        return status in ("insufficient", "tight")

    def _run_update_check(self) -> None:
        from PyQt6.QtCore import QCoreApplication
        from kira.ui._update_runner import run_update_flow

        def request_quit() -> None:
            inst = QCoreApplication.instance()
            if inst is not None:
                inst.quit()

        run_update_flow(parent=self, on_quit_request=request_quit)

    def _open_help_from_settings(self) -> None:
        from kira.ui.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(as_help=True)
        dlg.setParent(self, dlg.windowFlags())
        getattr(dlg, "exec")()

    def _run_gpu_check(self) -> None:
        polish_text = self._styler_model.text().strip() or self._cfg.styler.model
        whisper_model = self._cfg.whisper.model
        title = "Speech2Anywhere: GPU-Check"

        from kira.ui._gpu_scan_dialog import GpuScanDialog
        scan = GpuScanDialog(self)
        scan.start()

        thread = QThread(self)
        worker = _GpuCheckWorker(whisper_model, polish_text)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def on_finished(result) -> None:
            scan.finish()
            thread.quit()
            thread.wait()
            if result.status == "ok":
                light_information(self, title, result.message)
            elif result.status == "tight":
                light_warning(self, title, result.message)
            elif result.status == "insufficient":
                light_critical(self, title, result.message)
            else:
                light_warning(self, title, result.message)

        def on_failed(message: str) -> None:
            scan.finish()
            thread.quit()
            thread.wait()
            light_critical(
                self, title, f"Die GPU-Prüfung hat nicht geklappt:\n\n{message}",
            )

        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)
        thread.start()
        self._gpu_thread = thread
        self._gpu_worker = worker


    def _open_raw(self) -> None:
        self._cfg_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._cfg_path.exists():
            self._cfg_path.write_text(_MINIMAL_CONFIG, encoding="utf-8")
        try:
            subprocess.Popen(["notepad.exe", str(self._cfg_path)])
        except (OSError, FileNotFoundError) as exc:
            log.exception("notepad launch failed for %s", self._cfg_path)
            light_warning(
                self, "Speech2Anywhere",
                f"Der Editor wollte nicht starten ({exc}).\n\n"
                f"Öffne die Datei bitte von Hand:\n{self._cfg_path}",
            )

    def closeEvent(self, event) -> None:  # type: ignore[override]
        thread = self._pull_thread
        worker = self._pull_worker
        if worker is not None:
            worker.cancel()
        if thread is not None and thread.isRunning():
            if worker is not None:
                try:
                    worker.progress.disconnect()
                except (TypeError, RuntimeError):
                    pass
                try:
                    worker.finished.disconnect()
                except (TypeError, RuntimeError):
                    pass
            log.info(
                "Settings dialog closing while polish-pull running, "
                "cancel flagged, waiting up to 3s for clean exit",
            )
            thread.quit()
            if not thread.wait(3000):
                log.warning(
                    "polish-pull thread did not exit in 3s; orphaning "
                    "(no terminate, would risk a process-wide crash)",
                )
                _orphan_pull_threads.append((thread, worker))
        super().closeEvent(event)

    def _save(self) -> None:
        device_value = self._device.currentData()
        edit_enabled = self._edit_enabled.isChecked()
        if edit_enabled and not self._edit_hotkey.text().strip():
            light_warning(
                self, "Speech2Anywhere",
                "Trag noch eine Taste zum Bearbeiten ein oder schalte das Bearbeiten aus.",
            )
            return
        combo = self._hotkey.text().strip().lower()
        edit_combo = self._edit_hotkey.text().strip().lower()
        if combo not in SUPPORTED_COMBOS or (edit_enabled and edit_combo not in SUPPORTED_COMBOS):
            light_warning(
                self, "Speech2Anywhere",
                "Unter Windows gehen als Tasten F8 und F9. Trag bitte eine davon ein.",
            )
            return
        if edit_enabled and edit_combo == combo:
            light_warning(
                self, "Speech2Anywhere",
                "Diktat und Bearbeiten brauchen zwei verschiedene Tasten.",
            )
            return
        edit_hotkey_value = self._resolve_edit_combo(
            edit_enabled, self._edit_hotkey.text(),
        )
        new_fast_mode = self._fast_mode.isChecked()

        if new_fast_mode and not self._cfg.styler.fast_mode:
            fast_model = self._cfg.styler.fast_model
            if not _ollama_model_installed(fast_model):
                if not self._pull_blocking(fast_model):
                    self._fast_mode.setChecked(False)
                    return

        updates = {
            "audio.input_gain": float(self._gain.value()),
            "audio.input_device": device_value,
            "whisper.language": self._language.currentData(),
            "learning.enabled": self._learning_enabled.isChecked(),
            "styler.model": self._styler_model.text().strip(),
            "styler.fast_mode": new_fast_mode,
            "styler.timeout_seconds": float(self._styler_timeout.value()),
            "injector.restore_clipboard_after_ms": int(self._restore_ms.value()),
            "hotkey.combo": combo,
            "hotkey.edit_combo": edit_hotkey_value,
            "ui.hud_style": self._hud_style.currentData(),
            "ui.hud_live_words": self._hud_live_words.isChecked(),
        }

        self._cfg_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._cfg_path.exists():
            self._cfg_path.write_text(_MINIMAL_CONFIG, encoding="utf-8")

        try:
            current = self._cfg_path.read_text(encoding="utf-8")
            updated = update_scalars(current, updates)
            self._cfg_path.write_text(updated, encoding="utf-8")
            needs_restart = update_scalars(
                current, {key: value for key, value in updates.items() if not key.startswith("ui.")},
            ) != current
        except KeyError as e:
            light_warning(
                self, "Speech2Anywhere",
                f"Die config.yaml sieht anders aus als erwartet ({e}).\n\n"
                "Öffne sie einmal über „Rohconfig öffnen…“ und schau, ob alle Abschnitte "
                "da sind: audio, whisper, styler, injector, hotkey.",
            )
            return
        except Exception as e:
            log.exception("settings save failed")
            light_critical(self, "Speech2Anywhere", f"Speichern hat leider nicht geklappt: {e}")
            return

        if needs_restart:
            detail = "Fast alles wirkt nach einem kurzen Neustart: im Tray-Menü auf Beenden und Speech2Anywhere wieder starten."
        else:
            detail = "Das wirkt schon ab dem nächsten Diktat."
        light_information(self, "Speech2Anywhere", "Gespeichert!\n\n" + detail)
        self.accept()


    def _query_input_devices(self) -> list[tuple[int, str]]:
        try:
            import sounddevice as sd
            devices = list(sd.query_devices())
        except Exception:
            log.exception("sd.query_devices() failed in settings dialog")
            return []
        out: list[tuple[int, str]] = []
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                name = d.get("name") or ""
                if name:
                    out.append((i, name))
        return out

    def _populate_device_combo(
        self, initial_value: int | str | None,
    ) -> None:
        self._device.blockSignals(True)
        try:
            self._device.clear()
            self._device.addItem(_DEVICE_DEFAULT_LABEL, userData=None)
            devices = self._query_input_devices()
            for _idx, name in devices:
                self._device.addItem(name, userData=name)

            pos = self._match_initial(initial_value, devices)
            if pos is None:
                self._device.setCurrentIndex(0)
                if initial_value is None or not devices:
                    self._device_hint.setVisible(False)
                else:
                    self._device_hint.setText(
                        f"Dein Mikrofon „{initial_value}“ ist gerade nicht zu finden. "
                        "Steckt es? Dann auf Aktualisieren klicken. Sonst nimmt "
                        "Speech2Anywhere das Standardmikrofon von Windows."
                    )
                    self._device_hint.setVisible(True)
            else:
                self._device.setCurrentIndex(pos + 1)
                self._device_hint.setVisible(False)
        finally:
            self._device.blockSignals(False)

    @staticmethod
    def _match_initial(
        initial_value: int | str | None,
        devices: list[tuple[int, str]],
    ) -> int | None:
        if initial_value is None or not devices:
            return None
        if isinstance(initial_value, int):
            for pos, (idx, _name) in enumerate(devices):
                if idx == initial_value:
                    return pos
            return None
        needle = str(initial_value).lower()
        if not needle:
            return None
        for pos, (_idx, name) in enumerate(devices):
            if needle in name.lower():
                return pos
        return None

    def _refresh_devices(self) -> None:
        current = self._device.currentData()
        self._populate_device_combo(current)

    def _update_polish_model(self) -> None:
        model_name = self._styler_model.text().strip()
        if not model_name:
            light_warning(self, "Speech2Anywhere", "Trag zuerst ein Modell für die Politur ein.")
            return
        self._start_model_pull(model_name, "Speech2Anywhere: Modell-Update")

    def _start_model_pull(
        self,
        model_name: str,
        window_title: str,
        on_success=None,
        on_done=None,
    ) -> None:
        progress = QProgressDialog(
            f"Lade {model_name}…", "Abbrechen", 0, 0, self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setWindowTitle(window_title)
        progress.setMinimumDuration(0)
        apply_light_theme(progress)
        progress.show()

        thread = QThread(self)
        worker = _PullWorker(model_name)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def on_progress(status: str, completed: int, total: int) -> None:
            if total > 0:
                safe_completed = max(0, min(completed, total))
                maximum, value = _progress_scale(completed, total)
                progress.setMaximum(maximum)
                progress.setValue(value)
                pct = (safe_completed / total) * 100
                mb_done = safe_completed / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                progress.setLabelText(
                    f"{status}\n{mb_done:.1f} / {mb_total:.1f} MB ({pct:.0f}%)"
                )
            else:
                progress.setLabelText(status or f"Lade {model_name}…")

        def on_finished(success: bool, message: str) -> None:
            progress.close()
            thread.quit()
            thread.wait()
            if success:
                if on_success is not None:
                    on_success()
                else:
                    light_information(self, "Speech2Anywhere", message)
            else:
                if message != "Abgebrochen.":
                    light_critical(self, "Speech2Anywhere", message)
            if on_done is not None:
                on_done(success)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        progress.canceled.connect(worker.cancel)
        thread.start()
        self._pull_thread = thread
        self._pull_worker = worker

    def _pull_blocking(self, model_name: str) -> bool:
        from PyQt6.QtCore import QEventLoop
        loop = QEventLoop()
        state = {"success": False}

        def on_pull_done(success: bool) -> None:
            state["success"] = success
            loop.quit()

        self._start_model_pull(
            model_name,
            "Speech2Anywhere: Modell wird geladen",
            on_done=on_pull_done,
        )
        loop.exec()
        return state["success"]

    def _offer_uncensored_model(self) -> None:
        from kira.gpu_check import assess

        result = assess(
            whisper_model=self._cfg.whisper.model,
            polish_model=_UNCENSORED_MODEL,
        )
        if self._uncensored_gpu_blocks(result.status):
            severity = (
                QMessageBox.Icon.Critical
                if result.status == "insufficient"
                else QMessageBox.Icon.Warning
            )
            box = QMessageBox(self)
            box.setIcon(severity)
            box.setWindowTitle("Speech2Anywhere: Unzensiertes Modell")
            box.setText("Das unzensierte Modell ist für deine Grafikkarte zu groß. Trotzdem laden?")
            box.setInformativeText(
                f"Es braucht rund 16 GB Grafikspeicher ({_UNCENSORED_MODEL}). Reicht der nicht, "
                "lagert Ollama Teile auf den Prozessor aus, und die Politur dauert mehrere Sekunden "
                f"statt Sekundenbruchteilen.\n\n{result.message}"
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            box.setDefaultButton(QMessageBox.StandardButton.No)
            yes = box.button(QMessageBox.StandardButton.Yes)
            if yes is not None:
                yes.setText("Trotzdem laden")
            no = box.button(QMessageBox.StandardButton.No)
            if no is not None:
                no.setText("Abbrechen")
            apply_light_theme(box)
            if box.exec() != QMessageBox.StandardButton.Yes.value:
                return

        if _ollama_model_installed(_UNCENSORED_MODEL):
            self._apply_uncensored_model()
            return

        self._start_model_pull(
            _UNCENSORED_MODEL,
            "Speech2Anywhere: Unzensiertes Modell",
            on_success=self._apply_uncensored_model,
        )

    def _apply_uncensored_model(self) -> None:
        self._styler_model.setText(_UNCENSORED_MODEL)
        message = (
            "Das unzensierte Modell ist bereit und als "
            f"Qualitätsmodell eingetragen ({_UNCENSORED_MODEL}).\n\n"
            "Klick auf Speichern, dann ist es dabei."
        )
        if self._fast_mode.isChecked():
            message += (
                "\n\nAchtung: Der schnelle Modus ist an. Solange er "
                "läuft, poliert Speech2Anywhere mit dem schnellen Modell "
                f"({self._cfg.styler.fast_model}), und das unzensierte "
                "Qualitätsmodell hat Pause. Schalte den schnellen Modus aus, "
                "wenn das unzensierte Modell ran soll."
            )
        light_information(self, "Speech2Anywhere", message)
