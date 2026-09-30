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
        self.setWindowTitle("Über Speech2Anywhere")
        icon_path = _ASSETS / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setModal(True)
        self.setMinimumWidth(760)
        apply_light_theme(self)
        body = comic.dialog_frame(self, "Über")

        cfg = _safe_load_config()
        whisper_model_name = Path(cfg.whisper.model).name or cfg.whisper.model
        mic_label = (
            str(cfg.audio.input_device)
            if cfg.audio.input_device is not None
            else "Windows-Standard"
        )
        body.setSpacing(12)
        card = comic.ComicCard(f"Version {__version__}", comic.mascot_pixmap(32), row_padding=5)
        card.add_row("Spracherkennung", "", _value(f"faster-whisper · {whisper_model_name}"))
        card.add_row("Politur", "", _value(f"{cfg.styler.model} ({cfg.styler.provider})"))
        card.add_row("Taste", "", _value(f"{effective_hotkey(cfg.hotkey.combo).upper()} halten"))
        card.add_row("Mikrofon", "", _value(mic_label))
        source = _value(
            f"<a href='https://github.com/{UPDATE_REPO}' style='color: {comic.INK};'>"
            f"github.com/{UPDATE_REPO}</a>"
        )
        source.setOpenExternalLinks(True)
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        card.add_row("Quelle", "", source)
        body.addWidget(card)
        body.addWidget(comic.HintBubble([
            "Speech2Anywhere von", comic.brand_logo(20), "· © 2026 Mike Pollow, Personal-Use-Lizenz",
        ]))
        body.addStretch()

        close_btn = QPushButton("Schließen")
        close_btn.setObjectName("comicPrimary")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        body.addLayout(comic.footer_row(None, close_btn))
