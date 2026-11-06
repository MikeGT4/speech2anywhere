from __future__ import annotations
import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton

from kira import UPDATE_REPO, __version__
from kira.config import effective_hotkey
from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme
from kira.texte import tr

log = logging.getLogger(__name__)
from kira._resources import assets_dir as _assets_dir  # noqa: E402
_ASSETS = _assets_dir()


def _safe_load_config():
    try:
        from kira.config import load_config
        return load_config()
    except Exception:
        from kira.config import Config
        return Config()


def _value(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("comicValue")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class AboutDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(tr("Über Speech2Anywhere"))
        icon_path = _ASSETS / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setModal(True)
        self.setMinimumWidth(760)
        apply_light_theme(self)
        body = comic.dialog_frame(self, tr("Über"))

        cfg = _safe_load_config()
        on_processor = cfg.whisper.device == "cpu"
        whisper_spec = cfg.whisper.cpu_model if on_processor else cfg.whisper.model
        whisper_model_name = Path(whisper_spec).name or whisper_spec
        polish_model = cfg.styler.fast_model if on_processor or cfg.styler.fast_mode else cfg.styler.model
        mic_label = (
            str(cfg.audio.input_device)
            if cfg.audio.input_device is not None
            else tr("Windows-Standard")
        )
        body.setSpacing(12)
        card = comic.ComicCard(f"Version {__version__}", comic.mascot_pixmap(32), row_padding=5)
        device_name = "CPU" if on_processor else "GPU"
        card.add_row(tr("Spracherkennung"), "", _value(f"faster-whisper · {whisper_model_name} · {device_name}"))
        polish_text = f"{polish_model} ({cfg.styler.provider})" if cfg.styler.enabled else tr("aus")
        card.add_row(tr("Politur"), "", _value(polish_text))
        key_use = tr("{} drücken, noch einmal zum Beenden") if cfg.hotkey.mode == "toggle" else tr("{} halten")
        card.add_row(tr("Taste"), "", _value(key_use.format(effective_hotkey(cfg.hotkey.combo).upper())))
        card.add_row(tr("Mikrofon"), "", _value(mic_label))
        source = _value(
            f"<a href='https://github.com/{UPDATE_REPO}' style='color: {comic.INK};'>"
            f"github.com/{UPDATE_REPO}</a>"
        )
        source.setOpenExternalLinks(True)
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        card.add_row(tr("Quelle"), "", source)
        body.addWidget(card)
        body.addWidget(comic.HintBubble([
            tr("Speech2Anywhere von"), comic.brand_logo(20), tr("· © 2026 Mike Pollow, Personal-Use-Lizenz"),
        ]))
        body.addStretch()

        close_btn = QPushButton(tr("Schließen"))
        close_btn.setObjectName("comicPrimary")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        body.addLayout(comic.footer_row(None, close_btn))
