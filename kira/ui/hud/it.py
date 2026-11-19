# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_OUT, Frame, clamp
from kira.ui.hud.fachgebiet import (
    Fachgebiet, badge_check, fly_out, lettering, outlined, ringed, ringed_line, rounded, stroke, twinkle,
)
from kira.ui.hud.saison import INK, ROUND, WHITE, YELLOW, Pose, ellipse, faded, glow, sparkle
from kira.texte import N_

SLATE = QColor("#1F2633")
SLATE_LIGHT = QColor("#34405A")
CYAN = QColor("#4FC1FF")
GREEN = QColor("#4AD66D")
ORANGE = QColor("#FFA657")
CODE_RED = QColor("#FF6B6B")
CODE_WHITE = QColor("#E6EDF3")
HEADSET = QColor("#2B2F3A")
CUSHION = QColor("#4A5160")
BEETLE = QColor("#5BBF6A")
BEETLE_DARK = QColor("#2F7A3B")
DIM = QColor("#6B7385")
LENS = QColor("#CFEFFF")

WIFI_AT = QPointF(83.0, 72.0)
BINARY_CLOCK = (240.0, 9.5)
WIFI_RADII = (5.6, 10.2, 14.8)
CODE_COLORS = (CYAN, GREEN, ORANGE, CODE_WHITE, CYAN, ORANGE, GREEN, CODE_WHITE)
GLYPHS = ("{ }", "1", "</>", "0")
GLYPH_ROUTES = ((228.0, 20.0, 236.0, 12.0, 1.0), (98.0, 18.0, 88.0, 11.0, 0.9), (232.0, 56.0, 238.0, 66.0, 0.85),
                (106.0, 58.0, 94.0, 67.0, 0.8))
BRANCH_STEPS = 24


def _cubic(a, b, c, d, steps: int) -> list[QPointF]:
    out = []
    for i in range(steps + 1):
        u = i / steps
        v = 1.0 - u
        w0, w1, w2, w3 = v * v * v, 3 * v * v * u, 3 * v * u * u, u * u * u
        out.append(QPointF(w0 * a[0] + w1 * b[0] + w2 * c[0] + w3 * d[0],
                           w0 * a[1] + w1 * b[1] + w2 * c[1] + w3 * d[1]))
    return out


def branch_points(x0: float, x1: float, y: float) -> list[QPointF]:
    down = _cubic((x0 + 8.0, y), (x0 + 14.0, y + 16.0), (x0 + 22.0, y + 16.0), (x0 + 28.0, y + 16.0), BRANCH_STEPS)
    up = _cubic((x0 + 30.0, y + 16.0), (x0 + 34.0, y + 16.0), (x0 + 36.0, y + 8.0), (x1 - 4.0, y), BRANCH_STEPS)
    return down + up


def _headset(p: QPainter, dy: float, angle: float, led: bool, mic_drop: float, mic_wiggle: float) -> None:
    p.save()
    p.translate(35.0, 36.0 + dy)
    p.rotate(angle)
    band = QPainterPath(QPointF(-25.0, 0.0))
    band.cubicTo(QPointF(-25.0, -24.0), QPointF(25.0, -24.0), QPointF(25.0, 0.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for color, width in ((WHITE, 6.0), (INK, 4.2), (HEADSET, 2.2)):
        p.setPen(QPen(color, width, *ROUND))
        p.drawPath(band)
    boom = QPainterPath(QPointF(25.0, 4.0))
    boom.cubicTo(QPointF(24.0, 13.0), QPointF(20.0, 15.0 + mic_drop), QPointF(13.0 + mic_wiggle, 14.0 + mic_drop))
    for color, width in ((WHITE, 4.2), (INK, 2.6), (HEADSET, 1.0)):
        p.setPen(QPen(color, width, *ROUND))
        p.drawPath(boom)
    ringed(p, ellipse(12.0 + mic_wiggle, 14.0 + mic_drop, 2.8, 2.4), CUSHION, 1.2, 3.0)
    for side in (-1, 1):
        ringed(p, rounded(side * 25.0 - 4.0, -6.0, 8.0, 13.0, 3.6), HEADSET, 1.5, 4.0)
        outlined(p, rounded(side * 25.0 - 2.4 - side * 1.2, -4.0, 3.0, 9.0, 1.4), CUSHION, 0.8)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(GREEN if led else DIM)
    p.drawEllipse(QPointF(26.4, -3.2), 1.1, 1.1)
    if led:
        glow(p, 26.4, -3.2, 4.0, GREEN, 0.6)
    p.restore()


def _wifi(p: QPainter, x: float, y: float, bars: int, color: QColor, warn: bool) -> None:
    for k, r in enumerate(WIFI_RADII):
        rect = QRectF(x - r, y - r, 2 * r, 2 * r)
        for pen_color, width in ((WHITE, 5.2), (INK, 3.6), (color if k < bars else DIM, 1.8)):
            p.setPen(QPen(pen_color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(rect, 45 * 16, 90 * 16)
    ringed(p, ellipse(x, y - 0.5, 2.2), color if bars > 0 else DIM, 1.2, 3.0)
    if warn:
        lettering(p, x + 11.0, y - 3.0, "!", 10.0, 0.0, YELLOW, 2.0, 0.8)


def _binary_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = BINARY_CLOCK
    second = int(math.floor(elapsed)) % 60
    cm._ink_shape(p, rounded(cx - 18.0, cy - 5.5, 36.0, 11.0, 5.5), SLATE, 1.4, 1.3)
    flash = not reduced and elapsed >= 60 and elapsed % 60 < 0.5
    for i in range(6):
        lit = flash or (second >> (5 - i)) & 1
        x = cx - 12.5 + i * 5.0
        if lit:
            glow(p, x, cy, 3.6, GREEN, 0.55)
        p.setPen(QPen(INK, 0.7))
        p.setBrush(GREEN if lit else SLATE_LIGHT)
        p.drawEllipse(QPointF(x, cy), 1.7, 1.7)
    cm._clock_digits(p, cx - 21.0, cy + 0.4, elapsed)


def _beetle(p: QPainter, x: float, y: float, leg: float) -> None:
    p.save()
    p.translate(x, y)
    p.setPen(QPen(INK, 0.9, *ROUND))
    for side in (-1, 1):
        for k in range(3):
            a = math.radians(side * (60 + k * 30) + leg * (1 if k % 2 else -1))
            p.drawLine(QPointF(side * 1.5, -1.0 + k * 2.0),
                       QPointF(side * 1.5 + math.sin(a) * 3.2 * side, -1.0 + k * 2.0 + math.cos(a) * 1.2))
    outlined(p, ellipse(0, 0.6, 3.2, 3.8), BEETLE, 1.0)
    stroke(p, 0.0, -2.8, 0.0, 4.2, BEETLE_DARK, 0.8)
    outlined(p, ellipse(0, -3.6, 1.9, 1.6), INK, 0.6)
    stroke(p, -0.8, -4.8, -2.2, -6.6, INK, 0.7)
    stroke(p, 0.8, -4.8, 2.2, -6.6, INK, 0.7)
    p.restore()


class IT(Fachgebiet):
    key = "it"
    SCENES = ("build", "bug", "merge")
    CLOCKS = ("binaer",)
    WORDS = (N_("bla"), N_("bla();"), N_("bla"))
    WORD_FILLS = (QColor(comic.YELLOW_HOVER), QColor("#A8E6FF"), QColor("#B6F2A7"))
    ZACK_WORD = N_("Läuft!")
    SILENCE = (N_("Kein Signal"), N_("404: Ton nicht gefunden."))
    CAPTIONS = {
        "build": (N_("kompiliert …"), N_("Build grün!"), 2.3),
        "bug": (N_("Bug-Jagd …"), N_("gefixt!"), 2.4),
        "merge": (N_("wird gemergt …"), N_("gemergt!"), 2.3),
    }
    LOOKS = {
        "build": ((10, 8), "line", "smile"),
        "bug": ((8, 12), "line", "o"),
        "merge": ((10, 6), "line", "smile"),
    }

    def accessory(self, p: QPainter, pose: Pose) -> None:
        dy, angle, led, drop, wiggle = 0.0, 0.0, False, 0.0, 0.0
        if pose.kind == "talk":
            led = True
            if not pose.reduced:
                wiggle = 1.2 * pose.level * math.sin(pose.t * 11.0)
                dy = -0.6 * pose.level * abs(math.sin(pose.t * 8.0))
        elif pose.kind == "shout":
            dy, angle, led = -1.6, (0.0 if pose.reduced else 3.0 * math.sin(pose.t * 31.0)), True
        elif pose.kind == "wink":
            led = True
        elif pose.kind == "sad":
            angle, drop = 6.0, 3.0
        else:
            angle = 0.0 if pose.reduced else 1.0 * math.sin(pose.t * 1.6)
        _headset(p, dy, angle, led, drop, wiggle)

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        bars, color, warn = 3, CYAN, False
        if self.mode == "rec":
            if an.clip:
                color = CODE_RED
            elif an.silent:
                bars, warn = 0, True
            else:
                bars = 3 if self._lv > 0.62 else 2 if self._lv > 0.38 else 1 if self._lv > 0.12 else 0
        elif self.mode == "error":
            bars = 0
        _wifi(p, WIFI_AT.x(), WIFI_AT.y(), bars, color, warn)

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _binary_clock(p, elapsed, reduced)

    @staticmethod
    def _window(p: QPainter, x0: float, y0: float, w: float, h: float) -> None:
        frame = rounded(x0, y0, w, h, 3.0)
        cm._ink_shape(p, frame, SLATE, 1.6, 1.4)
        p.save()
        p.setClipPath(frame)
        p.fillRect(QRectF(x0, y0, w, 6.0), SLATE_LIGHT)
        p.restore()
        p.setPen(Qt.PenStyle.NoPen)
        for k, color in enumerate((CODE_RED, ORANGE, GREEN)):
            p.setBrush(color)
            p.drawEllipse(QPointF(x0 + 4.0 + k * 3.6, y0 + 3.0), 1.1, 1.1)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(INK, 1.6, *ROUND))
        p.drawPath(frame)

    def scene_build(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, w, h = 100.0, 10.0, 42.0, 36.0
        at = self.payoff("build")
        self._window(p, x0, y0, w, h)
        p.save()
        p.setClipRect(QRectF(x0 + 2.0, y0 + 7.0, w - 4.0, h - 19.0))
        scroll = 0.0 if reduced else (e * 9.0) % 4.4
        for k, color in enumerate(CODE_COLORS):
            y = y0 + 10.0 + k * 4.4 - scroll
            x = x0 + 4.0 + (k % 3) * 3.0
            length = 8.0 + ((k * 7) % 5) * 4.0
            stroke(p, x, y, x + length, y, color, 1.5)
            stroke(p, x + length + 2.5, y, x + length + 7.0, y, faded(WHITE, 0.6), 1.5)
        p.restore()
        done = 1.0 if reduced else clamp(e / (at - 0.1), 0.0, 1.0)
        bar = rounded(x0 + 4.0, y0 + h - 9.0, w - 8.0, 5.0, 2.5)
        outlined(p, bar, SLATE_LIGHT, 1.0)
        if done > 0:
            p.save()
            p.setClipPath(bar)
            p.fillRect(QRectF(x0 + 4.0, y0 + h - 9.0, (w - 8.0) * done, 5.0), GREEN if e >= at else CYAN)
            p.restore()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(INK, 1.0))
            p.drawPath(bar)
        if e >= at:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.2, 0.0, 1.0))
            p.save()
            p.translate(x0 + w - 3.0, y0 + h - 3.0)
            p.scale(pop, pop)
            badge_check(p, 0.0, 0.0, 5.4, GREEN, WHITE)
            p.restore()
        elif not reduced:
            p.save()
            p.translate(x0 + w - 6.0, y0 + 3.0)
            p.rotate(e * 576.0)
            p.setPen(QPen(WHITE, 1.1, *ROUND))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(-2.0, -2.0, 4.0, 4.0), 0, 270 * 16)
            p.restore()

    def scene_bug(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, w, h = 100.0, 10.0, 42.0, 36.0
        at = self.payoff("bug")
        self._window(p, x0, y0, w, h)
        for k in range(5):
            y = y0 + 11.0 + k * 5.2
            x = x0 + 4.0 + (k % 2) * 3.0
            stroke(p, x, y, x + 12.0 + ((k * 5) % 4) * 5.0, y, CODE_COLORS[k], 1.5)
        caught = reduced or e >= at
        if caught:
            bx, by = x0 + 27.0, y0 + 21.5
        else:
            u = e / at
            bx = x0 + 9.0 + 24.0 * (0.5 + 0.5 * math.sin(u * 5.2))
            by = y0 + 13.0 + 18.0 * u + math.sin(e * 7.0) * 1.5
        if not caught:
            _beetle(p, bx, by, math.sin(e * 30.0) * 12.0)
            lx = bx + math.sin(e * 3.0) * 4.0
            ly = by - 1.0
            for color, width in ((WHITE, 4.0), (INK, 2.6)):
                p.setPen(QPen(color, width, *ROUND))
                p.drawLine(QPointF(lx + 6.0, ly + 6.0), QPointF(lx + 11.0, ly + 11.0))
            p.setPen(QPen(INK, 1.6))
            p.setBrush(faded(LENS, 0.35))
            p.drawEllipse(QPointF(lx + 1.0, ly + 1.0), 6.6, 6.6)
        else:
            k = 1.0 if reduced else clamp((e - at) / 0.3, 0.0, 1.0)
            if k < 1.0:
                cm._puff(p, bx, by, 3.0 + 4.0 * k, 1.0 - k, WHITE)
            p.save()
            p.translate(bx, by)
            pop = 1.0 if reduced else EASE_OUT(k)
            p.scale(pop, pop)
            badge_check(p, 0.0, 0.0, 5.2, GREEN, WHITE)
            p.restore()

    def scene_merge(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, x1, y = 101.0, 143.0, 22.0
        at = self.payoff("merge")
        main_k = 1.0 if reduced else clamp(e / (at - 0.15), 0.0, 1.0)
        trunk = QPainterPath(QPointF(x0, y))
        trunk.lineTo(x0 + (x1 - x0) * main_k, y)
        ringed_line(p, trunk, CYAN, 1.8, 4.4)
        points = branch_points(x0, x1, y)
        branch_k = 1.0 if reduced else clamp((e - 0.3) / (at - 0.5), 0.0, 1.0)
        shown = int(round(branch_k * (len(points) - 1)))
        if shown >= 1:
            path = QPainterPath(points[0])
            for point in points[1:shown + 1]:
                path.lineTo(point)
            ringed_line(p, path, ORANGE, 1.8, 4.4)
        for u in (0.0, 0.3, 0.55):
            if main_k >= u:
                outlined(p, ellipse(x0 + 2.0 + (x1 - x0 - 6.0) * u, y, 2.6), CYAN, 1.1)
        for index in (BRANCH_STEPS // 2, BRANCH_STEPS + BRANCH_STEPS // 3):
            if shown >= index:
                outlined(p, ellipse(points[index].x(), points[index].y(), 2.4), ORANGE, 1.1)
        if e >= at:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.2, 0.0, 1.0))
            p.save()
            p.translate(x1 - 4.0, y)
            p.scale(pop, pop)
            badge_check(p, 0.0, 0.0, 4.4, GREEN, WHITE)
            p.restore()
            sparkle(p, x1 - 2.0, y - 9.0, 3.0 * twinkle(e, reduced), WHITE)

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        fills = (CYAN, QColor(comic.YELLOW_HOVER), GREEN, QColor(comic.YELLOW_HOVER))

        def draw(pp, x, y, size, moment, j):
            lettering(pp, x, y, GLYPHS[j], 9.0 * size, math.sin(moment * 6 + j) * 10, fills[j], 2.2, 1.0)
        fly_out(p, t, f, k, draw, GLYPH_ROUTES)

    def error_decor(self, p: QPainter, left: float, top: float) -> None:
        _beetle(p, left + 10.0, top + 2.0, 20.0)
