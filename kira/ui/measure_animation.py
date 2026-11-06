# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math
import time

from PyQt6.QtCore import QPointF, QRectF, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget

from kira.texte import tr
from kira.ui import _comic as comic
from kira.ui.hud import comic as scene
from kira.ui.hud.base import H, W

FRAME_MS = 33
SHADOW = 4


def _ink_text(p: QPainter, x: float, y: float, text: str, font, color) -> None:
    path = QPainterPath()
    path.addText(QPointF(x, y), font, text)
    p.fillPath(path, QColor(color))


class MeasureAnimation(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(W + SHADOW + 2, H + SHADOW + 2)
        self._started = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.update)
        self.setVisible(False)

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self._started = time.monotonic()
        self._timer.start()
        self.setVisible(True)

    def stop(self) -> None:
        self._timer.stop()
        self.setVisible(False)

    def paintEvent(self, event) -> None:  # noqa: N802
        t = time.monotonic() - self._started
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QPainterPath()
        card.addRoundedRect(QRectF(1.5, 1.5, W - 3, H - 3), 16, 16)
        scene._ink_shape(p, card, scene.WHITE)
        scene._mascot(p, "think")
        scene._trail(p)
        scene._ink_shape(p, scene._cloud(scene.CLOUD), scene.THOUGHT, 2.2)
        scene._gears(p, 115, 31, t * 2 * math.pi * 0.55)
        _ink_text(p, 137, 31, tr("Messen"), comic.baloo(800, 15), scene.INK)
        scene._dots(p, 225, 26, t)
        _ink_text(p, 137, 47, tr("bitte kurz warten"), comic.baloo(600, 11), scene.LABEL)
        p.end()
