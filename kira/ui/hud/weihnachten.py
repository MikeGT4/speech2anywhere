# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import functools
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_OUT, Frame, clamp, prog
from kira.ui.hud.saison import (
    CLOUD, HINT_BODY, INK, LABEL, ROUND, STEEL, TINT, WHITE, YELLOW, Pose, Saison, ellipse, faded, glow, polygon,
    sparkle, text, unit,
)

SANTA = QColor("#C9252C")
SANTA_DARK = QColor("#9E1B21")
SANTA_LIGHT = QColor("#E45A5F")
FUR_SHADE = QColor("#E4E4E4")
KRAFT = QColor("#E8D2A6")
DOUGH = QColor("#F3D7A1")
COOKIE = QColor("#E3A857")
FIR = QColor("#2E7D4F")
CANDLE_WAX = QColor("#FFF6E0")
FLAME = QColor("#FFD23F")
REINDEER = QColor("#9A5B2E")
WINTER = QColor("#15294B")
SNOW = QColor("#F4FAFF")
DRIFT_EDGE = QColor("#B9CCE0")
OVEN_GLASS = QColor("#4A2C1A")
OVEN_HEAT = QColor("#FF9A3D")

BEARD = ('<ellipse cx="160" cy="236" rx="30" ry="20" fill="#FFB1B6"/>'
         '<ellipse cx="356" cy="236" rx="30" ry="20" fill="#FFB1B6"/>'
         '<path d="M 150 238 C 126 290 124 352 144 394 C 150 424 172 448 198 448 C 208 474 242 486 262 470 '
         'C 282 486 318 474 328 448 C 354 448 376 424 380 394 C 400 352 398 290 374 238 '
         'C 344 262 306 268 262 262 C 218 268 180 262 150 238 Z" fill="#FFFFFF" stroke="#111111" '
         'stroke-width="14" stroke-linejoin="round"/>')
MUSTACHE = ('<path d="M 262 246 C 240 222 194 222 172 240 C 158 252 164 276 186 276 C 214 276 242 268 262 258 '
            'C 282 268 310 276 338 276 C 360 276 366 252 352 240 C 330 222 284 222 262 246 Z" fill="#FFFFFF" '
            'stroke="#111111" stroke-width="12" stroke-linejoin="round"/>')

HAT_X, HAT_Y = 35.0, 18.85
HAT_SCALE = 0.88
PANEL = QRectF(1.5, 1.5, 257.0, 77.0)
FLAKE_COUNT = 30
SNOW_FALL_H = 84.0
CLOUD_SNOW_DEPTH = 7.5
PILE_LEFT, PILE_RIGHT = 86.0, 251.0
PILE_BUMPS = 7
PILE_DEPTH = 5.0
HINT_SHIFT = 2.0
SLED_CYCLE_S = 2.8
ARCH_CANDLES = 7
CANDLE_STEP_S = 0.36
ARCH_R_OUT, ARCH_R_IN = 19.0, 15.0
OVEN_DONE_S = 2.8
DING_S = 0.6
WREATH_AT = (244.0, 21.0)
WREATH_CANDLES = (-6.6, -2.2, 2.2, 6.6)
WREATH_BERRIES = ((-8.0, 1.6), (0.0, 3.6), (8.0, 1.6), (-3.6, -2.6))
CANDLE_S = 15.0
CELEBRATE_S = 0.9
ZACK_FLAKES = ((236.0, 16.0, 248.0, 7.5, 3.2), (94.0, 18.0, 84.0, 8.0, 2.8), (244.0, 58.0, 253.0, 68.0, 2.6),
               (104.0, 60.0, 92.0, 70.0, 2.4))


def _santa_parts(fx: float, fy: float) -> tuple[QPainterPath, QPainterPath, QPainterPath]:
    tip = QPointF(21.5 + fx, -3.5 + fy)
    cone = QPainterPath(QPointF(-17.0, 0.0))
    cone.cubicTo(QPointF(-14.5, -8.5), QPointF(-7.0, -15.0), QPointF(1.5, -15.2))
    cone.cubicTo(QPointF(10.0, -15.4), QPointF(17.5 + fx * 0.5, -11.0 + fy * 0.4), tip)
    cone.cubicTo(QPointF(18.5 + fx * 0.6, -4.0 + fy * 0.6), QPointF(15.0, -5.6), QPointF(12.6, -3.2))
    cone.cubicTo(QPointF(14.2, -1.6), QPointF(16.0, -0.6), QPointF(17.0, 0.0))
    cone.closeSubpath()
    band = QPainterPath(QPointF(-19.5, -2.2))
    band.cubicTo(QPointF(-8.0, -5.4), QPointF(8.0, -5.4), QPointF(19.5, -2.2))
    band.cubicTo(QPointF(22.2, -1.6), QPointF(22.2, 3.0), QPointF(19.5, 3.6))
    band.cubicTo(QPointF(8.0, 0.8), QPointF(-8.0, 0.8), QPointF(-19.5, 3.6))
    band.cubicTo(QPointF(-22.2, 3.0), QPointF(-22.2, -1.6), QPointF(-19.5, -2.2))
    band.closeSubpath()
    return cone, band, ellipse(tip.x(), tip.y(), 4.0)


def _santa_hat(p: QPainter, x: float, y: float, angle: float, fx: float, fy: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.scale(HAT_SCALE, HAT_SCALE)
    cone, band, pom = _santa_parts(fx, fy)
    whole = QPainterPath()
    whole.addPath(cone)
    whole.addPath(band)
    whole.addPath(pom)
    whole.setFillRule(Qt.FillRule.WindingFill)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(WHITE, 4.0, *ROUND))
    p.drawPath(whole)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPath(whole.translated(1.2, 1.2))
    p.setPen(QPen(INK, 1.6, *ROUND))
    p.setBrush(SANTA)
    p.drawPath(cone)
    p.save()
    p.setClipPath(cone)
    p.setBrush(Qt.BrushStyle.NoBrush)
    fold = QPainterPath(QPointF(12.6, -3.2))
    fold.cubicTo(QPointF(9.0, -7.0), QPointF(9.5, -12.0), QPointF(14.0 + fx * 0.4, -12.0 + fy * 0.3))
    p.setPen(QPen(SANTA_DARK, 2.2, *ROUND))
    p.drawPath(fold)
    shine = QPainterPath(QPointF(-12.5, -3.0))
    shine.cubicTo(QPointF(-10.5, -8.5), QPointF(-6.0, -12.4), QPointF(-0.5, -13.2))
    p.setPen(QPen(SANTA_LIGHT, 1.1, *ROUND))
    p.drawPath(shine)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.6, *ROUND))
    p.drawPath(cone)
    p.setPen(QPen(INK, 1.5, *ROUND))
    p.setBrush(WHITE)
    p.drawPath(band)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(FUR_SHADE)
    for k in range(5):
        p.drawEllipse(QPointF(-14.0 + k * 7.0, 1.6 - abs(k - 2) * 0.5), 1.6, 0.8)
    p.setPen(QPen(INK, 1.4, *ROUND))
    p.setBrush(WHITE)
    p.drawPath(pom)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(FUR_SHADE)
    p.drawEllipse(QPointF(21.5 + fx + 1.2, -3.5 + fy + 1.3), 1.5, 1.0)
    p.restore()


def _star(cx: float, cy: float, r_out: float, r_in: float, rot: float = -90.0) -> QPainterPath:
    points = []
    for i in range(10):
        a = math.radians(rot + i * 36)
        r = r_out if i % 2 == 0 else r_in
        points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return polygon(points)


def _snowflake(p: QPainter, x: float, y: float, r: float, rot: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(rot)
    for pen in (QPen(INK, 2.2, *ROUND), QPen(WHITE, 1.0, *ROUND)):
        p.setPen(pen)
        for k in range(3):
            a = math.radians(k * 60)
            dx, dy = math.cos(a) * r, math.sin(a) * r
            p.drawLine(QPointF(-dx, -dy), QPointF(dx, dy))
    p.restore()


@functools.lru_cache(maxsize=1)
def _panel() -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(PANEL, 10, 10)
    return path


@functools.lru_cache(maxsize=1)
def _flakes() -> tuple:
    out = []
    for i in range(FLAKE_COUNT):
        out.append((5.0 + unit(i, 11) * 9.0, unit(i, 13) * 262, unit(i, 17) * SNOW_FALL_H, 0.8 + unit(i, 19),
                    0.55 + unit(i, 23) * 0.9, faded(SNOW, 0.55 + 0.45 * unit(i, 29))))
    return tuple(out)


@functools.lru_cache(maxsize=1)
def _drift() -> QPainterPath:
    path = QPainterPath(QPointF(0.0, 80.0))
    path.lineTo(0.0, 73.0)
    for k in range(27):
        x = k * 10.0
        path.lineTo(x, 72.5 - 1.8 * math.sin(x * 0.05 + 0.4) - 1.0 * math.sin(x * 0.19))
    path.lineTo(262.0, 80.0)
    path.closeSubpath()
    return path


def snowflakes(t: float, reduced: bool) -> list[tuple[float, float, float, QColor]]:
    out = []
    for i, (speed, x0, y0, sway, r, color) in enumerate(_flakes()):
        if reduced:
            out.append((x0, y0 - 2.0, r, color))
        else:
            out.append((x0 + math.sin(t * sway + i) * 2.4, (y0 + t * speed) % SNOW_FALL_H - 2.0, r, color))
    return out


def _winter_panel(p: QPainter, t: float, reduced: bool) -> None:
    panel = _panel()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(WINTER)
    p.drawPath(panel)
    p.save()
    p.setClipPath(panel)
    for x, y, r, color in snowflakes(t, reduced):
        p.setBrush(color)
        p.drawEllipse(QPointF(x, y), r, r)
    p.setBrush(SNOW)
    p.setPen(QPen(DRIFT_EDGE, 1.0))
    p.drawPath(_drift())
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 2.4))
    p.drawPath(panel)


def _drip_y(x: float, top: float, depth: float, wave: float, drop: float) -> float:
    s = max(0.0, math.sin(x * 0.21 + 1.3))
    s3 = s * s * s
    return top + depth + wave * math.sin(x * 0.47) + s3 * s3 * drop


@functools.lru_cache(maxsize=1)
def _cloud_snow() -> tuple[QPainterPath, QPainterPath]:
    x, y, w = CLOUD.x(), CLOUD.y(), CLOUD.width()
    band = QPainterPath(QPointF(x - 4.0, y - 4.0))
    band.lineTo(x + w + 4.0, y - 4.0)
    edge = QPainterPath()
    steps = 40
    for i in range(steps, -1, -1):
        bx = x - 4.0 + (w + 8.0) * i / steps
        by = _drip_y(bx, y, CLOUD_SNOW_DEPTH, 1.4, 4.5)
        band.lineTo(bx, by)
        if i == steps:
            edge.moveTo(bx, by)
        else:
            edge.lineTo(bx, by)
    band.closeSubpath()
    return band, edge


@functools.lru_cache(maxsize=1)
def _pile() -> QPainterPath:
    top = HINT_BODY.top()
    width = (PILE_RIGHT - PILE_LEFT) / PILE_BUMPS
    path = QPainterPath(QPointF(PILE_LEFT, top + 2.4))
    path.cubicTo(QPointF(PILE_LEFT - 1.2, top + 0.4), QPointF(PILE_LEFT, top - 1.0), QPointF(PILE_LEFT + 2.0, top - 1.2))
    for i in range(PILE_BUMPS):
        x0 = PILE_LEFT + 2.0 + (width - 4.0 / PILE_BUMPS) * i
        x1 = x0 + width - 4.0 / PILE_BUMPS
        lift = 3.0 + 1.4 * unit(i, 41)
        end_y = top - 1.2 if i == PILE_BUMPS - 1 else top + 0.2
        path.cubicTo(QPointF(x0 + (x1 - x0) * 0.15, top - 1.2 - lift), QPointF(x1 - (x1 - x0) * 0.15, top - 1.2 - lift),
                     QPointF(x1, end_y))
    path.cubicTo(QPointF(PILE_RIGHT, top - 1.0), QPointF(PILE_RIGHT + 1.2, top + 0.4), QPointF(PILE_RIGHT, top + 2.4))
    steps = 30
    for k in range(steps + 1):
        bx = PILE_RIGHT - (PILE_RIGHT - PILE_LEFT) * k / steps
        path.lineTo(bx, _drip_y(bx, top, PILE_DEPTH - 2.0, 1.0, 3.0))
    path.closeSubpath()
    return path


@functools.lru_cache(maxsize=1)
def _logo_bubble() -> tuple:
    tokens = cm._BUBBLE.split()
    start = (float(tokens[1]), float(tokens[2]))
    curves = []
    i = 3
    while i + 6 < len(tokens) and tokens[i] == "C":
        n = [float(v) for v in tokens[i + 1:i + 7]]
        curves.append(((n[0], n[1]), (n[2], n[3]), (n[4], n[5])))
        i += 7
    return start, tuple(curves)


def _bubble_path(cx: float, cy: float, scale: float) -> QPainterPath:
    start, curves = _logo_bubble()
    path = QPainterPath(QPointF(cx + (start[0] - 257.0) * scale, cy + (start[1] - 248.0) * scale))
    for c1, c2, end in curves:
        path.cubicTo(QPointF(cx + (c1[0] - 257.0) * scale, cy + (c1[1] - 248.0) * scale),
                     QPointF(cx + (c2[0] - 257.0) * scale, cy + (c2[1] - 248.0) * scale),
                     QPointF(cx + (end[0] - 257.0) * scale, cy + (end[1] - 248.0) * scale))
    path.closeSubpath()
    return path


@functools.lru_cache(maxsize=2)
def _arch(cx: float, base: float) -> QPainterPath:
    arc = QPainterPath(QPointF(cx - ARCH_R_OUT, base))
    arc.arcTo(QRectF(cx - ARCH_R_OUT, base - ARCH_R_OUT, ARCH_R_OUT * 2, ARCH_R_OUT * 2), 180, -180)
    arc.lineTo(cx + ARCH_R_IN, base)
    arc.arcTo(QRectF(cx - ARCH_R_IN, base - ARCH_R_IN, ARCH_R_IN * 2, ARCH_R_IN * 2), 0, 180)
    arc.closeSubpath()
    return arc


def _candle_flame(x: float, y: float, h: float, w: float) -> QPainterPath:
    flame = QPainterPath(QPointF(x, y - h))
    flame.cubicTo(QPointF(x + w, y - h * 0.45), QPointF(x + w * 0.86, y), QPointF(x, y))
    flame.cubicTo(QPointF(x - w * 0.86, y), QPointF(x - w, y - h * 0.45), QPointF(x, y - h))
    return flame


def _schwibbogen(p: QPainter, cx: float, base: float, lit: float, t: float, reduced: bool) -> None:
    spots = []
    for i in range(ARCH_CANDLES):
        a = math.radians(160 - i * 140 / (ARCH_CANDLES - 1))
        spots.append((cx + math.cos(a) * ARCH_R_OUT, base - math.sin(a) * ARCH_R_OUT))
    for i, (x, y) in enumerate(spots):
        if i < lit:
            flick = 1.0 if reduced else 0.75 + 0.25 * math.sin(t * 13 + i * 2.1)
            glow(p, x, y - 6.8, 5.5, FLAME, 0.45 * flick)
    cm._ink_shape(p, _arch(cx, base), INK, 1.0, 1.2)
    p.setBrush(INK)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(cx - ARCH_R_OUT - 3.0, base, (ARCH_R_OUT + 3.0) * 2, 3.4), 1.0, 1.0)
    p.setBrush(WHITE)
    p.setPen(QPen(INK, 1.0, *ROUND))
    p.drawPath(_bubble_path(cx, base - 8.0, 0.031))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawEllipse(QPointF(cx - 1.8, base - 10.3), 0.9, 1.1)
    p.drawEllipse(QPointF(cx + 1.7, base - 10.3), 0.9, 1.1)
    p.drawEllipse(QPointF(cx, base - 6.0), 1.2, 0.9)
    for i, (x, y) in enumerate(spots):
        p.setBrush(CANDLE_WAX)
        p.setPen(QPen(INK, 0.7))
        p.drawRect(QRectF(x - 1.0, y - 5.0, 2.0, 5.0))
        if i < lit:
            k = clamp(lit - i, 0.0, 1.0)
            flick = 1.0 if reduced else 0.85 + 0.15 * math.sin(t * 17 + i * 1.3)
            p.setBrush(FLAME)
            p.setPen(QPen(INK, 0.6))
            p.drawPath(_candle_flame(x, y - 5.0, (3.0 + 0.6 * flick) * EASE_OUT(k), 1.4))


def _reindeer(p: QPainter, x: float, y: float, run: float) -> None:
    p.save()
    p.translate(x, y)
    p.setPen(QPen(INK, 1.0, *ROUND))
    for k, lx in enumerate((-3.6, -2.0, 2.4, 4.0)):
        a = math.sin(run + (0.0 if k < 2 else math.pi)) * (0.6 if k % 2 else 0.9)
        p.drawLine(QPointF(lx, 1.8), QPointF(lx + a * 3.0, 6.2))
    p.setPen(QPen(INK, 1.1, *ROUND))
    p.setBrush(REINDEER)
    p.drawPath(ellipse(0.0, 0.0, 5.8, 3.3))
    p.setPen(QPen(INK, 1.0, *ROUND))
    p.drawPath(polygon(((3.4, -1.6), (5.6, -5.0), (7.4, -4.0), (5.6, -0.4))))
    p.drawPath(ellipse(7.6, -5.4, 2.4, 1.9))
    p.setPen(QPen(INK, 0.9, *ROUND))
    for side in (0.0, 1.3):
        p.drawLine(QPointF(6.6 + side, -7.0), QPointF(5.4 + side, -11.0))
        p.drawLine(QPointF(5.9 + side, -9.4), QPointF(4.0 + side, -10.2))
        p.drawLine(QPointF(5.6 + side, -10.4), QPointF(6.8 + side, -11.8))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(SANTA)
    p.drawEllipse(QPointF(10.0, -5.0), 1.0, 1.0)
    p.setBrush(INK)
    p.drawEllipse(QPointF(7.8, -6.0), 0.45, 0.45)
    p.restore()


@functools.lru_cache(maxsize=1)
def _sleigh_shapes() -> tuple[QPainterPath, QPainterPath]:
    body = QPainterPath(QPointF(-9.0, -4.0))
    body.lineTo(4.0, -4.0)
    body.cubicTo(QPointF(6.5, -4.0), QPointF(7.4, -1.0), QPointF(6.4, 1.4))
    body.lineTo(-7.4, 1.4)
    body.cubicTo(QPointF(-9.2, 1.4), QPointF(-9.6, -2.0), QPointF(-9.0, -4.0))
    body.closeSubpath()
    runner = QPainterPath(QPointF(-8.0, 4.2))
    runner.lineTo(6.0, 4.2)
    runner.cubicTo(QPointF(9.0, 4.2), QPointF(10.0, 1.4), QPointF(8.0, 0.6))
    return body, runner


def _sleigh(p: QPainter, x: float, y: float) -> None:
    body, runner = _sleigh_shapes()
    p.save()
    p.translate(x, y)
    p.setPen(QPen(INK, 1.0, *ROUND))
    p.setBrush(KRAFT)
    p.drawPath(ellipse(-4.0, -5.0, 4.4, 3.6))
    p.setPen(QPen(INK, 0.9, *ROUND))
    p.setBrush(YELLOW)
    p.drawRect(QRectF(-1.6, -9.6, 4.6, 4.2))
    p.setPen(QPen(SANTA, 0.9))
    p.drawLine(QPointF(0.7, -9.6), QPointF(0.7, -5.4))
    cm._ink_shape(p, body, SANTA, 1.2, 1.2)
    p.setPen(QPen(YELLOW, 0.9, *ROUND))
    p.drawLine(QPointF(-7.0, -1.4), QPointF(4.0, -1.4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.3, *ROUND))
    p.drawPath(runner)
    p.drawLine(QPointF(-5.0, 1.4), QPointF(-5.0, 4.2))
    p.drawLine(QPointF(3.0, 1.4), QPointF(3.0, 4.2))
    p.restore()


def _sled(p: QPainter, elapsed: float, reduced: bool) -> None:
    ph = 1.45 if reduced else elapsed % SLED_CYCLE_S
    u = ph / SLED_CYCLE_S
    x = 72.0 + u * 190.0
    y = 47.5 - math.sin(clamp(u, 0.0, 1.0) * math.pi) * 4.0
    p.save()
    p.setClipPath(cm._cloud(CLOUD))
    if not reduced:
        for k in range(5):
            sx = x - 12.0 - k * 9.0
            sy = y - 1.0 + math.sin((u - k * 0.12) * math.pi) * 1.5
            sparkle(p, sx, sy - (k % 2) * 3.0, 2.6 * (1.0 - k / 5), YELLOW)
    p.translate(x, y)
    p.scale(1.35, 1.35)
    p.setPen(QPen(INK, 0.8, *ROUND))
    p.drawLine(QPointF(6.0, -1.0), QPointF(28.0, -3.5))
    _reindeer(p, 24.0, -3.0, 0.0 if reduced else elapsed * 16.0)
    _sleigh(p, 0.0, 0.0)
    p.restore()


def _heart(cx: float, cy: float, s: float) -> QPainterPath:
    path = QPainterPath(QPointF(cx, cy + s * 0.9))
    path.cubicTo(QPointF(cx - s * 1.3, cy + s * 0.1), QPointF(cx - s * 0.9, cy - s * 1.0), QPointF(cx, cy - s * 0.35))
    path.cubicTo(QPointF(cx + s * 0.9, cy - s * 1.0), QPointF(cx + s * 1.3, cy + s * 0.1), QPointF(cx, cy + s * 0.9))
    path.closeSubpath()
    return path


@functools.lru_cache(maxsize=1)
def _oven_shapes() -> tuple[QPainterPath, QPainterPath]:
    body = QPainterPath()
    body.addRoundedRect(QRectF(-20.0, -16.0, 40.0, 34.0), 4.0, 4.0)
    window = QPainterPath()
    window.addRoundedRect(QRectF(-16.0, -3.6, 32.0, 18.0), 3.0, 3.0)
    return body, window


def _oven(p: QPainter, cx: float, cy: float, elapsed: float, reduced: bool) -> None:
    bake = 1.0 if reduced else clamp(elapsed / OVEN_DONE_S, 0.0, 1.0)
    done = reduced or elapsed >= OVEN_DONE_S
    body, window = _oven_shapes()
    p.save()
    p.translate(cx, cy)
    if not done:
        p.translate(math.sin(elapsed * 40) * 0.25, 0.0)
    cm._ink_shape(p, body, WHITE, 1.8, 1.6)
    p.setPen(QPen(INK, 1.2))
    p.drawLine(QPointF(-20.0, -9.0), QPointF(20.0, -9.0))
    p.setPen(Qt.PenStyle.NoPen)
    for k, kx in enumerate((-13.0, -7.5, 9.0)):
        p.setBrush(INK if k < 2 else SANTA)
        p.drawEllipse(QPointF(kx, -12.6), 1.7, 1.7)
    p.setPen(QPen(INK, 1.2))
    p.setBrush(STEEL)
    p.drawRoundedRect(QRectF(-12.0, -7.4, 24.0, 2.2), 1.0, 1.0)
    p.setPen(QPen(INK, 1.4))
    p.setBrush(OVEN_GLASS)
    p.drawPath(window)
    p.save()
    p.setClipPath(window)
    glow(p, 0.0, 6.0, 20.0, OVEN_HEAT, (0.45 + 0.4 * bake) * (0.9 if reduced else 0.8 + 0.2 * math.sin(elapsed * 9)))
    p.setPen(QPen(STEEL, 1.4, *ROUND))
    p.drawLine(QPointF(-14.0, 10.6), QPointF(14.0, 10.6))
    tone = QColor(int(DOUGH.red() + (COOKIE.red() - DOUGH.red()) * bake),
                  int(DOUGH.green() + (COOKIE.green() - DOUGH.green()) * bake),
                  int(DOUGH.blue() + (COOKIE.blue() - DOUGH.blue()) * bake))
    heart_tone = QColor(int(tone.red() * 0.95), int(tone.green() * 0.85), int(tone.blue() * 0.8))
    rise = 0.8 + 0.2 * EASE_OUT(bake)
    for kx, shape in ((-9.0, "star"), (0.0, "heart"), (9.0, "star")):
        p.save()
        p.translate(kx, 7.4)
        p.scale(rise, rise)
        p.setPen(QPen(INK, 0.8, *ROUND))
        p.setBrush(tone if shape == "star" else heart_tone)
        p.drawPath(_star(0.0, 0.0, 4.4, 2.5) if shape == "star" else _heart(0.0, 0.2, 3.6))
        p.restore()
    p.restore()
    p.setPen(QPen(WHITE, 1.0, *ROUND))
    p.drawLine(QPointF(-13.0, -1.4), QPointF(-9.0, -1.4))
    p.setPen(QPen(INK, 2.0, *ROUND))
    p.drawLine(QPointF(-17.0, 16.0), QPointF(-17.0, 19.0))
    p.drawLine(QPointF(17.0, 16.0), QPointF(17.0, 19.0))
    if not reduced:
        p.setPen(QPen(faded(OVEN_HEAT, 0.9), 1.2, *ROUND))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for j in range(3):
            cyc = (elapsed * 0.9 + j / 3) % 1.0
            x0 = -8.0 + j * 8.0
            lift = cyc * 3.5
            wave = QPainterPath(QPointF(x0, -17.5 - lift))
            wave.cubicTo(QPointF(x0 + 1.6, -18.8 - lift), QPointF(x0 - 1.6, -20.2 - lift), QPointF(x0, -21.5 - lift))
            p.save()
            p.setOpacity(p.opacity() * (1.0 - cyc))
            p.drawPath(wave)
            p.restore()
    p.restore()
    if done and not reduced:
        k = clamp((elapsed - OVEN_DONE_S) / DING_S, 0.0, 1.0)
        if k < 1.0:
            p.save()
            p.setOpacity(p.opacity() * (1.0 - prog(k, 0.7, 0.3)))
            cm._sfx(p, cx + 14.0, cy - 21.0, "DING!", 7.0 + 2.0 * EASE_OUT(min(1.0, k * 3)), 10, 1.8, 0.9)
            p.restore()


@functools.lru_cache(maxsize=1)
def _wreath() -> QPainterPath:
    cx, cy = WREATH_AT
    ring = QPainterPath()
    ring.addEllipse(QPointF(cx, cy), 10.6, 4.4)
    ring.addEllipse(QPointF(cx, cy - 0.4), 6.0, 1.9)
    ring.setFillRule(Qt.FillRule.OddEvenFill)
    return ring


def wreath_lit(elapsed: float, reduced: bool) -> int:
    within = (math.floor(elapsed) if reduced else elapsed) % 60
    if not reduced and elapsed >= 60 and within < CELEBRATE_S:
        return len(WREATH_CANDLES)
    return 1 + int(within // CANDLE_S)


def _wreath_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = WREATH_AT
    within = (math.floor(elapsed) if reduced else elapsed) % 60
    celebrate = not reduced and elapsed >= 60 and within < CELEBRATE_S
    lit = wreath_lit(elapsed, reduced)
    cm._ink_shape(p, _wreath(), FIR, 1.3, 1.2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(SANTA)
    for bx, by in WREATH_BERRIES:
        p.drawEllipse(QPointF(cx + bx, cy + by), 0.9, 0.9)
    for k, ox in enumerate(WREATH_CANDLES):
        base = cy - 0.4 + (0.8 if abs(ox) < 3.0 else 0.0)
        x, y = cx + ox, base - 8.0
        p.setBrush(SANTA)
        p.setPen(QPen(INK, 0.8))
        p.drawRect(QRectF(x - 1.3, y, 2.6, 8.0))
        if k < lit:
            flick = 1.0 if reduced else 0.85 + 0.15 * math.sin(elapsed * 15 + k * 1.9)
            glow(p, x, y - 2.0, 4.0, FLAME, 0.5 * flick)
            p.setBrush(FLAME)
            p.setPen(QPen(INK, 0.6))
            p.drawPath(_candle_flame(x, y, 3.2 + 0.5 * flick, 1.3))
        else:
            p.setPen(QPen(INK, 0.8, *ROUND))
            p.drawLine(QPointF(x, y), QPointF(x, y - 1.4))
    if celebrate:
        k = math.sin(within / CELEBRATE_S * math.pi)
        sparkle(p, cx + 10.0, cy - 14.0, 3.8 * k, YELLOW)
        sparkle(p, cx - 11.0, cy - 12.0, 2.6 * k, YELLOW)
    cm._clock_digits(p, cx - 13.5, 14.6, elapsed)


class Weihnachten(Saison):
    key = "weihnachten"
    SCENES = ("schlitten", "schwibbogen", "plaetzchen")
    CLOCKS = ("kranz",)
    WORDS = ("bla", "ho!", "hoho!")
    WORD_FILLS = (QColor(comic.YELLOW_HOVER), QColor("#FFFFFF"), QColor("#FFD9A0"))
    ZACK_WORD = "Bescherung!"
    SILENCE = ("Kein Signal", "Stille Nacht im Mikrofon.")

    def svg_under(self, kind: str) -> str:
        return BEARD

    def svg_over(self, kind: str) -> str:
        return MUSTACHE

    def accessory(self, p: QPainter, pose: Pose) -> None:
        angle, dy, fx, fy = -4.0, 0.0, 0.0, 0.0
        if pose.kind == "talk":
            if not pose.reduced:
                angle = -4.0 + 3.0 * pose.level * math.sin(pose.t * 8.0)
                swing = math.sin(pose.t * 7.0 - 0.5) * (0.35 + pose.level)
                fx, fy = 1.6 * swing, 1.6 * abs(swing)
        elif pose.kind == "shout":
            angle = -10.0 + (0.0 if pose.reduced else 4.0 * math.sin(pose.t * 29.0))
            dy, fx, fy = 0.0, -1.2, -3.6
        elif pose.kind == "wink":
            angle, dy, fy = -10.0, -0.4, -1.0
        elif pose.kind == "sad":
            angle, dy, fx, fy = 7.0, 1.6, -2.0, 5.0
        else:
            angle = 4.0 + (0.0 if pose.reduced else 1.5 * math.sin(pose.t * 1.6))
            if pose.kind == "look":
                angle += pose.look[0] * 0.2
        _santa_hat(p, HAT_X, HAT_Y + dy, angle, fx, fy)

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        _winter_panel(p, 0.0 if f.reduced else t, f.reduced)

    def cloud(self, p: QPainter) -> None:
        cm._trail(p)
        cloud = cm._cloud(CLOUD)
        band, edge = _cloud_snow()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK)
        p.drawPath(cloud.translated(cm.SHADOW, cm.SHADOW))
        p.setBrush(TINT)
        p.drawPath(cloud)
        p.save()
        p.setClipPath(cloud)
        p.setBrush(WHITE)
        p.drawPath(band)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(INK, 1.4, *ROUND))
        p.drawPath(edge)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(INK, 2.2, *ROUND))
        p.drawPath(cloud)

    def hint_decor(self, p: QPainter) -> float:
        p.setPen(QPen(INK, 1.4, *ROUND))
        p.setBrush(WHITE)
        p.drawPath(_pile())
        return HINT_SHIFT

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _wreath_clock(p, elapsed, reduced)

    def caption(self, key: str, elapsed: float) -> str:
        if key == "schwibbogen":
            return "leuchtet!" if elapsed >= ARCH_CANDLES * CANDLE_STEP_S else "Lichter an …"
        if key == "plaetzchen":
            return "duftet!" if elapsed >= OVEN_DONE_S else "im Ofen …"
        return ""

    def paint_scene(self, p: QPainter, key: str, t: float, f: Frame, elapsed: float, title: str) -> None:
        if key == "schlitten":
            ph = 1.45 if f.reduced else elapsed % SLED_CYCLE_S
            look = round((-12 + 24 * clamp(ph / SLED_CYCLE_S, 0.0, 1.0)) / 3) * 3
            self.figure(p, self.pose("look", t, f, look=(look, 6), mouth="o"))
            self.cloud(p)
            text(p, 110, 26, title, 15)
            _sled(p, elapsed, f.reduced)
        elif key == "schwibbogen":
            lit = ARCH_CANDLES if f.reduced else elapsed / CANDLE_STEP_S
            self.figure(p, self.pose("look", t, f, look=(8, 10), mouth="smile"))
            self.cloud(p)
            _schwibbogen(p, 122.0, 46.0, lit, elapsed, f.reduced)
            text(p, 150, 33, title, 15)
            text(p, 150, 49, self.caption(key, ARCH_CANDLES * CANDLE_STEP_S if f.reduced else elapsed), 11, 600, LABEL)
        else:
            done = f.reduced or elapsed >= OVEN_DONE_S
            surprised = done and not f.reduced and elapsed < OVEN_DONE_S + 0.8
            self.figure(p, self.pose("look", t, f, look=(10, 12), mouth="o" if surprised else "smile"))
            self.cloud(p)
            _oven(p, 122.0, 33.0, elapsed, f.reduced)
            text(p, 150, 33, title, 15)
            text(p, 150, 49, self.caption(key, OVEN_DONE_S if f.reduced else elapsed), 11, 600, LABEL)

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        for j, (sx, sy, ex, ey, r) in enumerate(ZACK_FLAKES):
            u = 1.0 if f.reduced else EASE_OUT(clamp(k * 1.8 - j * 0.1, 0.0, 1.0))
            if u <= 0:
                continue
            x, y = sx + (ex - sx) * u, sy + (ey - sy) * u
            if j % 2 == 0:
                _snowflake(p, x, y, r, 0.0 if f.reduced else t * 90)
            else:
                sparkle(p, x, y, r + 0.6, YELLOW)
