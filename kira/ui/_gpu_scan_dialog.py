from __future__ import annotations
import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QWidget

from kira.ui import _comic as comic

_PANEL_W, _PANEL_H = 340, 150
_SHADOW = 5


class _ScanWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(_PANEL_W, _PANEL_H)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._phase += 0.22
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        card = QRectF(1.5, 1.5, _PANEL_W - _SHADOW - 3, _PANEL_H - _SHADOW - 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(comic.INK))
        p.drawRoundedRect(card.translated(_SHADOW, _SHADOW), 16, 16)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(comic.INK), 3))
        p.drawRoundedRect(card, 16, 16)

        p.setPen(QColor(comic.INK))
        p.setFont(comic.baloo(700, 17))
        p.drawText(QRectF(0, 18, card.width(), 26), Qt.AlignmentFlag.AlignHCenter, "GPU wird geprüft…")

        left, width = 34.0, card.width() - 68
        cy, amp = 94.0, 20.0
        wave = QPainterPath()
        steps = int(width)
        for px in range(steps + 1):
            t = px / width
            y = cy + amp * (
                0.7 * math.sin(t * 6.0 * math.pi - self._phase)
                + 0.3 * math.sin(t * 2.4 * math.pi - self._phase * 0.5)
            )
            point = QPointF(left + px, y)
            if px == 0:
                wave.moveTo(point)
            else:
                wave.lineTo(point)
        p.setBrush(Qt.BrushStyle.NoBrush)
        cap, join = Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        p.setPen(QPen(QColor(comic.YELLOW), 10, Qt.PenStyle.SolidLine, cap, join))
        p.drawPath(wave)
        p.setPen(QPen(QColor(comic.INK), 3, Qt.PenStyle.SolidLine, cap, join))
        p.drawPath(wave)


class GpuScanDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        comic.border_off_on_show(self)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFixedSize(_PANEL_W, _PANEL_H)
        self._scan = _ScanWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scan)

    def start(self) -> None:
        self._scan.start()
        self.show()

    def finish(self) -> None:
        self._scan.stop()
        self.close()
