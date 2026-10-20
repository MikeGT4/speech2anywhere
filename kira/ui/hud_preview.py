# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging
import time
from collections import deque

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QSizePolicy, QWidget

from kira.live_words import fragments
from kira.ui import _comic as comic
from kira.ui.hud import create_style
from kira.ui.hud.base import H, W, Frame, load_fonts
from kira.ui.hud.signal import SAMPLE_RATE, SignalAnalysis, SignalTap
from kira.ui.hud_qt import CURSOR_GAP_X, CURSOR_GAP_Y, FRAME_MS, animations_off

log = logging.getLogger(__name__)

RAW_TEXT = "Äh, kannst du mir die Unterlagen bis Freitag schicken"
POLISHED_TEXT = "Kannst du mir die Unterlagen bis Freitag schicken?"
RELEASE_S = 3.4
POLISH_S = 5.2
DONE_S = 7.0
IDLE_S = 7.3
LOOP_S = 9.0
STUCK_S = LOOP_S + 2.0
WORD_TIMES = (0.7, 1.3, 1.9, 2.5, 3.1)
BLOCK = 1600
BLOCK_S = BLOCK / SAMPLE_RATE
VOICE_PEAK = 0.3
ROOM_NOISE = 0.004

DESK = QColor("#2E2E33")
POINTER_FILL = QColor("#FFFFFF")
PAD = 12.0
POINTER_H = 19.0
TILE_SCALE = 1.5


def voice_block(start: int, count: int, rng: np.random.Generator) -> np.ndarray:
    n = np.arange(start, start + count, dtype=np.float64)
    t = n / SAMPLE_RATE
    syllable = np.clip(np.sin(2 * np.pi * 4.6 * t) * 1.3 + 0.25, 0.0, 1.0)
    phrase = np.clip(np.sin(2 * np.pi * 0.45 * t + 0.9) * 4.0 + 3.4, 0.0, 1.0)
    f0 = 2 * np.pi * (128.0 * t + 6.0 * np.sin(2 * np.pi * 0.8 * t))
    tone = (np.sin(f0) + 0.55 * np.sin(2 * f0) + 0.3 * np.sin(3 * f0)
            + 0.15 * np.sin(5 * f0) + 0.1 * np.sin(9 * f0)) / 2.1
    hiss = rng.uniform(-1.0, 1.0, count)
    return (VOICE_PEAK * syllable * phrase * (tone + 0.12 * hiss) + ROOM_NOISE * hiss).astype(np.float32)


def spoken_words(seconds: float) -> list[str]:
    words = RAW_TEXT.split()
    count = max(1, min(len(words), round(len(words) * seconds / RELEASE_S)))
    return fragments(" ".join(words[:count]))


class PreviewDriver:
    def __init__(self, key: str, scale: float = TILE_SCALE, live_words: bool = True,
                 reduced: bool = False) -> None:
        self.key = key
        self.scale = scale
        self.live_words = live_words
        self.reduced = reduced
        self.dpr = 1.0
        self.failed = False
        self.tap = SignalTap()
        self.an = SignalAnalysis()
        self.frame = Frame()
        self.style = self._build(key)
        self.t = 0.0
        self.loop_t0 = 0.0
        self._events: list[tuple[float, str]] = []
        self._pushed = 0
        self._press_t = 0.0
        self._recent: deque[str] = deque(maxlen=3)
        self._rng = np.random.default_rng(7)

    @property
    def loop_t(self) -> float:
        return self.t - self.loop_t0

    def _build(self, key: str):
        try:
            return create_style(key)
        except Exception:
            log.exception("Vorschau: Stil %s nicht ladbar", key)
            self.failed = True
            return None

    def set_style(self, key: str, t: float) -> None:
        self.key = key
        self.failed = False
        style = self._build(key)
        if style is not None:
            self.style = style
            self.restart(t)

    def restart(self, t: float) -> None:
        self.t = t
        self.loop_t0 = t
        self._events = [(0.0, "rec")]
        self._events += [(w, "words") for w in WORD_TIMES]
        self._events += [(RELEASE_S, "trans"), (POLISH_S, "polish"), (DONE_S, "done"), (IDLE_S, "idle")]

    def advance(self, t: float) -> None:
        dt = min(0.05, max(0.0, t - self.t))
        self.t = t
        if self.failed:
            return
        try:
            self._run_events()
            self._feed_voice()
            style = self.style
            self.tap.advance(dt)
            self.an.update(self.tap, t, dt, recording=style.mode == "rec", rec_elapsed=t - style.t0)
            style.tick(t, dt, self.frame, self.tap, self.an)
            if not self._events and self.loop_t >= LOOP_S and (not style.visible or self.loop_t >= STUCK_S):
                self.restart(t)
        except Exception:
            self._fail("Rechenschritt")

    def paint(self, p: QPainter, x: float, y: float) -> None:
        style = self.style
        if self.failed or not style.visible:
            return
        p.save()
        try:
            p.translate(x, y)
            p.scale(self.scale, self.scale)
            p.setOpacity(style.fade_alpha(self.t))
            style.paint(p, self.t, self.frame, self.tap, self.an)
        except Exception:
            self._fail("Zeichnen")
        finally:
            p.restore()

    def _fail(self, where: str) -> None:
        if not self.failed:
            log.exception("Vorschau %s: %s fehlgeschlagen", self.key, where)
        self.failed = True

    def _run_events(self) -> None:
        while self._events and self._events[0][0] <= self.loop_t + 1e-9:
            at, kind = self._events.pop(0)
            self._apply(self.loop_t0 + at, kind, at)

    def _apply(self, t: float, kind: str, at: float) -> None:
        style, f = self.style, self.frame
        if kind == "rec":
            f.reduced = self.reduced
            f.px = self.scale * self.dpr
            f.polishing = False
            f.polish_t = -1.0
            f.raw_text = ""
            f.polished_text = ""
            self.tap.start()
            self.an.reset(t)
            self._pushed = 0
            self._press_t = t
            self._recent.clear()
            style.press(t, f)
        elif kind == "words":
            words = [w for w in spoken_words(at) if w not in self._recent]
            if words and self.live_words and style.live_words:
                self._recent.extend(words)
                style.feed_words(t, words)
        elif kind == "trans":
            style.release(t, f)
        elif kind == "polish":
            f.raw_text = RAW_TEXT
            f.polishing = True
            f.polish_t = t
        elif kind == "done":
            f.polished_text = POLISHED_TEXT
            style.done(t, f)
        elif kind == "idle":
            style.abort(t)

    def _feed_voice(self) -> None:
        if self.style.mode != "rec":
            return
        due = int((self.t - self._press_t) / BLOCK_S) + 1
        while self._pushed < due:
            self.tap.push(voice_block(self._pushed * BLOCK, BLOCK, self._rng))
            self._pushed += 1


class HudPreview(QWidget):
    def __init__(self, key: str, live_words: bool = True, scale: float = TILE_SCALE,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        load_fonts()
        self._driver = PreviewDriver(key, min(scale, TILE_SCALE), live_words)
        hud_w, hud_h = W * TILE_SCALE, H * TILE_SCALE
        self._size = QSize(round(PAD + CURSOR_GAP_X + hud_w + PAD),
                           round(PAD + hud_h + CURSOR_GAP_Y + POINTER_H + PAD))
        self.setMinimumWidth(self._size.width())
        self.setFixedHeight(self._size.height())
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Vorschau der Anzeige")
        self.setAccessibleDescription("Spielt ein Diktat im gewählten Stil ab: Aufnahme, Erkennen, Politur, fertig.")
        self.setToolTip("So läuft die Anzeige beim Diktieren ab: Aufnahme, Erkennen, Politur, fertig.")
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    @property
    def driver(self) -> PreviewDriver:
        return self._driver

    @property
    def running(self) -> bool:
        return self._timer.isActive()

    def sizeHint(self) -> QSize:  # noqa: N802
        return self._size

    def set_style(self, key: str) -> None:
        if not key or key == self._driver.key:
            return
        self._driver.set_style(key, time.monotonic())
        self._driver.reduced = animations_off()
        self.update()

    def set_live_words(self, on: bool) -> None:
        self._driver.live_words = bool(on)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._driver.reduced = animations_off()
        self._driver.dpr = self.devicePixelRatioF()
        self._driver.restart(time.monotonic())
        self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        self._driver.advance(time.monotonic())
        self.update()

    def pointer_tip(self) -> QPointF:
        group_w = CURSOR_GAP_X + W * TILE_SCALE
        return QPointF(round((self.width() - group_w) / 2), PAD + H * TILE_SCALE + CURSOR_GAP_Y)

    def hud_origin(self) -> QPointF:
        tip = self.pointer_tip()
        return QPointF(tip.x() + CURSOR_GAP_X, tip.y() - CURSOR_GAP_Y - H * self._driver.scale)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            self._paint_desk(p)
            self._paint_pointer(p, self.pointer_tip())
            origin = self.hud_origin()
            self._driver.paint(p, origin.x(), origin.y())
        finally:
            p.end()

    def _paint_desk(self, p: QPainter) -> None:
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        p.fillPath(path, DESK)
        p.setPen(QPen(QColor(comic.INK), 2))
        p.drawPath(path)

    @staticmethod
    def _paint_pointer(p: QPainter, tip: QPointF) -> None:
        x, y = tip.x(), tip.y()
        arrow = QPolygonF([
            QPointF(x, y), QPointF(x, y + 16.5), QPointF(x + 4.0, y + 12.6), QPointF(x + 6.6, y + 18.4),
            QPointF(x + 9.0, y + 17.4), QPointF(x + 6.5, y + 11.7), QPointF(x + 11.8, y + 11.7),
        ])
        p.save()
        p.setBrush(POINTER_FILL)
        pen = QPen(QColor(comic.INK), 1.2)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.drawPolygon(arrow)
        p.restore()
