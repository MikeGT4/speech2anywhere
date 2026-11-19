# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from kira.ui.hud.base import EASE_OUT, clamp
from kira.ui.hud.comic import TILE
from kira.ui.hud.fachgebiet import (
    EDEL_GOLD, EDEL_GOLD_LIGHT, EDEL_IVORY, HAIRLINE, Edel, badge_check, brass_brush, drop_shadow, filled,
    linear_brush, mono_digits, radial_brush, rounded,
)
from kira.ui.hud.saison import ROUND, WHITE, Pose, ellipse, faded, sparkle
from kira.texte import N_

AMBER_LIGHT = QColor("#E6A04A")
AMBER = QColor("#B5641C")
AMBER_DEEP = QColor("#6E3510")
AMBER_EDGE = QColor("#3A1A08")
RUBBER_LIGHT = QColor("#4A4A4E")
RUBBER = QColor("#2B2B2E")
LABEL_PAPER = QColor("#F3EBDD")
LABEL_INK = QColor("#7A5A3A")
LINEN_LIGHT = QColor("#FBF9F4")
LINEN = QColor("#ECE6DA")
GLASS = QColor(226, 240, 246, 150)
GLASS_EDGE = QColor("#5A6A72")
TUBE_LIGHT = QColor(220, 235, 240, 220)
TUBE_SHADE = QColor(170, 190, 200, 220)
PHARMA_GREEN = QColor("#1F7A5E")

BOTTLE_TOP = 36.0
CYLINDER_CLOCK = (245.0, 14.0)


def amber_glass(x0: float, x1: float):
    return linear_brush(x0, 0, x1, 0, ((0.0, AMBER_DEEP), (0.3, AMBER_LIGHT), (0.6, AMBER), (1.0, AMBER_DEEP)))


def amber_liquid(x0: float, x1: float):
    return linear_brush(x0, 0, x1, 0, ((0.0, AMBER_DEEP), (0.4, AMBER_LIGHT), (1.0, AMBER)))


def _bottle_path(x0: float, x1: float, neck_l: float, neck_r: float, top: float, shoulder: float,
                 bottom: float) -> QPainterPath:
    path = QPainterPath(QPointF(x0, shoulder + 6.0))
    path.cubicTo(QPointF(x0, shoulder + 2.0), QPointF(neck_l - 4.0, shoulder), QPointF(neck_l, shoulder))
    path.lineTo(neck_l, top)
    path.lineTo(neck_r, top)
    path.lineTo(neck_r, shoulder)
    path.cubicTo(QPointF(neck_r + 4.0, shoulder), QPointF(x1, shoulder + 2.0), QPointF(x1, shoulder + 6.0))
    path.lineTo(x1, bottom - 2.0)
    path.cubicTo(QPointF(x1, bottom), QPointF(x0, bottom), QPointF(x0, bottom - 2.0))
    path.closeSubpath()
    return path


def _drop(p: QPainter, x: float, y: float, size: float) -> None:
    drop = QPainterPath(QPointF(x, y - 2.4 * size))
    drop.cubicTo(QPointF(x + 1.5 * size, y - 0.4), QPointF(x + 1.5 * size, y + 1.4 * size), QPointF(x, y + 1.5 * size))
    drop.cubicTo(QPointF(x - 1.5 * size, y + 1.4 * size), QPointF(x - 1.5 * size, y - 0.4), QPointF(x, y - 2.4 * size))
    filled(p, drop, linear_brush(x - 1, y - 2, x + 1, y + 2, ((0.0, AMBER_LIGHT), (1.0, AMBER))), AMBER_EDGE, 0.5)


def _pipette(p: QPainter, x: float, y: float, squeeze: float, tube: float = 12.0) -> None:
    p.save()
    p.translate(x, y)
    filled(p, rounded(-1.6, 6.0, 3.2, tube, 1.2), linear_brush(-1.6, 0, 1.6, 0, ((0.0, TUBE_LIGHT), (1.0, TUBE_SHADE))),
           GLASS_EDGE, 0.5)
    filled(p, rounded(-3.6, 4.0, 7.2, 3.0, 1.0), brass_brush(-3.6, 4, 3.6, 7))
    bulb = QPainterPath(QPointF(-4.6, 4.2))
    bulb.cubicTo(QPointF(-5.4 - squeeze, -3.0), QPointF(-3.0, -6.6), QPointF(0.0, -6.6))
    bulb.cubicTo(QPointF(3.0, -6.6), QPointF(5.4 + squeeze, -3.0), QPointF(4.6, 4.2))
    bulb.closeSubpath()
    filled(p, bulb, linear_brush(-5, 0, 5, 0, ((0.0, RUBBER_LIGHT), (0.4, QColor("#3A3A3E")), (1.0, RUBBER))))
    p.setPen(QPen(QColor(255, 255, 255, 80), 0.8, *ROUND))
    p.drawLine(QPointF(-2.6, -3.0), QPointF(-2.8, 1.6))
    p.restore()


def _beaker(p: QPainter, cx: float, top: float, bottom: float, half: float) -> QPainterPath:
    glass = QPainterPath(QPointF(cx - half - 1.6, top))
    glass.lineTo(cx - half, top + 1.6)
    glass.lineTo(cx - half, bottom - 2.0)
    glass.quadTo(QPointF(cx - half, bottom), QPointF(cx - half + 2.0, bottom))
    glass.lineTo(cx + half - 2.0, bottom)
    glass.quadTo(QPointF(cx + half, bottom), QPointF(cx + half, bottom - 2.0))
    glass.lineTo(cx + half, top)
    glass.closeSubpath()
    drop_shadow(p, glass, 1.2, 1.6, 0.2)
    filled(p, glass, GLASS, GLASS_EDGE, 0.8)
    return glass


def _cylinder_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = CYLINDER_CLOCK
    u = ((math.floor(elapsed) if reduced else elapsed) % 60) / 60
    filled(p, ellipse(cx, cy + 9.6, 6.4, 1.8), brass_brush(cx - 6, cy + 8, cx + 6, cy + 11), HAIRLINE, 0.6)
    tube = rounded(cx - 4.4, cy - 9.6, 8.8, 19.0, 2.4)
    drop_shadow(p, tube, 1.0, 1.4, 0.25)
    filled(p, tube, GLASS, GLASS_EDGE, 0.8)
    level = cy + 8.6 - 16.4 * u
    p.save()
    p.setClipPath(tube)
    p.fillRect(QRectF(cx - 5.0, level, 10.0, cy + 10.0 - level), amber_liquid(cx - 4.0, cx + 4.0))
    p.setPen(QPen(faded(WHITE, 0.8), 0.6))
    p.drawLine(QPointF(cx - 4.0, level + 0.4), QPointF(cx + 4.0, level + 0.4))
    p.restore()
    p.setPen(QPen(HAIRLINE, 0.5))
    for k in range(6):
        y = cy + 6.0 - k * 3.0
        p.drawLine(QPointF(cx - 4.4, y), QPointF(cx - 2.2 if k % 2 else cx - 1.2, y))
    p.setPen(QPen(faded(WHITE, 0.85), 0.9, *ROUND))
    p.drawLine(QPointF(cx + 2.6, cy - 7.6), QPointF(cx + 2.6, cy + 6.0))
    since = elapsed % 60
    if not reduced and elapsed >= 60 and since < 0.6:
        sparkle(p, cx + 5.5, cy - 9.0, 3.0 * math.sin(since / 0.6 * math.pi), WHITE)
    mono_digits(p, cx - 8.0, cy + 0.4, elapsed)


def dropper(pose: Pose) -> tuple[float, float]:
    t = 0.0 if pose.reduced else pose.t
    if pose.kind == "talk" and not pose.reduced:
        return pose.level * max(0.0, math.sin(t * 5.0)), (t * (0.8 + 1.6 * pose.level)) % 1.0
    if pose.kind in ("think", "look") and not pose.reduced:
        return 0.0, (t * 0.6) % 1.0
    if pose.kind == "shout":
        return 1.0, 0.5 if pose.reduced else (t * 4.0) % 1.0
    if pose.kind == "wink":
        return 0.0, 0.85
    return 0.0, -1.0


class Medikamente(Edel):
    key = "medikamente"
    SCENES = ("dosieren", "etikett", "mischen")
    CLOCKS = ("messzylinder",)
    WORDS = (N_("bla"), N_("schluck!"), N_("bla"))
    WORD_FILLS = (EDEL_IVORY, QColor("#F2C27A"), QColor("#CFE9DF"))
    ZACK_WORD = N_("Wirkt!")
    SILENCE = (N_("Kein Signal"), N_("Kein Wirkstoff im Mikrofon."))
    INK_COLOR = QColor("#1F4D44")
    CAPTIONS = {
        "dosieren": (N_("wird dosiert …"), N_("genau dosiert!"), 2.4),
        "etikett": (N_("wird beschriftet …"), N_("beschriftet!"), 2.4),
        "mischen": (N_("wird gerührt …"), N_("klar gelöst!"), 2.4),
    }
    LOOKS = {
        "dosieren": ((10, 10), "line", "smile"),
        "etikett": ((10, 8), "line", "smile"),
        "mischen": ((8, 10), "line", "o"),
    }

    def tile(self, p: QPainter, pose: Pose) -> None:
        p.fillRect(TILE, radial_brush(30, 28, 52, ((0.0, LINEN_LIGHT), (1.0, LINEN))))
        bottle = _bottle_path(22.0, 48.0, 30.0, 40.0, BOTTLE_TOP, 40.0, 68.0)
        drop_shadow(p, bottle, 2.0, 2.0, 0.25)
        filled(p, bottle, amber_glass(22.0, 48.0), AMBER_EDGE, 0.8)
        filled(p, rounded(24.5, 49.0, 21.0, 12.0, 1.0), LABEL_PAPER, LABEL_INK, 0.6)
        p.setPen(QPen(LABEL_INK, 0.6))
        p.drawLine(QPointF(27.0, 53.0), QPointF(43.0, 53.0))
        p.drawLine(QPointF(27.0, 56.6), QPointF(38.0, 56.6))
        p.setPen(QPen(QColor(255, 255, 255, 150), 1.2, *ROUND))
        p.drawLine(QPointF(25.0, 45.0), QPointF(25.4, 64.0))

    def accessory(self, p: QPainter, pose: Pose) -> None:
        if pose.kind == "sad":
            cap = linear_brush(0, 31, 0, 37, ((0.0, RUBBER_LIGHT), (1.0, RUBBER)))
            filled(p, rounded(29.0, 31.0, 12.0, 6.0, 1.4), cap)
            return
        squeeze, fall = dropper(pose)
        _pipette(p, 35.0, 12.0, squeeze)
        if fall >= 0.0:
            _drop(p, 35.0, 30.5 + fall * 7.0, 1.0 + 0.6 * min(1.0, fall * 2.0))
        if pose.kind == "wink":
            sparkle(p, 49.0, 30.0, 2.8, WHITE)

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _cylinder_clock(p, elapsed, reduced)

    def scene_dosieren(self, p: QPainter, e: float, reduced: bool) -> None:
        cx = 121.0
        at = self.payoff("dosieren")
        top, bottom = 30.0, 52.0
        glass = _beaker(p, cx, top, bottom, 13.0)
        fill = 1.0 if reduced else clamp(e / at, 0.0, 1.0)
        level = bottom - 2.0 - (bottom - top - 8.0) * (0.25 + 0.75 * fill)
        mark = bottom - 2.0 - (bottom - top - 8.0)
        p.save()
        p.setClipPath(glass)
        p.fillRect(QRectF(cx - 14.0, level, 28.0, bottom - level + 1.0), amber_liquid(cx - 13.0, cx + 13.0))
        p.setPen(QPen(faded(WHITE, 0.8), 0.6))
        p.drawLine(QPointF(cx - 12.6, level + 0.4), QPointF(cx + 12.6, level + 0.4))
        p.restore()
        p.setPen(QPen(HAIRLINE, 0.5))
        for k in range(5):
            y = bottom - 4.0 - k * 4.0
            p.drawLine(QPointF(cx + 13.0, y), QPointF(cx + 10.4 if k % 2 else cx + 9.0, y))
        p.setPen(QPen(EDEL_GOLD, 1.2))
        p.drawLine(QPointF(cx - 13.0, mark), QPointF(cx + 13.0, mark))
        _pipette(p, cx - 2.0, 13.0, 0.0 if reduced else 0.5 * max(0.0, math.sin(e * 9.0)), 8.0)
        if not reduced and e < at:
            fall = (e % 0.35) / 0.35
            _drop(p, cx - 2.0, 29.5 + fall * (level - 31.0), 0.9)
        if e >= at:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.2, 0.0, 1.0))
            p.save()
            p.translate(cx + 15.0, top + 2.0)
            p.scale(pop, pop)
            badge_check(p, 0.0, 0.0, 4.6, WHITE, PHARMA_GREEN)
            p.restore()

    def scene_etikett(self, p: QPainter, e: float, reduced: bool) -> None:
        at = self.payoff("etikett")
        bottle = _bottle_path(109.0, 133.0, 116.0, 126.0, 8.0, 14.0, 52.0)
        drop_shadow(p, bottle, 1.6, 1.8, 0.25)
        filled(p, bottle, amber_glass(109.0, 133.0), AMBER_EDGE, 0.8)
        filled(p, rounded(115.0, 4.0, 12.0, 5.0, 1.2), linear_brush(0, 4, 0, 9, ((0.0, RUBBER_LIGHT), (1.0, RUBBER))))
        label = rounded(111.0, 25.0, 20.0, 19.0, 1.2)
        filled(p, label, LABEL_PAPER, LABEL_INK, 0.6)
        written = 1.0 if reduced else clamp(e / (at - 0.2), 0.0, 1.0)
        lines = ((113.5, 30.0, 14.0, 1.1), (113.5, 34.5, 12.0, 0.8), (113.5, 38.5, 9.0, 0.8))
        for k, (x, y, length, width) in enumerate(lines):
            part = clamp(written * len(lines) - k, 0.0, 1.0)
            if part > 0:
                p.setPen(QPen(PHARMA_GREEN if k == 0 else LABEL_INK, width, *ROUND))
                p.drawLine(QPointF(x, y), QPointF(x + length * part, y))
        p.setPen(QPen(QColor(255, 255, 255, 150), 1.2, *ROUND))
        p.drawLine(QPointF(111.6, 18.0), QPointF(111.8, 48.0))
        if e >= at:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.2, 0.0, 1.0))
            p.save()
            p.translate(129.0, 42.0)
            p.scale(pop, pop)
            badge_check(p, 0.0, 0.0, 4.6, WHITE, PHARMA_GREEN)
            p.restore()

    def scene_mischen(self, p: QPainter, e: float, reduced: bool) -> None:
        cx = 121.0
        at = self.payoff("mischen")
        top, bottom = 18.0, 50.0
        clear = 1.0 if reduced else clamp((e - (at - 0.4)) / 0.4, 0.0, 1.0)
        a = 0.0 if reduced else e * 7.0
        rod_x = cx + math.cos(a) * 5.0
        glass = _beaker(p, cx, top, bottom, 12.0)
        p.save()
        p.setClipPath(glass)
        level = top + 9.0
        p.fillRect(QRectF(cx - 13.0, level, 26.0, bottom - level + 1.0), amber_liquid(cx - 12.0, cx + 12.0))
        if clear < 1.0:
            p.setPen(Qt.PenStyle.NoPen)
            for k in range(9):
                swirl = a * 0.6 + k * 0.7
                r = 2.0 + (k % 4) * 2.4
                x = cx + math.cos(swirl) * r
                y = level + 9.0 + math.sin(swirl) * r * 0.6 + (k % 3) * 3.0
                p.setBrush(QColor(255, 244, 220, int(200 * (1.0 - clear))))
                p.drawEllipse(QPointF(x, y), 1.4, 1.1)
        p.setPen(QPen(faded(WHITE, 0.8), 0.6))
        p.drawLine(QPointF(cx - 11.6, level + 0.4), QPointF(cx + 11.6, level + 0.4))
        p.restore()
        rod = QPainterPath(QPointF(rod_x - 3.0, bottom - 4.0))
        rod.lineTo(rod_x + 6.0, top - 8.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(GLASS_EDGE, 2.4, *ROUND))
        p.drawPath(rod)
        p.setPen(QPen(TUBE_LIGHT, 1.2, *ROUND))
        p.drawPath(rod)
        if e >= at:
            sparkle(p, cx + 14.0, top + 6.0, 2.8 if reduced else 2.8 * abs(math.sin(e * 4.0)), WHITE)
            sparkle(p, cx - 9.0, top + 14.0, 2.0 if reduced else 2.0 * abs(math.cos(e * 4.0)), EDEL_GOLD_LIGHT)
