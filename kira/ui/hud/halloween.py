# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import functools
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPen

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_IN_OUT, EASE_OUT, Frame, clamp, prog
from kira.ui.hud.saison import (
    INK, LABEL, ROUND, SMOKE, STEEL, WHITE, YELLOW, Pose, Saison, ellipse, faded, glow, polygon, text,
)

HAT = QColor("#3B2A5C")
HAT_LIGHT = QColor("#5E4A8C")
ORANGE = QColor("#FF8A1F")
ORANGE_DARK = QColor("#D9620B")
CARVED = QColor("#5A2A06")
CANDLE = QColor("#FFE066")
GLOW = QColor("#FFC400")
STEM = QColor("#5E7F2B")
MOON = QColor("#FFF1B8")
CRATER = QColor("#F2DA86")
MOON_SHADE = QColor("#4A3F66")
BAT = QColor("#17121F")
POT = QColor("#2B2B31")
POT_RIM = QColor("#45454F")
POT_SHINE = QColor("#7C7C88")
STRAW = QColor("#F2C14E")
WOOD = QColor("#8A5A2B")
DIRT = QColor("#6B6760")
DUST = QColor("#9A9486")

HAT_X, HAT_Y = 35.0, 19.3
HAT_SCALE = 0.79
JACK = QPointF(77.0, 64.0)
JACK_SCALE = 0.8
JACK_DIM = 0.35
JACK_GLOW_RISE = 10.0
PUMPKIN_RX, PUMPKIN_RY = 17.0, 13.0
EYE_L = ((-9.5, -2.0), (-3.5, -2.0), (-6.5, -7.2))
EYE_R = ((3.5, -2.0), (9.5, -2.0), (6.5, -7.2))
NOSE = ((-1.6, 1.6), (1.6, 1.6), (0.0, -1.0))
GRIN = ((-11.0, 3.0), (-7.4, 6.4), (-3.8, 3.6), (0.0, 7.0), (3.8, 3.6), (7.4, 6.4), (11.0, 3.0),
        (7.4, 9.8), (0.0, 10.6), (-7.4, 9.8))
CUTS = ((EYE_L, 0.2, 0.75), (EYE_R, 0.85, 1.4), (NOSE, 1.45, 1.65), (GRIN, 1.75, 2.6))
CARVE_DONE = 2.6
CARVE_LIGHT_S = 2.9
BOIL_AFTER_S = 3.0
FOAM = tuple((-11.0 + k * 4.4, -10.4 - (k % 2) * 1.2, 2.6 + (k % 3) * 0.5) for k in range(6))
DRIPS = ((-12.0, 7.0), (1.5, 9.5), (11.0, 6.0))
LINE_Y = cm.LINE_Y
LINE_TEXT = "Bla bla blubb, bla bla!"
CRUMBS = (("äh", 117.0, 43.5, -18.0), ("ähm", 140.0, 54.5, 12.0), ("öh", 163.0, 43.0, 20.0),
          ("hm", 186.0, 55.0, -10.0), ("äh", 206.0, 43.5, 8.0), ("ähm", 224.0, 54.0, -15.0))
BROOM_PASS_S = 1.6
BROOM_CYCLE_S = 2.1
BROOM_LEFT, BROOM_RIGHT = 110.0, 232.0
MOON_AT = (244.0, 14.0, 8.4)
CRATERS = ((-2.6, -2.2, 1.6), (2.4, 2.0, 2.0), (3.2, -3.4, 1.0), (-3.0, 3.4, 1.1))
OWL_S = 1.2
BAT_FLIGHTS = ((236.0, 18.0, 246.0, 9.5), (96.0, 20.0, 84.0, 9.5), (240.0, 56.0, 247.0, 66.0))
BLUBB_Y = -21.75


def _hat_cone(fx: float, fy: float) -> QPainterPath:
    cone = QPainterPath(QPointF(-9.0, -1.0))
    cone.cubicTo(QPointF(-7.6, -6.6), QPointF(-5.2, -11.6), QPointF(-1.4, -14.8))
    cone.cubicTo(QPointF(1.8, -17.4), QPointF(7.4, -17.8), QPointF(12.6 + fx, -15.0 + fy))
    cone.cubicTo(QPointF(8.2, -14.6), QPointF(4.8, -13.4), QPointF(3.8, -11.0))
    cone.cubicTo(QPointF(5.4, -6.8), QPointF(7.4, -3.6), QPointF(9.0, -1.0))
    cone.closeSubpath()
    return cone


@functools.lru_cache(maxsize=1)
def _hat_brim() -> QPainterPath:
    return ellipse(0.0, 0.0, 20.5, 3.4)


def _witch_hat(p: QPainter, x: float, y: float, angle: float, fx: float, fy: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.scale(HAT_SCALE, HAT_SCALE)
    brim = _hat_brim()
    cone = _hat_cone(fx, fy)
    both = QPainterPath()
    both.addPath(brim)
    both.addPath(cone)
    both.setFillRule(Qt.FillRule.WindingFill)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(WHITE, 4.0, *ROUND))
    p.drawPath(both)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPath(both.translated(1.2, 1.2))
    p.setPen(QPen(INK, 1.6, *ROUND))
    p.setBrush(HAT)
    p.drawPath(brim)
    p.drawPath(cone)
    p.save()
    p.setClipPath(cone)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(ORANGE)
    p.drawRect(QRectF(-12.0, -4.4, 24.0, 3.4))
    side = QPainterPath(QPointF(-6.4, -3.6))
    side.cubicTo(QPointF(-5.4, -7.6), QPointF(-3.6, -10.8), QPointF(-1.0, -13.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(HAT_LIGHT, 1.1, *ROUND))
    p.drawPath(side)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.6, *ROUND))
    p.drawPath(cone)
    p.drawLine(QPointF(-8.6, -4.4), QPointF(8.6, -4.4))
    p.setBrush(YELLOW)
    p.setPen(QPen(INK, 0.9))
    p.drawRect(QRectF(-1.9, -4.6, 3.8, 3.6))
    p.setBrush(HAT)
    p.drawRect(QRectF(-0.8, -3.6, 1.6, 1.6))
    p.restore()


def _bat_shape(lift: float) -> QPainterPath:
    path = QPainterPath(QPointF(-0.3, -1.4))
    path.lineTo(-0.9, -2.8)
    path.lineTo(-1.3, -1.2)
    path.lineTo(-1.4, -0.4)
    path.cubicTo(QPointF(-3.6, -2.4 - lift), QPointF(-6.4, -3.0 - lift), QPointF(-8.0, -1.6 - lift * 0.6))
    path.cubicTo(QPointF(-6.6, -0.6), QPointF(-6.0, 0.4), QPointF(-5.2, 1.0))
    path.cubicTo(QPointF(-4.4, 0.0), QPointF(-3.6, 0.2), QPointF(-3.0, 1.2))
    path.cubicTo(QPointF(-2.4, 0.4), QPointF(-1.8, 0.6), QPointF(-1.2, 1.2))
    path.cubicTo(QPointF(-1.0, 2.4), QPointF(1.0, 2.4), QPointF(1.2, 1.2))
    path.cubicTo(QPointF(1.8, 0.6), QPointF(2.4, 0.4), QPointF(3.0, 1.2))
    path.cubicTo(QPointF(3.6, 0.2), QPointF(4.4, 0.0), QPointF(5.2, 1.0))
    path.cubicTo(QPointF(6.0, 0.4), QPointF(6.6, -0.6), QPointF(8.0, -1.6 - lift * 0.6))
    path.cubicTo(QPointF(6.4, -3.0 - lift), QPointF(3.6, -2.4 - lift), QPointF(1.4, -0.4))
    path.lineTo(1.3, -1.2)
    path.lineTo(0.9, -2.8)
    path.lineTo(0.3, -1.4)
    path.closeSubpath()
    return path


def _bat(p: QPainter, x: float, y: float, s: float, flap: float) -> None:
    p.save()
    p.translate(x, y)
    p.scale(s, s)
    shape = _bat_shape(flap * 3.2)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(WHITE, 2.6, *ROUND))
    p.drawPath(shape)
    p.setPen(QPen(INK, 0.9, *ROUND))
    p.setBrush(BAT)
    p.drawPath(shape)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(YELLOW)
    p.drawEllipse(QPointF(-0.6, 0.0), 0.45, 0.45)
    p.drawEllipse(QPointF(0.6, 0.0), 0.45, 0.45)
    p.restore()


@functools.lru_cache(maxsize=4)
def _lobes(scale: float) -> QPainterPath:
    rx, ry = PUMPKIN_RX * scale, PUMPKIN_RY * scale
    path = QPainterPath()
    path.addEllipse(QPointF(-rx * 0.38, ry * 0.04), rx * 0.62, ry * 0.94)
    path.addEllipse(QPointF(rx * 0.38, ry * 0.04), rx * 0.62, ry * 0.94)
    path.addEllipse(QPointF(0.0, 0.0), rx * 0.62, ry)
    path.setFillRule(Qt.FillRule.WindingFill)
    return path


@functools.lru_cache(maxsize=4)
def _stem(scale: float) -> QPainterPath:
    ry = PUMPKIN_RY * scale
    stem = QPainterPath(QPointF(-1.8 * scale, -ry + 1.2))
    stem.cubicTo(QPointF(-2.0 * scale, -ry - 3.0 * scale), QPointF(0.0, -ry - 5.6 * scale),
                 QPointF(2.6 * scale, -ry - 6.0 * scale))
    stem.lineTo(3.2 * scale, -ry - 4.0 * scale)
    stem.cubicTo(QPointF(1.4 * scale, -ry - 3.4 * scale), QPointF(1.8 * scale, -ry - 1.0),
                 QPointF(2.0 * scale, -ry + 1.2))
    stem.closeSubpath()
    return stem


def _pumpkin_shell(p: QPainter, scale: float, lit: float, flicker: float, rise: float = 0.0) -> None:
    rx, ry = PUMPKIN_RX * scale, PUMPKIN_RY * scale
    if lit > 0:
        glow(p, 0.0, -rise, rx * 1.7, GLOW, 0.55 * lit * flicker)
    p.setPen(QPen(INK, 1.3, *ROUND))
    p.setBrush(STEM)
    p.drawPath(_stem(scale))
    lobes = _lobes(scale)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPath(lobes.translated(1.6, 1.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 3.2, *ROUND))
    p.drawPath(lobes)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(ORANGE)
    p.drawPath(lobes)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(ORANGE_DARK, 1.2, *ROUND))
    for side in (-1, 1):
        rib = QPainterPath(QPointF(side * rx * 0.22, -ry * 0.92))
        rib.cubicTo(QPointF(side * rx * 0.42, -ry * 0.3), QPointF(side * rx * 0.42, ry * 0.3),
                    QPointF(side * rx * 0.22, ry * 0.92))
        p.drawPath(rib)


def _hole(p: QPainter, path: QPainterPath, lit: float, flicker: float) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(CARVED)
    p.drawPath(path)
    p.setPen(QPen(INK, 1.1, *ROUND))
    p.setBrush(faded(CANDLE, lit * (0.7 + 0.3 * flicker)) if lit > 0 else Qt.BrushStyle.NoBrush)
    p.drawPath(path)


def _jack(p: QPainter, cx: float, cy: float, lit: float, flicker: float) -> None:
    p.save()
    p.translate(cx, cy)
    _pumpkin_shell(p, JACK_SCALE, lit, flicker, JACK_GLOW_RISE)
    for points, _t0, _t1 in CUTS:
        _hole(p, polygon(points, scale=JACK_SCALE), lit, flicker)
    p.restore()


def _cut_so_far(points, u: float) -> tuple[QPainterPath, QPointF]:
    ring = list(points) + [points[0]]
    lengths = []
    total = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        d = math.sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0))
        lengths.append(d)
        total += d
    goal = total * u
    run = 0.0
    tip = QPointF(ring[0][0], ring[0][1])
    path = QPainterPath(tip)
    for (x0, y0), (x1, y1), d in zip(ring, ring[1:], lengths):
        if run + d >= goal:
            k = (goal - run) / d if d > 0 else 0.0
            tip = QPointF(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)
            path.lineTo(tip)
            break
        path.lineTo(x1, y1)
        run += d
        tip = QPointF(x1, y1)
    return path, tip


def _knife(p: QPainter, x: float, y: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(-35)
    p.setPen(QPen(INK, 0.9, *ROUND))
    p.setBrush(STEEL)
    p.drawPath(polygon(((0.0, 0.0), (1.6, -1.0), (8.0, -1.4), (8.0, 0.6), (1.6, 0.6))))
    p.setBrush(WOOD)
    p.setPen(QPen(INK, 0.9))
    p.drawRoundedRect(QRectF(8.0, -1.8, 6.5, 2.8), 1.0, 1.0)
    p.restore()


def _carving(p: QPainter, cx: float, cy: float, carved: float, lit: float, flicker: float, knife: bool) -> None:
    p.save()
    p.translate(cx, cy)
    _pumpkin_shell(p, 1.0, lit, flicker)
    for points, t0, t1 in CUTS:
        u = clamp((carved - t0) / (t1 - t0), 0.0, 1.0)
        if u <= 0:
            continue
        if u >= 1.0:
            _hole(p, polygon(points), lit, flicker)
            continue
        cut, tip = _cut_so_far(points, u)
        p.setPen(QPen(INK, 1.1, *ROUND))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(cut)
        if knife:
            _knife(p, tip.x(), tip.y())
            for k in range(2):
                age = (u * 6 + k * 0.5) % 1.0
                a = -2.2 + k * 1.3
                x = tip.x() + math.cos(a) * age * 9
                y = tip.y() + math.sin(a) * age * 9 + age * age * 6
                p.setPen(QPen(INK, 0.6))
                p.setBrush(ORANGE)
                p.drawPath(polygon(((x, y), (x + 1.6, y - 0.6), (x + 0.6, y + 1.2))))
    p.restore()


def _flame(p: QPainter, x: float, y: float, h: float, w: float) -> None:
    outer = QPainterPath(QPointF(x, y - h))
    outer.cubicTo(QPointF(x + w * 0.9, y - h * 0.45), QPointF(x + w, y), QPointF(x, y))
    outer.cubicTo(QPointF(x - w, y), QPointF(x - w * 0.9, y - h * 0.45), QPointF(x, y - h))
    p.setPen(QPen(INK, 1.0, *ROUND))
    p.setBrush(ORANGE)
    p.drawPath(outer)
    inner = QPainterPath(QPointF(x, y - h * 0.55))
    inner.cubicTo(QPointF(x + w * 0.45, y - h * 0.25), QPointF(x + w * 0.5, y), QPointF(x, y))
    inner.cubicTo(QPointF(x - w * 0.5, y), QPointF(x - w * 0.45, y - h * 0.25), QPointF(x, y - h * 0.55))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(YELLOW)
    p.drawPath(inner)


@functools.lru_cache(maxsize=1)
def _pot() -> tuple[QPainterPath, QPainterPath, QPainterPath, QPainterPath]:
    body = QPainterPath(QPointF(-15.5, -8.0))
    body.cubicTo(QPointF(-20.5, -2.0), QPointF(-20.0, 10.0), QPointF(-11.0, 15.0))
    body.lineTo(11.0, 15.0)
    body.cubicTo(QPointF(20.0, 10.0), QPointF(20.5, -2.0), QPointF(15.5, -8.0))
    body.closeSubpath()
    legs = QPainterPath()
    for side in (-1, 1):
        legs.addPath(polygon(((side * 8.0, 14.0), (side * 10.5, 19.0), (side * 13.0, 13.0))))
    shine = QPainterPath(QPointF(-14.0, -2.0))
    shine.cubicTo(QPointF(-15.0, 3.0), QPointF(-13.0, 8.0), QPointF(-9.0, 11.0))
    foam = QPainterPath()
    for x, y, r in FOAM:
        foam.addEllipse(QPointF(x, y), r, r)
    foam.setFillRule(Qt.FillRule.WindingFill)
    return body, legs, shine, foam


def _cauldron(p: QPainter, cx: float, cy: float, age: float, boil: bool, reduced: bool, since: float) -> None:
    body, legs, shine, foam = _pot()
    p.save()
    p.translate(cx, cy)
    if boil and not reduced:
        p.translate(math.sin(age * 71) * 0.6, math.cos(age * 53) * 0.4)
    for j, fx in enumerate((-7.0, 0.0, 7.0)):
        h = 6.0 + (0.0 if reduced else 1.8 * math.sin(age * 13 + j * 1.7)) + (1.6 if boil else 0.0)
        _flame(p, fx, 23.5, h, 3.0)
    p.setPen(QPen(INK, 1.8, *ROUND))
    p.drawLine(QPointF(-11.0, 23.8), QPointF(11.0, 23.8))
    p.setPen(QPen(INK, 1.3, *ROUND))
    p.setBrush(POT)
    p.drawPath(legs)
    cm._ink_shape(p, body, POT, 2.0, 1.6)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(POT_SHINE, 1.4, *ROUND))
    p.drawPath(shine)
    p.setPen(QPen(INK, 1.8, *ROUND))
    p.setBrush(POT_RIM)
    p.drawPath(ellipse(0.0, -8.5, 17.5, 4.2))
    p.setPen(QPen(INK, 1.0, *ROUND))
    p.setBrush(YELLOW)
    p.drawPath(ellipse(0.0, -8.5, 14.2, 2.7))
    if boil:
        over = 1.0 if reduced else EASE_OUT(clamp((since - BOIL_AFTER_S) / 1.2, 0.0, 1.0))
        for dx, length in DRIPS:
            ln = length * over
            if ln < 0.5:
                continue
            drip = QPainterPath(QPointF(dx - 2.2, -8.0))
            drip.lineTo(dx - 2.0, -8.0 + ln)
            drip.cubicTo(QPointF(dx - 2.0, -5.0 + ln), QPointF(dx + 2.0, -5.0 + ln), QPointF(dx + 2.0, -8.0 + ln))
            drip.lineTo(dx + 2.2, -8.0)
            drip.closeSubpath()
            p.setPen(QPen(INK, 1.0, *ROUND))
            p.setBrush(YELLOW)
            p.drawPath(drip)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(INK, 2.0, *ROUND))
        p.drawPath(foam)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(YELLOW)
        p.drawPath(foam)
    rate = 1.6 if boil else 0.9
    for j in range(4):
        cyc = 0.62 if reduced else (age * rate + j / 4) % 1.0
        bx = -8.0 + j * 5.2 + math.sin(cyc * 6.0 + j) * 1.4
        by = -9.35 - cyc * 13.5
        r = 1.0 + cyc * (2.4 if boil else 1.6)
        a = 1.0 - prog(cyc, 0.8, 0.2)
        if a <= 0:
            continue
        p.save()
        p.setOpacity(p.opacity() * a)
        p.setBrush(WHITE)
        p.setPen(QPen(INK, 0.9))
        p.drawEllipse(QPointF(bx, by), r, r)
        p.restore()
        if j % 2 == 0 and cyc > 0.7 and not reduced:
            k = prog(cyc, 0.7, 0.3)
            p.save()
            p.setOpacity(p.opacity() * (1.0 - k))
            cm._sfx(p, bx + 3, BLUBB_Y, "blubb" if j == 0 else "bla", 6.5 + k * 1.5, -10 + j * 8, 1.2, 0.8)
            p.restore()
    if boil and not reduced:
        for j in range(3):
            a = ((age - BOIL_AFTER_S) * 0.9 + j / 3) % 1.0
            cm._puff(p, -6 + j * 6 + a * 3, -13.1 - a * 9, 1.8 + a * 3.0, 1.0 - prog(a, 0.45, 0.55), SMOKE)
    p.restore()


def _broom(p: QPainter, x: float, y: float, direction: int, lifted: bool) -> None:
    p.save()
    p.translate(x, y - (5.0 if lifted else 0.0))
    p.scale(direction, 1.0)
    p.setPen(QPen(INK, 3.4, *ROUND))
    p.drawLine(QPointF(-1.0, -7.0), QPointF(-15.0, -25.0))
    p.setPen(QPen(WOOD, 1.8, *ROUND))
    p.drawLine(QPointF(-1.0, -7.0), QPointF(-15.0, -25.0))
    lean = 0.0 if lifted else -2.4
    cm._ink_shape(p, polygon(((-2.8, -8.0), (2.4, -8.0), (6.6 + lean, 1.2), (-6.2 + lean, 1.2))), STRAW, 1.4, 1.2)
    p.setPen(QPen(faded(INK, 0.55), 0.7, *ROUND))
    for k in range(5):
        u = (k + 1) / 6
        p.drawLine(QPointF(-2.4 + 4.8 * u, -6.8), QPointF(-6.0 + lean + 12.4 * u, 0.6))
    p.setBrush(ORANGE)
    p.setPen(QPen(INK, 1.0))
    p.drawRoundedRect(QRectF(-3.2, -9.6, 6.4, 2.6), 0.8, 0.8)
    p.restore()


def _dustpan(p: QPainter, x: float, y: float, pile: int) -> None:
    pan = polygon(((x - 6.0, y + 1.5), (x + 4.0, y + 1.5), (x + 6.0, y - 6.5), (x + 4.4, y - 6.5),
                   (x + 2.6, y - 0.8), (x - 6.0, y - 0.8)))
    cm._ink_shape(p, pan, STEEL, 1.2, 1.0)
    p.setPen(QPen(INK, 1.6, *ROUND))
    p.drawLine(QPointF(x + 5.4, y - 6.0), QPointF(x + 8.6, y - 10.5))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(DUST)
    for k in range(min(pile, 6)):
        p.drawEllipse(QPointF(x - 3.6 + (k % 3) * 2.6, y - 1.6 - (k // 3) * 1.6), 1.4, 0.9)


def _sweep(p: QPainter, elapsed: float, reduced: bool) -> None:
    ph = 1.2 if reduced else elapsed % BROOM_CYCLE_S
    sweeping = ph < BROOM_PASS_S
    if sweeping:
        bx = BROOM_LEFT + (BROOM_RIGHT - BROOM_LEFT) * EASE_IN_OUT(ph / BROOM_PASS_S)
    else:
        bx = BROOM_RIGHT - (BROOM_RIGHT - BROOM_LEFT) * EASE_IN_OUT((ph - BROOM_PASS_S) / (BROOM_CYCLE_S - BROOM_PASS_S))
    p.setFont(comic.baloo(800, 8))
    p.setPen(INK)
    p.drawText(QPointF(112.0, LINE_Y + 2.5), LINE_TEXT)
    small = comic.baloo(700, 8)
    metrics = QFontMetricsF(small)
    pile = 0
    pushed = 0
    returning = not sweeping and ph > BROOM_CYCLE_S - 0.35
    for word, x0, y0, angle in CRUMBS:
        gone = reduced or not sweeping
        x, y, a, alpha = x0, y0, angle, 1.0
        if sweeping and bx + 7.0 > x0:
            x = bx + 8.0 + (pushed % 2) * 3.4
            y = LINE_Y - 1.0 - (pushed // 2) * 4.2 + (y0 - LINE_Y) * 0.15
            a = angle + (x - x0) * 4.0
            pushed += 1
            if x > BROOM_RIGHT + 3.0:
                gone = True
        if gone:
            pile += 1
            if reduced or not returning:
                continue
            alpha = prog(ph, BROOM_CYCLE_S - 0.35, 0.35)
            x, y, a = x0, y0, angle
        p.save()
        p.setOpacity(p.opacity() * alpha)
        p.translate(x, y)
        p.rotate(a)
        p.setFont(small)
        p.setPen(DIRT)
        p.drawText(QPointF(-metrics.horizontalAdvance(word) / 2, 2.6), word)
        p.restore()
    _dustpan(p, BROOM_RIGHT + 9.0, LINE_Y + 3.5, pile)
    if sweeping and not reduced:
        for j in range(2):
            age = (ph * 2.2 + j * 0.5) % 1.0
            cm._puff(p, bx - 7.0 - age * 6.0, LINE_Y + 1.0 - age * 6.0, 1.6 + age * 2.4, 1.0 - prog(age, 0.4, 0.6),
                     SMOKE)
        for j in range(2):
            cyc = (ph * 1.3 + j * 0.5) % 1.0
            sx = bx - 22.0 - j * 24.0
            if sx > BROOM_LEFT:
                cm._sparkle(p, sx, LINE_Y - 8.0 - j * 3, 3.0 * math.sin(cyc * math.pi))
    _broom(p, bx, LINE_Y + 1.5, 1 if sweeping or reduced else -1, not sweeping and not reduced)


def _moon_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy, r = MOON_AT
    u = clamp(((math.floor(elapsed) if reduced else elapsed) % 60) / 60, 0.0, 1.0)
    disc = ellipse(cx, cy, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPath(disc.translated(1.6, 1.6))
    p.setBrush(MOON)
    p.drawPath(disc)
    p.save()
    p.setClipPath(disc)
    p.setBrush(CRATER)
    for dx, dy, cr in CRATERS:
        p.drawEllipse(QPointF(cx + dx, cy + dy), cr, cr)
    p.setBrush(faded(MOON_SHADE, 0.92))
    p.drawEllipse(QPointF(cx + 0.3 * r + u * 2.0 * r, cy - 0.2), r * 1.06, r * 1.06)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.8, *ROUND))
    p.drawPath(disc)
    since = elapsed % 60
    if not reduced and elapsed >= 60 and since < OWL_S:
        k = since / OWL_S
        _bat(p, cx - 6 - k * 34, cy + 10 - math.sin(k * math.pi) * 8, 1.0, math.sin(since * 30))
        p.save()
        p.setOpacity(p.opacity() * (1.0 - prog(k, 0.6, 0.4)))
        cm._sfx(p, cx - 26, cy + 14, "UHU!", 8 + 2 * EASE_OUT(min(1.0, k * 3)), -8, 2.2, 1.0)
        p.restore()
    cm._clock_digits(p, cx - r - 4.5, cy + 0.4, elapsed)


class Halloween(Saison):
    key = "halloween"
    SCENES = ("kessel", "besen", "kuerbis")
    CLOCKS = ("mond",)
    LANES = ((96.0, 50.0, -12.0), cm.LANES[1], cm.LANES[2])
    WORDS = ("bla", "buh!", "blubb!")
    WORD_FILLS = (QColor(comic.YELLOW_HOVER), QColor("#FFB020"), QColor("#FF9A3D"))
    ZACK_WORD = "Hokuspokus!"
    SILENCE = ("Kein Signal", "Totenstille im Mikrofon.")

    def accessory(self, p: QPainter, pose: Pose) -> None:
        dx = dy = fx = fy = 0.0
        angle = -3.0
        if pose.kind == "talk":
            if not pose.reduced:
                angle = -3.0 + 4.0 * pose.level * math.sin(pose.t * 8.0)
                swing = math.sin(pose.t * 6.5 - 0.8) * (0.4 + pose.level)
                fx, fy = 1.4 * swing, 0.9 * swing
                dy = -0.8 * pose.level * abs(math.sin(pose.t * 8.0))
        elif pose.kind == "shout":
            angle = -12.0 + (0.0 if pose.reduced else 5.0 * math.sin(pose.t * 31.0))
            dy, fx, fy = 0.0, -0.8, -1.1
        elif pose.kind == "wink":
            angle, dy = -12.0, -0.7
        elif pose.kind == "sad":
            angle, dx, dy, fx, fy = 13.0, 1.0, 2.6, -1.0, 4.0
        else:
            angle = 6.0 + (0.0 if pose.reduced else 2.0 * math.sin(pose.t * 1.6))
            if pose.kind == "look":
                angle += pose.look[0] * 0.25
        _witch_hat(p, HAT_X + dx, HAT_Y + dy, angle, fx, fy)
        if pose.kind == "shout":
            p.setPen(QPen(INK, 1.2 * HAT_SCALE, *ROUND))
            for k in (-1, 0, 1):
                p.drawLine(QPointF(HAT_X + k * 5.5, HAT_Y + 0.4), QPointF(HAT_X + k * 6.7, HAT_Y + 2.2))

    def jack_light(self, an) -> float:
        if self.mode == "error":
            return 0.0
        if self.mode == "rec" and an.silent and not an.clip:
            return JACK_DIM
        return 1.0

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        x, y = JACK.x(), JACK.y()
        if self.mode == "rec" and an.clip and not f.reduced:
            x += math.sin(t * 71.0) * 0.7
            y += math.cos(t * 53.0) * 0.4
        flicker = 1.0 if f.reduced else 0.82 + 0.18 * math.sin(t * 17.0) * math.sin(t * 7.3)
        _jack(p, x, y, self.jack_light(an), flicker)

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _moon_clock(p, elapsed, reduced)

    def caption(self, key: str, elapsed: float) -> str:
        if key == "kessel":
            return "kocht über!" if elapsed >= BOIL_AFTER_S else "es brodelt …"
        if key == "kuerbis":
            return "leuchtet!" if elapsed >= CARVE_LIGHT_S else "wird geschnitzt …"
        return ""

    def paint_scene(self, p: QPainter, key: str, t: float, f: Frame, elapsed: float, title: str) -> None:
        if key == "kessel":
            boil = elapsed >= BOIL_AFTER_S
            self.figure(p, self.pose("look", t, f, look=(8, 16), mouth="o" if boil else "smile"))
            self.cloud(p)
            _cauldron(p, 121.0, 30.0, 0.0 if f.reduced else elapsed, boil, f.reduced, elapsed)
            text(p, 150, 31, title, 15)
            text(p, 150, 47, self.caption(key, elapsed), 11, 600, LABEL)
        elif key == "besen":
            ph = 1.2 if f.reduced else elapsed % BROOM_CYCLE_S
            u = ph / BROOM_PASS_S if ph < BROOM_PASS_S else 1.0 - (ph - BROOM_PASS_S) / (BROOM_CYCLE_S - BROOM_PASS_S)
            look = round((-12 + 24 * clamp(u, 0.0, 1.0)) / 3) * 3
            self.figure(p, self.pose("look", t, f, look=(look, 14), mouth="smile"))
            self.cloud(p)
            _sweep(p, elapsed, f.reduced)
            text(p, 110, 23, title, 15)
        else:
            carved = CARVE_LIGHT_S if f.reduced else elapsed
            lit = 1.0 if f.reduced else EASE_OUT(prog(elapsed, CARVE_LIGHT_S, 0.4))
            flicker = 1.0 if f.reduced else 0.8 + 0.2 * math.sin(elapsed * 17) * math.sin(elapsed * 7.3)
            self.figure(p, self.pose("look", t, f, look=(10, 10), mouth="o" if lit > 0.5 else "smile"))
            self.cloud(p)
            _carving(p, 121.0, 33.0, carved, lit, flicker, not f.reduced and carved < CARVE_DONE)
            text(p, 150, 31, title, 15)
            text(p, 150, 47, self.caption(key, carved), 11, 600, LABEL)

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        if f.reduced:
            _bat(p, 226.0, 12.0, 1.0, 0.3)
            _bat(p, 104.0, 14.0, 0.85, -0.2)
            return
        for j, (sx, sy, ex, ey) in enumerate(BAT_FLIGHTS):
            u = EASE_OUT(clamp(k * 1.8 - j * 0.12, 0.0, 1.0))
            if u <= 0:
                continue
            _bat(p, sx + (ex - sx) * u, sy + (ey - sy) * u, 0.7 + 0.35 * u, math.sin(t * 28 + j))
