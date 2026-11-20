# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_OUT, Frame, clamp, prog
from kira.ui.hud.fachgebiet import (
    FLY_ROUTES, Fachgebiet, badge_check, check, fly_out, heart, outlined, pulse, ringed, rounded, stroke,
)
from kira.ui.hud.saison import INK, ROUND, STEEL, WHITE, Pose, ellipse, faded, glow, polygon, sparkle
from kira.ui.hud.weihnachten import _bubble_path
from kira.texte import N_

HEART_RED = QColor("#E5394A")
BLUSH = QColor("#FFB8C0")
MIRROR = QColor("#E8EEF2")
MIRROR_SHADE = QColor("#A9B6BF")
BAND = QColor("#34414D")
FILM = QColor("#14202B")
XRAY = QColor("#C9F0FF")
LIGHTBOX = QColor("#DDE3E7")
PAD_HEAD = QColor("#DCEBF5")
PAD_LINE = QColor("#C9DCEA")
BLUE_INK = QColor("#2456A6")
HEALTHY = QColor("#1E9E6A")
SKIN = QColor("#F1C79B")
SKIN_PAD = QColor("#FBE3C8")
TUBE = QColor("#3A4652")

ECG_LEFT, ECG_RIGHT, ECG_BASE, ECG_HEIGHT = 76.0, 250.0, 71.5, 13.5
ECG_SPEED = 62.0
ECG_FLOOR = 75.0
CALM_PERIOD, CALM_AMP = 0.9, 0.42
HEART_CLOCK = (244.0, 15.0)
MIRROR_AT = (35.0, 21.0)
PAD = (101.0, 9.5, 40.0, 42.5)
PAD_ROWS = (17.0, 24.5, 32.0)
CLEAN_WORDS = ((9.0, 6.0, 11.0), (12.0, 7.0, 7.0), (8.0, 10.0))
SCRIBBLE_LOOPS = 7
SCRIBBLE_STEPS = 90


def ecg_wave(u: float) -> float:
    return (0.12 * pulse(u, 0.16, 0.035) - 0.10 * pulse(u, 0.285, 0.012) + pulse(u, 0.31, 0.012)
            - 0.26 * pulse(u, 0.338, 0.013) + 0.24 * pulse(u, 0.55, 0.055))


def _head_mirror(p: QPainter, x: float, y: float, angle: float, glint: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    band = QPainterPath(QPointF(-18.5, 4.2))
    band.cubicTo(QPointF(-10.0, -0.6), QPointF(10.0, -0.6), QPointF(18.5, 4.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for color, width in ((WHITE, 5.4), (INK, 3.6), (BAND, 1.6)):
        p.setPen(QPen(color, width, *ROUND))
        p.drawPath(band)
    p.save()
    p.translate(-4.5, -6.6)
    p.rotate(-14)
    ringed(p, ellipse(0, 0, 8.4, 7.4), MIRROR, 1.5, 4.4)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(MIRROR_SHADE, 1.0, *ROUND))
    p.drawPath(ellipse(0, 0, 6.2, 5.3))
    shine = QPainterPath(QPointF(-5.0, -1.0))
    shine.cubicTo(QPointF(-4.5, -3.8), QPointF(-2.0, -5.2), QPointF(0.8, -5.0))
    p.setPen(QPen(WHITE, 1.5, *ROUND))
    p.drawPath(shine)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawEllipse(QPointF(0.4, 0.3), 1.5, 1.3)
    p.restore()
    if glint > 0:
        sparkle(p, 2.0, -11.0, 3.2 * glint, WHITE)
    p.restore()


def _heart_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = HEART_CLOCK
    frac = elapsed - math.floor(elapsed)
    beat = 1.0 if reduced else 1.0 + 0.17 * pulse(frac, 0.05, 0.05) + 0.09 * pulse(frac, 0.25, 0.05)
    p.save()
    p.translate(cx, cy)
    p.scale(beat, beat)
    cm._ink_shape(p, heart(0, 0.6, 7.6), HEART_RED, 1.8, 1.6)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(faded(WHITE, 0.9))
    p.drawEllipse(QPointF(-3.6, -2.0), 1.7, 1.0)
    p.restore()
    since = elapsed % 60
    if not reduced and elapsed >= 60 and since < 0.9:
        u = since / 0.9
        for j, ox in enumerate((-8.0, 7.0)):
            p.save()
            p.setOpacity(p.opacity() * (1.0 - prog(u, 0.5, 0.5)))
            outlined(p, heart(cx + ox + math.sin(u * 6 + j) * 1.2, cy - 4 - u * 5, 2.4), BLUSH, 0.9)
            p.restore()
    cm._clock_digits(p, cx - 11.5, cy + 0.4, elapsed)


def _scribble(xa: float, xb: float, y: float, upto: float, seed: int) -> QPainterPath:
    total = SCRIBBLE_LOOPS * 2 * math.pi
    path = QPainterPath()
    for i in range(SCRIBBLE_STEPS + 1):
        s = i / SCRIBBLE_STEPS
        if s > upto:
            break
        th = s * total
        point = QPointF(xa + s * (xb - xa) - 2.0 * math.sin(th),
                        y - 2.0 - 1.9 * math.cos(th) + 0.8 * math.sin(th * 0.37 + seed))
        if i == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    return path


def _pen(p: QPainter, x: float, y: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(-50)
    outlined(p, rounded(2.0, -1.5, 12.0, 3.0, 1.4), BLUE_INK, 0.9)
    outlined(p, polygon(((0.0, 0.0), (2.4, -1.4), (2.4, 1.4))), STEEL, 0.8)
    stroke(p, 9.5, -1.5, 9.5, 1.5, faded(WHITE, 0.8), 0.7)
    p.restore()


class Medizin(Fachgebiet):
    key = "medizin"
    SCENES = ("rezept", "roentgen", "abhoeren")
    CLOCKS = ("herz",)
    LANES = cm.LANES
    WORDS = (N_("bla"), N_("Aaah!"), N_("bla"))
    WORD_FILLS = (QColor(comic.YELLOW_HOVER), QColor("#FFFFFF"), BLUSH)
    ZACK_WORD = N_("Kerngesund!")
    SILENCE = (N_("Kein Signal"), N_("Das Mikrofon hält die Luft an."))
    FIGURE_SCALE = 0.8464
    FIGURE_SHIFT = (-0.106, 4.444)
    CAPTIONS = {
        "rezept": (N_("kritzelt …"), N_("lesbar!"), 2.45),
        "roentgen": (N_("durchleuchtet …"), N_("alles heil!"), 2.5),
        "abhoeren": (N_("hört hin …"), N_("klingt gut!"), 2.4),
    }
    LOOKS = {
        "rezept": ((10, 12), "line", "o"),
        "roentgen": ((10, 6), "line", "smile"),
        "abhoeren": ((6, 12), "smile", "o"),
    }

    def __init__(self) -> None:
        super().__init__()
        self._beats: list[tuple[float, float, float]] = []
        self._next_beat = 0.0

    def _calm_history(self, t: float) -> None:
        self._beats = []
        start = t - 3.9
        while start < t:
            self._beats.append((start, CALM_PERIOD, CALM_AMP))
            start += CALM_PERIOD
        self._next_beat = start

    def on_press(self, t: float, f: Frame) -> None:
        super().on_press(t, f)
        self._calm_history(t)

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        super().step(t, dt, f, tap, an)
        if self.mode == "hidden":
            return
        now = self.t0 + 0.2 if f.reduced else t
        if not self._beats or now - self._next_beat > 4.0:
            self._calm_history(now)
        while self._next_beat <= now:
            period, amp = CALM_PERIOD, CALM_AMP
            if self.mode == "rec" and not an.silent:
                level = clamp(self._lv * 1.15, 0.0, 1.0)
                period, amp = 0.92 - 0.3 * level, 0.45 + 0.55 * level
                if an.clip:
                    amp = 1.15
            self._beats.append((self._next_beat, period, amp))
            self._next_beat += period
        horizon = now - (ECG_RIGHT - ECG_LEFT) / ECG_SPEED - 1.5
        self._beats = [beat for beat in self._beats if beat[0] + beat[1] > horizon]

    def ecg_at(self, moment: float) -> float:
        for start, period, amp in reversed(self._beats):
            if start <= moment:
                u = (moment - start) / period
                return amp * ecg_wave(u) if u < 1.0 else 0.0
        return 0.0

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        if self.mode == "error" or (self.mode == "rec" and an.silent and not an.clip):
            return
        if not self._beats:
            self._calm_history(t)
        now = self.t0 + 0.2 if f.reduced else t
        trace = QPainterPath()
        x = ECG_LEFT
        head = QPointF(ECG_LEFT, ECG_BASE)
        while x <= ECG_RIGHT + 0.01:
            head = QPointF(x, min(ECG_FLOOR, ECG_BASE - ECG_HEIGHT * self.ecg_at(now - (ECG_RIGHT - x) / ECG_SPEED)))
            if x == ECG_LEFT:
                trace.moveTo(head)
            else:
                trace.lineTo(head)
            x += 1.0
        ramp = QLinearGradient(ECG_LEFT, 0, ECG_LEFT + 30.0, 0)
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        for color, width in ((WHITE, 4.6), (INK, 1.9)):
            ramp.setColorAt(0.0, faded(color, 0.0))
            ramp.setColorAt(1.0, faded(color, 1.0))
            p.setPen(QPen(QBrush(ramp), width, *ROUND))
            p.drawPath(trace)
        glow(p, head.x(), head.y(), 4.2, HEART_RED, 0.55)
        p.setPen(QPen(INK, 1.0))
        p.setBrush(HEART_RED)
        p.drawEllipse(head, 2.2, 2.2)
        p.restore()

    def accessory(self, p: QPainter, pose: Pose) -> None:
        angle = dx = dy = glint = 0.0
        if pose.kind == "talk":
            if not pose.reduced:
                angle = 3.0 * pose.level * math.sin(pose.t * 8.0)
                dy = -0.5 * pose.level * abs(math.sin(pose.t * 8.0))
        elif pose.kind == "shout":
            angle, dy = -9.0 + (0.0 if pose.reduced else 4.0 * math.sin(pose.t * 31.0)), -0.6
        elif pose.kind == "wink":
            glint = 1.0 if pose.reduced else 0.65 + 0.35 * math.sin(pose.t * 9.0)
        elif pose.kind == "sad":
            angle, dx, dy = 11.0, 1.0, 2.4
        else:
            angle = 0.0 if pose.reduced else 1.5 * math.sin(pose.t * 1.6)
            if pose.kind == "look":
                angle += pose.look[0] * 0.2
        _head_mirror(p, MIRROR_AT[0] + dx, MIRROR_AT[1] + dy, angle, glint)

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _heart_clock(p, elapsed, reduced)

    def scene_rezept(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, w, h = PAD
        pad = rounded(x0, y0, w, h, 3.0)
        cm._ink_shape(p, pad, WHITE, 1.6, 1.4)
        p.save()
        p.setClipPath(pad)
        p.fillRect(QRectF(x0, y0, w, 8.0), PAD_HEAD)
        p.restore()
        stroke(p, x0, y0 + 8.0, x0 + w, y0 + 8.0, INK, 1.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK)
        for k in range(4):
            p.drawEllipse(QPointF(x0 + 8.0 + k * 8.0, y0 + 0.6), 1.3, 1.3)
        rows = [y0 + row for row in PAD_ROWS]
        for row_y in rows:
            stroke(p, x0 + 4.0, row_y + 0.8, x0 + w - 4.0, row_y + 0.8, PAD_LINE, 0.8)
        clean = clamp((e - 2.3) / 0.35, 0.0, 1.0)
        written = clamp(e / 2.3, 0.0, 1.0)
        pen_at = None
        for i, row_y in enumerate(rows):
            part = clamp(written * 3.0 - i, 0.0, 1.0)
            if part > 0 and clean < 1.0:
                path = _scribble(x0 + 6.0, x0 + w - 7.0 - (8.0 if i == 2 else 0.0), row_y, part, i)
                p.save()
                p.setOpacity(p.opacity() * (1.0 - clean))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(BLUE_INK, 0.9, *ROUND))
                p.drawPath(path)
                p.restore()
                if 0.0 < part < 1.0:
                    pen_at = path.currentPosition()
            if clean > 0:
                p.save()
                p.setOpacity(p.opacity() * clean)
                x = x0 + 5.0
                for length in CLEAN_WORDS[i]:
                    stroke(p, x, row_y - 0.6, x + length, row_y - 0.6, INK, 1.7)
                    x += length + 3.2
                p.restore()
        if pen_at is not None and not reduced:
            _pen(p, pen_at.x(), pen_at.y())
        if clean > 0:
            p.save()
            p.setOpacity(p.opacity() * clean)
            check(p, x0 + w - 11.0, y0 + h - 11.0, 8.0, HEALTHY, 2.0)
            p.restore()
            if not reduced and clean < 1.0:
                sparkle(p, x0 + w - 2.0, y0 + 12.0, 3.6 * math.sin(clean * math.pi), WHITE)

    def scene_roentgen(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, w, h = 100.0, 10.0, 42.0, 35.0
        cm._ink_shape(p, rounded(x0, y0, w, h, 3.5), LIGHTBOX, 1.6, 1.4)
        stroke(p, x0 + 8.0, y0 + h + 1.5, x0 + 6.0, y0 + h + 6.0, INK, 1.6)
        stroke(p, x0 + w - 8.0, y0 + h + 1.5, x0 + w - 6.0, y0 + h + 6.0, INK, 1.6)
        screen = rounded(x0 + 3.5, y0 + 3.5, w - 7.0, h - 7.0, 2.0)
        p.setPen(QPen(INK, 1.0))
        p.setBrush(FILM)
        p.drawPath(screen)
        light = 1.0 if reduced else clamp(e / 0.3, 0.0, 1.0) * (0.75 + 0.25 * math.sin(e * 60) if e < 0.5 else 1.0)
        reveal = 1.0 if e >= 2.4 else clamp((e - 0.3) / 2.1, 0.0, 1.0)
        top, inner_h = y0 + 3.5, h - 7.0
        p.save()
        p.setClipPath(screen)
        glow(p, x0 + w / 2, y0 + h / 2, 22.0, XRAY, 0.22 * light)
        p.save()
        p.setClipRect(QRectF(x0, top, w, inner_h * reveal), Qt.ClipOperation.IntersectClip)
        bubble = _bubble_path(x0 + w / 2, y0 + h / 2 - 0.5, 0.05)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(faded(XRAY, 0.35 * light), 3.0, *ROUND))
        p.drawPath(bubble)
        p.setPen(QPen(faded(XRAY, light), 1.2, *ROUND))
        p.drawPath(bubble)
        beat = 1.0
        if e >= 2.4 and not reduced:
            frac = ((e - 2.4) / 0.8) % 1.0
            beat = 1.0 + 0.15 * pulse(frac, 0.06, 0.05) + 0.08 * pulse(frac, 0.28, 0.05)
        p.save()
        p.translate(x0 + w / 2, y0 + h / 2 - 1.0)
        p.scale(beat, beat)
        p.setPen(QPen(faded(XRAY, light), 0.9, *ROUND))
        p.setBrush(faded(HEART_RED, 0.75 * light))
        p.drawPath(heart(0, 0, 3.6))
        p.restore()
        p.restore()
        if 0.3 < e < 2.4 and not reduced:
            p.fillRect(QRectF(x0, top + inner_h * reveal - 1.5, w, 3.0), faded(XRAY, 0.45))
        p.restore()
        if e >= 2.4:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - 2.4) / 0.2, 0.0, 1.0))
            p.save()
            p.translate(x0 + w - 3.0, y0 + h - 3.0)
            p.scale(pop, pop)
            badge_check(p, 0.0, 0.0, 5.2, WHITE, HEALTHY)
            p.restore()

    def scene_abhoeren(self, p: QPainter, e: float, reduced: bool) -> None:
        cx, cy = 117.0, 34.0
        beat_time = 0.0 if reduced else e
        frac = (beat_time / 0.8) % 1.0
        beat = 1.0 + 0.12 * pulse(frac, 0.06, 0.05) + 0.07 * pulse(frac, 0.3, 0.05)
        p.save()
        p.translate(cx, cy)
        p.scale(beat, beat)
        cm._ink_shape(p, heart(0, 0, 11.0), HEART_RED, 2.0, 1.8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(faded(WHITE, 0.85))
        p.drawEllipse(QPointF(-5.5, -3.8), 2.4, 1.5)
        p.restore()
        chest = QPointF(cx + 8.5, cy - 2.0)
        tube = QPainterPath(chest)
        tube.cubicTo(QPointF(cx + 22.0, cy - 2.0), QPointF(cx + 16.0, cy - 16.0), QPointF(cx + 23.0, cy - 21.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(INK, 3.2, *ROUND))
        p.drawPath(tube)
        p.setPen(QPen(TUBE, 1.6, *ROUND))
        p.drawPath(tube)
        fork = QPointF(cx + 23.0, cy - 21.0)
        for ex, ey in ((cx + 17.5, cy - 27.5), (cx + 29.0, cy - 27.0)):
            arm = QPainterPath(fork)
            arm.quadTo(QPointF((fork.x() + ex) / 2, fork.y() - 1.0), QPointF(ex, ey))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(INK, 2.2, *ROUND))
            p.drawPath(arm)
            p.setPen(QPen(STEEL, 0.9, *ROUND))
            p.drawPath(arm)
            outlined(p, ellipse(ex, ey, 1.6), INK, 0.6)
        outlined(p, ellipse(chest.x(), chest.y(), 5.4), STEEL, 1.5)
        outlined(p, ellipse(chest.x(), chest.y(), 3.0), WHITE, 0.9)
        at = self.payoff("abhoeren")
        if e < at and not reduced:
            for j in range(2):
                age = (beat_time * 1.25 + j * 0.5) % 1.0
                r = 7.0 + age * 9.0
                p.save()
                p.setOpacity(p.opacity() * (1.0 - age))
                p.setPen(QPen(INK, 1.1, *ROUND))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(QRectF(chest.x() - r, chest.y() - r, 2 * r, 2 * r), -40 * 16, 80 * 16)
                p.restore()
        elif e >= at:
            for j in range(2):
                age = 0.45 if reduced else ((e - at) * 0.9 + j * 0.5) % 1.0
                x = cx - 8.0 + j * 7.0 + math.sin(age * 5 + j) * 2.0
                y = cy - 9.0 - age * 10.0
                p.save()
                p.setOpacity(p.opacity() * (1.0 - prog(age, 0.6, 0.4)))
                outlined(p, ellipse(x, y, 2.1, 1.6), INK, 0.6)
                stroke(p, x + 1.8, y, x + 1.8, y - 7.0, INK, 1.1)
                stroke(p, x + 1.8, y - 7.0, x + 4.4, y - 5.0, INK, 1.1)
                p.restore()

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        def draw(pp, x, y, size, moment, j):
            pp.save()
            pp.translate(x, y)
            pp.rotate(math.sin(moment * 9 + j) * 8)
            cm._ink_shape(pp, heart(0, 0, 4.8 * size), HEART_RED if j % 2 == 0 else BLUSH, 1.3, 1.1)
            pp.restore()
        fly_out(p, t, f, k, draw, FLY_ROUTES)

    def error_decor(self, p: QPainter, left: float, top: float) -> None:
        p.translate(left + 2.0, top + 3.5)
        p.rotate(-45)
        p.scale(0.8, 0.8)
        outlined(p, rounded(-12.0, -3.8, 24.0, 7.6, 3.8), SKIN, 1.2)
        p.setPen(QPen(faded(INK, 0.5), 0.7))
        p.setBrush(SKIN_PAD)
        p.drawRoundedRect(QRectF(-4.2, -2.6, 8.4, 5.2), 1.2, 1.2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(faded(INK, 0.35))
        for dx in (-9.0, -7.0, 7.0, 9.0):
            for dy in (-1.2, 1.2):
                p.drawEllipse(QPointF(dx, dy), 0.45, 0.45)
