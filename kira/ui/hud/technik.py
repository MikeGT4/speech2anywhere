# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_OUT, Frame, clamp
from kira.ui.hud.fachgebiet import FLY_ROUTES, Fachgebiet, badge_check, fly_out, lettering, outlined, rounded, stroke
from kira.ui.hud.saison import CLOUD, INK, ROUND, SMOKE, STEEL, WHITE, YELLOW, Pose, ellipse, faded, glow, polygon
from kira.ui.hud.weihnachten import _bubble_path
from kira.texte import N_

HELMET = QColor("#FF8A1F")
HELMET_DARK = QColor("#D9620B")
HELMET_LIGHT = QColor("#FFB266")
BLUEPRINT = QColor("#1F5FAF")
BLUEPRINT_LINE = QColor("#DCEBFF")
METER_CASE = QColor("#3B4651")
METER_FACE = QColor("#FFF8E8")
METER_RED = QColor("#E5484D")
METER_IDLE = QColor("#5B6A78")
NUCLEUS_RED = QColor("#E5484D")
NUCLEUS_BLUE = QColor("#3B82C4")
FIN = QColor("#1F5FAF")
FLAME = QColor("#FF8A1F")
WINDOW = QColor("#BFE3FF")
HANDLE = QColor("#FF8A1F")
COLD_BULB = QColor("#EEF3F6")

METER_AT = QPointF(83.0, 64.0)
ATOM_CLOCK = (245.0, 14.0)
HELMET_AT = (35.0, 21.5)
LAUNCH_PAD_Y = 50.0


def _helmet(p: QPainter, x: float, y: float, angle: float, lamp: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    dome = QPainterPath(QPointF(-16.0, 0.0))
    dome.cubicTo(QPointF(-16.0, -12.0), QPointF(-7.0, -15.5), QPointF(0.0, -15.5))
    dome.cubicTo(QPointF(7.0, -15.5), QPointF(16.0, -12.0), QPointF(16.0, 0.0))
    dome.closeSubpath()
    brim = rounded(-20.0, -1.6, 40.0, 4.2, 2.1)
    both = QPainterPath()
    both.addPath(dome)
    both.addPath(brim)
    both.setFillRule(Qt.FillRule.WindingFill)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(WHITE, 4.0, *ROUND))
    p.drawPath(both)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPath(both.translated(1.2, 1.2))
    outlined(p, dome, HELMET, 1.6)
    p.save()
    p.setClipPath(dome)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(HELMET_LIGHT, 1.4, *ROUND))
    shine = QPainterPath(QPointF(-11.0, -4.0))
    shine.cubicTo(QPointF(-10.0, -9.0), QPointF(-6.5, -12.0), QPointF(-2.5, -12.8))
    p.drawPath(shine)
    p.setPen(QPen(HELMET_DARK, 2.6, *ROUND))
    p.drawLine(QPointF(0.0, -15.5), QPointF(0.0, -1.0))
    p.restore()
    stroke(p, 0.0, -15.0, 0.0, -1.0, INK, 0.8)
    outlined(p, brim, HELMET_DARK, 1.5)
    if lamp > 0:
        glow(p, 0.0, -6.5, 7.0, YELLOW, 0.6 * lamp)
    outlined(p, ellipse(0.0, -6.5, 2.6, 2.3), YELLOW if lamp > 0 else STEEL, 1.0)
    p.restore()


def _meter(p: QPainter, x: float, y: float, needle: float, alarm: bool) -> None:
    p.save()
    p.translate(x, y)
    cm._ink_shape(p, rounded(-12.0, -9.0, 24.0, 17.0, 3.0), METER_CASE, 1.5, 1.3)
    face = rounded(-10.0, -7.4, 20.0, 12.0, 2.0)
    outlined(p, face, METER_FACE, 0.9)
    p.save()
    p.setClipPath(face)
    for k in range(9):
        a = math.radians(-135 + k * 11.25)
        inner, outer = 8.6, 10.4 if k % 2 == 0 else 9.6
        stroke(p, math.cos(a) * inner, 5.0 + math.sin(a) * inner, math.cos(a) * outer, 5.0 + math.sin(a) * outer,
               METER_RED if k >= 7 else INK, 0.8)
    a = math.radians(-135 + needle * 90)
    stroke(p, 0.0, 5.0, math.cos(a) * 9.4, 5.0 + math.sin(a) * 9.4, METER_RED if alarm else INK, 1.1)
    p.restore()
    outlined(p, ellipse(0.0, 5.0, 1.4), INK, 0.6)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(METER_RED if alarm else METER_IDLE)
    p.drawEllipse(QPointF(8.6, 6.0), 1.0, 1.0)
    p.restore()


def _atom(p: QPainter, cx: float, cy: float, r: float, phases: tuple[float, float, float], flash: float = 0.0) -> None:
    for k in range(3):
        p.save()
        p.translate(cx, cy)
        p.rotate(k * 60.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(WHITE, 2.8))
        p.drawPath(ellipse(0, 0, r, r * 0.38))
        p.setPen(QPen(INK, 1.1))
        p.drawPath(ellipse(0, 0, r, r * 0.38))
        p.restore()
    if flash > 0:
        glow(p, cx, cy, r * 1.4, YELLOW, 0.6 * flash)
    for k, phase in enumerate(phases):
        a = math.radians(k * 60.0)
        ex, ey = math.cos(phase) * r, math.sin(phase) * r * 0.38
        outlined(p, ellipse(cx + ex * math.cos(a) - ey * math.sin(a), cy + ex * math.sin(a) + ey * math.cos(a), 1.7),
                 YELLOW, 0.9)
    outlined(p, ellipse(cx - 1.0, cy - 0.6, 2.2), NUCLEUS_RED, 0.9)
    outlined(p, ellipse(cx + 1.2, cy + 0.8, 2.2), NUCLEUS_BLUE, 0.9)


def _atom_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = ATOM_CLOCK
    frac = elapsed - math.floor(elapsed)
    phases = (0.6, 2.4, 4.4) if reduced else (2 * math.pi * frac, elapsed * 2.6 + 2.0, elapsed * 1.7 + 4.0)
    since = elapsed % 60
    flash = math.sin(since / 0.6 * math.pi) if not reduced and elapsed >= 60 and since < 0.6 else 0.0
    _atom(p, cx, cy, 9.0, phases, flash)
    cm._clock_digits(p, cx - 11.5, cy + 0.4, elapsed)


def _bolt(x: float, y: float, s: float) -> QPainterPath:
    return polygon(((x - 1.0, y - 6.0 * s), (x + 3.0 * s, y - 6.0 * s), (x + 0.6, y - 0.6), (x + 3.6 * s, y - 0.6),
                    (x - 2.4 * s, y + 7.0 * s), (x - 0.4, y + 0.8), (x - 3.4 * s, y + 0.8)))


class Technik(Fachgebiet):
    key = "technik"
    SCENES = ("rakete", "bauplan", "gluehbirne")
    CLOCKS = ("atomuhr",)
    WORDS = (N_("bla"), N_("bzzt!"), N_("bla"))
    WORD_FILLS = (QColor(comic.YELLOW_HOVER), QColor("#BFE3FF"), QColor("#FFC98A"))
    ZACK_WORD = N_("Heureka!")
    SILENCE = (N_("Kein Signal"), N_("Funkstille im Mikrofon."))
    CAPTIONS = {
        "rakete": (N_("Countdown …"), N_("abgehoben!"), 2.3),
        "bauplan": (N_("zeichnet …"), N_("maßgenau!"), 2.4),
        "gluehbirne": (N_("zündet …"), N_("Geistesblitz!"), 2.4),
    }
    LOOKS = {
        "rakete": ((8, -6), "line", "o"),
        "bauplan": ((10, 10), "line", "smile"),
        "gluehbirne": ((8, -8), "line", "o"),
    }

    def __init__(self) -> None:
        super().__init__()
        self._needle = 0.0

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        super().step(t, dt, f, tap, an)
        target = 0.0
        if self.mode == "rec" and not an.silent:
            target = 1.0 if an.clip else clamp(self._lv * 0.95, 0.0, 0.86)
        tau = 0.08 if target > self._needle else 0.3
        self._needle += (target - self._needle) * min(1.0, dt / tau)

    def accessory(self, p: QPainter, pose: Pose) -> None:
        angle, dy, lamp = -6.0, 0.0, 0.0
        if pose.kind == "talk":
            if not pose.reduced:
                angle = -6.0 + 3.0 * pose.level * math.sin(pose.t * 8.0)
                dy = -0.6 * pose.level * abs(math.sin(pose.t * 8.0))
        elif pose.kind == "shout":
            angle = -14.0 + (0.0 if pose.reduced else 5.0 * math.sin(pose.t * 31.0))
        elif pose.kind == "wink":
            angle, lamp = -10.0, 1.0
        elif pose.kind == "sad":
            angle, dy = 12.0, 2.2
        else:
            angle = 2.0 + (0.0 if pose.reduced else 1.5 * math.sin(pose.t * 1.6))
            if pose.kind == "look":
                angle += pose.look[0] * 0.2
                lamp = 0.6
        _helmet(p, HELMET_AT[0], HELMET_AT[1] + dy, angle, lamp)

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        jitter = 0.0
        if self.mode == "rec" and not f.reduced and not an.silent:
            jitter = 0.03 * math.sin(t * 41.0) * self._lv
        _meter(p, METER_AT.x(), METER_AT.y(), clamp(self._needle + jitter, 0.0, 1.0), self.mode == "rec" and an.clip)

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _atom_clock(p, elapsed, reduced)

    def scene_rakete(self, p: QPainter, e: float, reduced: bool) -> None:
        cx = 124.0
        at = self.payoff("rakete")
        climb = clamp((e - at) / 0.9, 0.0, 1.0)
        lift = 0.0 if e < at else (60.0 if reduced else 70.0 * climb * climb)
        p.save()
        p.setClipPath(cm._cloud(CLOUD))
        stroke(p, cx - 13.0, LAUNCH_PAD_Y, cx + 13.0, LAUNCH_PAD_Y, INK, 2.0)
        if e < at and not reduced:
            for j in range(3):
                age = (e * 1.6 + j / 3) % 1.0
                cm._puff(p, cx - 6.0 + j * 6.0 + (age - 0.5) * 8, LAUNCH_PAD_Y - 2.0 - age * 3.0,
                         1.6 + age * 2.6 * (e / at), (1.0 - age) * clamp(e / at, 0.2, 1.0), SMOKE)
        elif e >= at:
            for j in range(4):
                age = 0.5 if reduced else ((e - at) * 1.2 + j / 4) % 1.0
                fade = 1.0 - clamp((age - 0.5) / 0.5, 0.0, 1.0)
                cm._puff(p, cx - 9.0 + j * 6.0, LAUNCH_PAD_Y - 2.0 - age * 4.0, 2.4 + age * 3.0, fade, SMOKE)
        shake = 0.0 if reduced or e >= at else math.sin(e * 60) * 0.5 * clamp(e / at, 0.0, 1.0)
        p.translate(cx + shake, LAUNCH_PAD_Y - 3.0 - lift)
        if e >= at or (not reduced and e > at - 0.6):
            flicker = 1.0 if reduced else 0.8 + 0.2 * math.sin(e * 40)
            flame = QPainterPath(QPointF(-3.0, 0.0))
            flame.quadTo(QPointF(0.0, 9.0 * flicker), QPointF(3.0, 0.0))
            flame.closeSubpath()
            outlined(p, flame, FLAME, 1.0)
        for side in (-1, 1):
            fin = polygon(((side * 3.6, -8.0), (side * 7.6, -1.0), (side * 7.6, 0.6), (side * 3.6, -1.6)))
            outlined(p, fin, FIN, 1.1)
        body = QPainterPath(QPointF(-3.8, 0.0))
        body.lineTo(-3.8, -14.0)
        body.cubicTo(QPointF(-3.8, -19.0), QPointF(0.0, -23.0), QPointF(0.0, -23.0))
        body.cubicTo(QPointF(0.0, -23.0), QPointF(3.8, -19.0), QPointF(3.8, -14.0))
        body.lineTo(3.8, 0.0)
        body.closeSubpath()
        cm._ink_shape(p, body, WHITE, 1.4, 1.2)
        outlined(p, ellipse(0.0, -13.0, 2.0), WINDOW, 0.9)
        p.restore()
        if e < at and not reduced:
            count = 3 - int(e / (at / 3.0))
            if count >= 1:
                lettering(p, 106.0, 26.0, str(count), 13.0, -8.0, WHITE, 2.2, 1.0)

    def scene_bauplan(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, w, h = 100.0, 10.0, 42.0, 38.0
        at = self.payoff("bauplan")
        sheet = rounded(x0, y0, w, h, 2.5)
        cm._ink_shape(p, sheet, BLUEPRINT, 1.6, 1.4)
        p.save()
        p.setClipPath(sheet)
        p.setPen(QPen(faded(BLUEPRINT_LINE, 0.18), 0.6))
        for k in range(1, 9):
            p.drawLine(QPointF(x0 + k * 5.0, y0), QPointF(x0 + k * 5.0, y0 + h))
        for k in range(1, 8):
            p.drawLine(QPointF(x0, y0 + k * 5.0), QPointF(x0 + w, y0 + k * 5.0))
        p.restore()
        drawn = 1.0 if reduced else clamp(e / (at - 0.2), 0.0, 1.0)
        bubble = _bubble_path(x0 + w / 2 - 3.0, y0 + h / 2 - 1.0, 0.055)
        box = bubble.boundingRect()
        p.save()
        p.setClipRect(QRectF(box.left() - 2.0, box.top() - 2.0, (box.width() + 4.0) * drawn, box.height() + 4.0))
        p.setPen(QPen(BLUEPRINT_LINE, 1.1, *ROUND))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bubble)
        p.restore()
        if drawn > 0.5:
            k = clamp((drawn - 0.5) * 2.0, 0.0, 1.0)
            p.setPen(QPen(faded(BLUEPRINT_LINE, k), 0.8))
            low = box.bottom() + 3.0
            p.drawLine(QPointF(box.left(), low), QPointF(box.right(), low))
            for xx, s in ((box.left(), 1), (box.right(), -1)):
                p.drawLine(QPointF(xx, low), QPointF(xx + s * 2.2, low - 1.3))
                p.drawLine(QPointF(xx, low), QPointF(xx + s * 2.2, low + 1.3))
            side = box.right() + 3.0
            p.drawLine(QPointF(side, box.top()), QPointF(side, box.bottom()))
            for yy, s in ((box.top(), 1), (box.bottom(), -1)):
                p.drawLine(QPointF(side, yy), QPointF(side - 1.3, yy + s * 2.2))
                p.drawLine(QPointF(side, yy), QPointF(side + 1.3, yy + s * 2.2))
        if e >= at:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.2, 0.0, 1.0))
            p.save()
            p.translate(x0 + w - 4.0, y0 + h - 4.0)
            p.scale(pop, pop)
            badge_check(p, 0.0, 0.0, 5.2, WHITE, BLUEPRINT)
            p.restore()

    def scene_gluehbirne(self, p: QPainter, e: float, reduced: bool) -> None:
        cx, cy = 121.0, 26.0
        at = self.payoff("gluehbirne")
        heat = 1.0 if reduced else clamp(e / at, 0.0, 1.0)
        lit = e >= at
        flicker = 1.0 if reduced or lit else 0.65 + 0.35 * abs(math.sin(e * 23.0) * math.sin(e * 7.0))
        if heat > 0.2:
            glow(p, cx, cy, 16.0 + 8.0 * heat, YELLOW, (0.25 + 0.45 * heat) * flicker)
        if lit:
            for k in range(7):
                a = math.radians(-90 + (k - 3) * 30)
                outer = 19.0 + (0.0 if reduced else 1.5 * math.sin(e * 8 + k))
                stroke(p, cx + math.cos(a) * 15.0, cy + math.sin(a) * 15.0, cx + math.cos(a) * outer,
                       cy + math.sin(a) * outer, INK, 1.6)
        bulb = QPainterPath(QPointF(cx - 5.0, cy + 12.0))
        bulb.cubicTo(QPointF(cx - 5.0, cy + 6.0), QPointF(cx - 11.0, cy + 4.0), QPointF(cx - 11.0, cy - 2.0))
        bulb.cubicTo(QPointF(cx - 11.0, cy - 9.0), QPointF(cx - 6.0, cy - 13.0), QPointF(cx, cy - 13.0))
        bulb.cubicTo(QPointF(cx + 6.0, cy - 13.0), QPointF(cx + 11.0, cy - 9.0), QPointF(cx + 11.0, cy - 2.0))
        bulb.cubicTo(QPointF(cx + 11.0, cy + 4.0), QPointF(cx + 5.0, cy + 6.0), QPointF(cx + 5.0, cy + 12.0))
        bulb.closeSubpath()
        glass = QColor(int(235 + 20 * heat), int(240 + 6 * heat * flicker), int(235 - 60 * heat * flicker))
        cm._ink_shape(p, bulb, glass if heat > 0.05 else COLD_BULB, 1.6, 1.4)
        filament = QPainterPath(QPointF(cx - 3.0, cy + 10.0))
        filament.lineTo(cx - 3.0, cy + 1.0)
        for k in range(5):
            filament.lineTo(cx - 3.0 + (k + 0.5) * 1.2, cy - 1.5 + (k % 2) * 2.4)
        filament.lineTo(cx + 3.0, cy + 1.0)
        filament.lineTo(cx + 3.0, cy + 10.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(int(120 + 135 * heat), int(60 + 150 * heat * flicker), int(30 + 30 * heat)), 1.1, *ROUND))
        p.drawPath(filament)
        for k in range(3):
            outlined(p, rounded(cx - 5.4 + k * 0.4, cy + 12.0 + k * 2.6, 10.8 - k * 0.8, 2.6, 1.0), STEEL, 1.0)
        outlined(p, ellipse(cx, cy + 20.5, 2.2, 1.4), INK, 0.6)

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        def draw(pp, x, y, size, moment, j):
            if j % 2 == 0:
                _atom(pp, x, y, 4.6 * size, (moment * 7 + j, moment * 5 + 2, moment * 4 + 4))
            else:
                cm._ink_shape(pp, _bolt(x, y, size * 0.9), YELLOW, 1.2, 1.0)
        fly_out(p, t, f, k, draw, FLY_ROUTES)

    def error_decor(self, p: QPainter, left: float, top: float) -> None:
        p.translate(left + 9.0, top + 2.0)
        p.rotate(-40)
        outlined(p, rounded(-2.4, 2.0, 4.8, 9.0, 2.0), HANDLE, 1.2)
        stroke(p, 0.0, -7.0, 0.0, 2.0, INK, 2.6)
        stroke(p, 0.0, -7.0, 0.0, 2.0, STEEL, 1.2)
        stroke(p, -1.0, -7.2, 1.0, -7.2, INK, 1.2)
