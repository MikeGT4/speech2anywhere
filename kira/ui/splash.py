from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QSplashScreen


from kira._resources import assets_dir as _assets_dir  # noqa: E402
_ASSETS = _assets_dir()


def make_splash() -> QSplashScreen | None:
    splash_path = _ASSETS / "kira-splash.png"
    if not splash_path.exists():
        splash_path = _ASSETS / "digitalroots-logo.png"
        if not splash_path.exists():
            return None
    pix = QPixmap(str(splash_path))
    pix = pix.scaledToWidth(720, Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    splash.show()
    return splash
