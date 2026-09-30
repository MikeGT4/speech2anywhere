from __future__ import annotations

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton

from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme

from kira._resources import assets_dir as _assets_dir  # noqa: E402
_ASSETS = _assets_dir()


def _explain(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("comicValue")
    label.setWordWrap(True)
    return label


class SetupHintDialog(QDialog):
    def __init__(self, mic_ok: bool, ollama_ok: bool) -> None:
        super().__init__()
        self.setWindowTitle("Speech2Anywhere Setup")
        icon_path = _ASSETS / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setModal(True)
        self.setMinimumWidth(680)
        apply_light_theme(self)
        self.user_clicked_open_mic_settings = False
        body = comic.dialog_frame(self, "Setup")

        card = comic.ComicCard("Noch etwas Setup", comic.mascot_pixmap(32))
        if not mic_ok:
            card.add_row("Mikrofon-Zugriff fehlt", "", _explain(
                "Speech2Anywhere braucht Zugriff aufs Mikrofon, um deine Stimme aufzunehmen."
            ))
        if not ollama_ok:
            card.add_row("Ollama nicht erreichbar", "", _explain(
                "Unter http://localhost:11434 antwortet kein Ollama. Bitte stelle sicher, dass Ollama läuft. "
                "Ohne Ollama fügt Speech2Anywhere den unpolierten Whisper-Text ein."
            ))
        body.addWidget(card)
        body.addStretch()

        buttons: list[QPushButton] = []
        if not mic_ok:
            mic_btn = QPushButton("Mikrofon-Einstellungen öffnen")
            mic_btn.setObjectName("comicPrimary")
            mic_btn.clicked.connect(self._on_mic_clicked)
            buttons.append(mic_btn)
        close_btn = QPushButton("Schließen")
        if mic_ok:
            close_btn.setObjectName("comicPrimary")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        buttons.append(close_btn)
        body.addLayout(comic.footer_row("© 2026 Mike Pollow · Digitalroots", *buttons))

    def _on_mic_clicked(self) -> None:
        self.user_clicked_open_mic_settings = True
        self.accept()
