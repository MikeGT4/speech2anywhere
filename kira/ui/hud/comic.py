# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import functools
import math
import random
from collections import deque
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtSvg import QSvgRenderer

from kira.ui import _comic as comic
from kira.ui.hud.base import EASE_IN_OUT, EASE_OUT, W, Frame, HudStyle, clamp, prog

INK = QColor(comic.INK)
YELLOW = QColor(comic.YELLOW)
WHITE = QColor("#FFFFFF")
TINT = QColor(comic.TINT)
LABEL = QColor(comic.LABEL)
REC = QColor("#E8590C")
STEEL = QColor("#EDEDED")
GLASS = QColor("#E3F4FB")
SWEAT = QColor("#CDEFFF")
SMOKE = QColor("#E6E6E6")
DULL = QColor("#EFE9DA")
SHEEN = QColor("#FFE88A")
THOUGHT = QColor(comic.TINT)
ALARM = QColor(comic.RED)
WORD_COLORS = (QColor(comic.YELLOW_HOVER), QColor("#FFB020"), QColor("#FFA24D"))
SHADOW = 3.0
_ROUND = (Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

TILE = QRectF(2, 8, 66, 66)
MOUTH = QPointF(64, 50)
LANES = ((90.0, 56.0, -12.0), (132.0, 30.0, 7.0), (200.0, 54.0, -6.0))
WORDS = ("bla", "bla", "blubb!")
SPAWN_LEVEL = 0.3
SPAWN_S = 0.34
LIFE_S = 1.0
FLIGHT_S = 0.45
DONE_S = 0.7
MAX_WORD_W = 84.0
MIN_WORD_PX = 8

CLOUD = QRectF(94, 3, 158, 56)
TRAIL = ((76, 30, 3.0), (85, 22, 4.2))
DRUM = QPointF(121, 31)
DRUM_SCALE = 0.9
DRUM_WORDS = (("bla", 8.5, 8), ("bla", 9.5, 8), ("blubb", 6.0, 7))
SPIN_AFTER_S = 3.0
SMOKE_AFTER_S = 3.0
SWEAT_AFTER_S = 6.0
SCENES = ("waesche", "buegeln", "zahnraeder")
CLOCKS = ("wecker", "zeitring", "sanduhr")
CLOCK_PX = 12
TICK_S = 0.16
RING_S = 0.7
SPARKLE_S = 0.6
FLIP_S = 0.45
SCENE_S = 5.0
IRON_PASS_S = 1.5
IRON_LEFT, IRON_RIGHT = 114.0, 232.0
LINE_Y = 49.5
SHEET = QRectF(105.0, 39.0, 138.0, 13.0)
SHEET_TEXT = "Bla bla blubb, bla bla!"
SHEET_PX = 8
WRINKLE_START = 2.6
WRINKLE_DECAY = 0.42
CREASES = ((110, 41, 116, 49), (131, 51, 134, 42), (149, 40, 154, 50), (172, 51, 175, 41),
           (194, 40, 199, 49), (216, 51, 219, 42), (233, 41, 238, 50))


@dataclass
class _Word:
    text: str
    born: float
    size: float
    lane: int
    width: float = 0.0
    fill: QColor = field(default_factory=lambda: QColor(YELLOW))


_BUBBLE = ("M 256 70 C 382 70 456 146 456 248 C 456 350 382 420 262 420 C 236 420 212 417 190 410 "
           "C 168 428 138 446 108 452 C 96 454 90 444 98 436 C 112 420 122 402 126 384 C 84 350 58 304 58 248 "
           "C 58 146 130 70 256 70 Z")
_LAUGH = ('<path d="M 360 144 L 384 128 M 378 180 L 420 176 M 374 216 L 414 232" stroke="#111111" '
          'stroke-width="14" stroke-linecap="round" fill="none"/>')
_WINK = ('<path d="M 274 184 C 286 150 340 150 352 184" fill="none" stroke="#111111" stroke-width="16" '
         'stroke-linecap="round"/>')
_MOUTH_LAUGH = ('<path d="M 170 262 C 170 328 212 366 258 366 C 306 366 346 328 346 262 C 290 282 226 282 170 262 Z" '
                'fill="#111111"/><path d="M 216 334 C 232 316 282 316 298 334 C 280 352 234 352 216 334 Z" '
                'fill="#E5484D"/>')
_MOUTHS = {
    "line": ('<path d="M 206 318 C 236 306 286 306 316 318" fill="none" stroke="#111111" stroke-width="18" '
             'stroke-linecap="round"/>'),
    "o": '<ellipse cx="262" cy="320" rx="19" ry="15" fill="#111111"/>',
    "smile": ('<path d="M 200 306 C 230 340 290 340 320 306" fill="none" stroke="#111111" stroke-width="18" '
              'stroke-linecap="round"/>'),
}
_RENDERERS: dict[tuple, QSvgRenderer] = {}


def _eye(cx: float, look_x: float = 12, look_y: float = 10) -> str:
    return (f'<ellipse cx="{cx}" cy="174" rx="38" ry="46" fill="#FFFFFF" stroke="#111111" stroke-width="14"/>'
            f'<ellipse cx="{cx + look_x}" cy="{174 + look_y}" rx="17" ry="20.1" fill="#111111"/>'
            f'<circle cx="{cx + look_x - 6.5}" cy="{174 + look_y - 8.5}" r="6.1" fill="#FFFFFF"/>')


def _face(kind: str, level: float) -> str:
    if kind == "talk":
        ry = 30 + 70 * level
        return (_eye(200) + _WINK + _LAUGH
                + f'<ellipse cx="258" cy="{300 + ry * 0.2}" rx="{62 + 18 * level}" ry="{ry}" fill="#111111"/>'
                + f'<ellipse cx="258" cy="{300 + ry * 0.75}" rx="{34 + 8 * level}" ry="{max(4, ry * 0.32)}" '
                  'fill="#E5484D"/>')
    if kind == "wink":
        return _eye(200) + _WINK + _LAUGH + _MOUTH_LAUGH
    if kind == "think":
        return (_eye(200, -4, -18) + _eye(312, -4, -18)
                + '<path d="M 206 318 C 236 306 286 306 316 318" fill="none" stroke="#111111" stroke-width="18" '
                  'stroke-linecap="round"/>')
    if kind == "sad":
        return (_eye(200, 6, 16) + _eye(312, -6, 16)
                + '<path d="M 196 342 C 226 302 292 302 322 342" fill="none" stroke="#111111" stroke-width="18" '
                  'stroke-linecap="round"/>')
    return ('<path d="M 168 146 L 224 174 L 168 202 M 344 146 L 288 174 L 344 202" fill="none" stroke="#111111" '
            'stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>'
            '<ellipse cx="258" cy="316" rx="84" ry="92" fill="#111111"/>'
            '<ellipse cx="258" cy="376" rx="44" ry="28" fill="#E5484D"/>')


def _render_face(p: QPainter, key: tuple, face) -> None:
    renderer = _RENDERERS.get(key)
    if renderer is None:
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
               '<rect x="0" y="0" width="512" height="512" rx="102" ry="102" fill="#FFC400"/>'
               f'<path d="{_BUBBLE}" fill="#FFFFFF" stroke="#111111" stroke-width="18" stroke-linejoin="round"/>'
               f'{face()}</svg>')
        renderer = QSvgRenderer(svg.encode("utf-8"))
        _RENDERERS[key] = renderer
    renderer.render(p, TILE)


def _mascot(p: QPainter, kind: str, level: float = 0.0) -> None:
    step = round(clamp(level, 0.0, 1.0) * 8) if kind == "talk" else 0
    _render_face(p, (kind, step), lambda: _face(kind, step / 8))


def _mascot_looking(p: QPainter, look: tuple[int, int], mouth: str) -> None:
    _render_face(p, ("look", look, mouth), lambda: _eye(200, *look) + _eye(312, *look) + _MOUTHS[mouth])


def _circling_look(age: float, period: float) -> tuple[int, int]:
    angle = (round(age / period * 16) % 16) * math.pi / 8
    return round(11 * math.cos(angle)), round(9 * math.sin(angle))


def _polygon(points) -> QPainterPath:
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
    path.closeSubpath()
    return path


def _burst(cx: float, cy: float, rx: float, ry: float, spikes: int, inner: float) -> QPainterPath:
    points = []
    for i in range(spikes * 2):
        a = math.pi * i / spikes
        k = 1.0 if i % 2 == 0 else inner
        points.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
    return _polygon(points)


def _ink_shape(p: QPainter, path: QPainterPath, fill: QColor, width: float = 2.4, shadow: float = SHADOW) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPath(path.translated(shadow, shadow))
    p.setBrush(fill)
    p.setPen(QPen(INK, width, *_ROUND))
    p.drawPath(path)


def _text(p: QPainter, x: float, y: float, s: str, font: QFont, color: QColor, align: str = "left") -> None:
    if align == "center":
        x -= QFontMetricsF(font).horizontalAdvance(s) / 2
    p.setFont(font)
    p.setPen(color)
    p.drawText(QPointF(x, y), s)


HINT_BODY = QRectF(80, 8, 177, 64)
HINT_TEXT_W = HINT_BODY.width() - 18
BOLD_STEP, SMALL_STEP = 15.5, 13.0


def _hint_fonts() -> tuple[QFont, QFont]:
    return comic.baloo(800, 12), comic.baloo(600, 10)


def _wrap(text: str, metrics: QFontMetricsF, limit: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and metrics.horizontalAdvance(f"{lines[-1]} {word}") <= HINT_TEXT_W:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    if len(lines) > limit:
        rest = " ".join(lines[limit - 1:])
        lines = lines[:limit - 1] + [metrics.elidedText(rest, Qt.TextElideMode.ElideRight, HINT_TEXT_W)]
    return lines


def error_lines(first: str, second: str) -> list[tuple[str, bool]]:
    bold, small = _hint_fonts()
    head = _wrap(first, QFontMetricsF(bold), 2)
    tail = _wrap(second, QFontMetricsF(small), 2) if second else []
    return [(line, True) for line in head] + [(line, False) for line in tail]


def _lettering(text: str, px: float) -> QPainterPath:
    path = QPainterPath()
    path.addText(0, 0, comic.baloo(800, max(1, round(px))), text)
    path.setFillRule(Qt.FillRule.WindingFill)
    return path


def _sfx(p: QPainter, x: float, y: float, s: str, px: float, angle: float, width: float = 3.2,
         shadow: float = 1.6, fill: QColor = YELLOW) -> None:
    path = _lettering(s, px)
    box = path.boundingRect()
    path.translate(-box.center().x(), -box.center().y())
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(QPen(INK, width, *_ROUND))
    p.setBrush(INK)
    p.drawPath(path.translated(shadow, shadow))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawPath(path)
    p.restore()


def _dots(p: QPainter, cx: float, cy: float, t: float) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    for i in range(3):
        lift = max(0.0, math.sin(t * 7 - i * 0.9)) * 3.2
        p.drawEllipse(QPointF(cx + (i - 1) * 11, cy - lift), 3.4, 3.4)


def _trail(p: QPainter) -> None:
    for x, y, radius in TRAIL:
        dot = QPainterPath()
        dot.addEllipse(QPointF(x, y), radius, radius)
        _ink_shape(p, dot, THOUGHT, 1.8, 1.5)


def _word_width(text: str, px: float) -> float:
    path = QPainterPath()
    path.addText(0, 0, comic.baloo(800, max(1, round(px))), text)
    return path.boundingRect().width()


def _fitted_word(text: str, size: float) -> tuple[str, float, float]:
    width = _word_width(text, size)
    if width <= MAX_WORD_W:
        return text, size, width
    px = max(MIN_WORD_PX, math.floor(round(size) * MAX_WORD_W / width))
    width = _word_width(text, px)
    while width > MAX_WORD_W and px > MIN_WORD_PX:
        px -= 1
        width = _word_width(text, px)
    while width > MAX_WORD_W and len(text.rstrip("…")) > 1:
        text = text.rstrip("…")[:-1] + "…"
        width = _word_width(text, px)
    return text, float(px), width


def _puff(p: QPainter, x: float, y: float, radius: float, alpha: float, fill: QColor) -> None:
    if alpha <= 0:
        return
    path = QPainterPath()
    path.addEllipse(QPointF(x, y), radius, radius * 0.85)
    p.save()
    p.setOpacity(p.opacity() * alpha)
    p.setPen(QPen(INK, 1.0))
    p.setBrush(fill)
    p.drawPath(path)
    p.restore()


def _sparkle(p: QPainter, cx: float, cy: float, r: float) -> None:
    if r <= 0.2:
        return
    points = []
    for i in range(8):
        a = math.pi * i / 4 - math.pi / 2
        k = r if i % 2 == 0 else r * 0.38
        points.append((cx + math.cos(a) * k, cy + math.sin(a) * k))
    p.setBrush(WHITE)
    p.setPen(QPen(INK, 1.1, *_ROUND))
    p.drawPath(_polygon(points))


def _plewd(p: QPainter, x: float, y: float, s: float, angle: float, alpha: float) -> None:
    if alpha <= 0:
        return
    path = QPainterPath(QPointF(0, -s))
    path.cubicTo(QPointF(s * 0.55, -s * 0.2), QPointF(s * 0.62, s * 0.55), QPointF(0, s * 0.62))
    path.cubicTo(QPointF(-s * 0.62, s * 0.55), QPointF(-s * 0.55, -s * 0.2), QPointF(0, -s))
    p.save()
    p.setOpacity(p.opacity() * alpha)
    p.translate(x, y)
    p.rotate(angle)
    p.setBrush(SWEAT)
    p.setPen(QPen(INK, 1.5, *_ROUND))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(WHITE)
    p.drawEllipse(QPointF(-s * 0.18, s * 0.12), s * 0.14, s * 0.2)
    p.restore()


def _sweat(p: QPainter, age: float) -> None:
    for j in range(2):
        cyc = (age / 1.3 + j * 0.5) % 1.0
        _plewd(p, 13 - cyc * 9 - j * 4, 19 - cyc * 10 + j * 8, 4.6, -40 - j * 15, 1.0 - prog(cyc, 0.55, 0.45))


def _drum(p: QPainter, age: float, spin: bool, reduced: bool) -> None:
    p.save()
    p.translate(DRUM)
    p.scale(DRUM_SCALE, DRUM_SCALE)
    if spin and not reduced:
        p.translate(math.sin(age * 71) * 0.7, math.cos(age * 53) * 0.5)
    ring = QPainterPath()
    ring.addEllipse(QPointF(0, 0), 22, 22)
    _ink_shape(p, ring, STEEL, 2.2, 1.6)
    glass = QPainterPath()
    glass.addEllipse(QPointF(0, 0), 17.5, 17.5)
    p.setPen(QPen(INK, 1.8, *_ROUND))
    p.setBrush(GLASS)
    p.drawPath(glass)
    p.save()
    p.setClipPath(glass)
    speed = 2 * math.pi / (0.7 if spin else 1.4)
    for j, (word, radius, px) in enumerate(DRUM_WORDS):
        a = age * speed + j * 2.1
        fall = 0.0 if spin else max(0.0, math.sin(a)) * 3.5
        _sfx(p, math.cos(a) * radius, math.sin(a) * radius + fall, word, px, math.degrees(a) * 0.6 + j * 40,
             1.3, 0.9)
    p.setPen(QPen(INK, 0.9))
    p.setBrush(WHITE)
    for j in range(5):
        p.drawEllipse(QPointF(-11 + j * 5.5, 11 - abs(math.sin(age * 6 + j)) * 2.5), 2.6, 2.6)
    p.restore()
    p.setPen(QPen(WHITE, 2.0, *_ROUND))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(-12, -12, 24, 24), 100 * 16, 50 * 16)
    if spin:
        p.setPen(QPen(INK, 1.4, *_ROUND))
        for side in (-1, 1):
            for row in range(2):
                y = -6 + row * 9
                squiggle = QPainterPath(QPointF(side * 25, y))
                squiggle.cubicTo(QPointF(side * 27.5, y + 1.5), QPointF(side * 22.5, y + 3.5), QPointF(side * 25, y + 5))
                p.drawPath(squiggle)
    p.restore()


def _gear(cx: float, cy: float, r: float, teeth: int, rot: float) -> QPainterPath:
    points = []
    for i in range(teeth * 4):
        a = rot + 2 * math.pi * i / (teeth * 4)
        k = r if i % 4 in (1, 2) else r * 0.74
        points.append((cx + math.cos(a) * k, cy + math.sin(a) * k))
    hole = QPainterPath()
    hole.addEllipse(QPointF(cx, cy), r * 0.28, r * 0.28)
    return _polygon(points).subtracted(hole)


def _gears(p: QPainter, cx: float, cy: float, rot: float) -> None:
    p.setPen(QPen(INK, 1.7, *_ROUND))
    p.setBrush(YELLOW)
    p.drawPath(_gear(cx - 3, cy + 3, 10.0, 8, rot))
    p.setBrush(WHITE)
    p.drawPath(_gear(cx + 9.6, cy - 7.6, 6.4, 6, -rot * 8 / 6 + 0.35))


def _iron_pass(ph: float) -> tuple[float, int]:
    n = int(ph // IRON_PASS_S)
    u = EASE_IN_OUT((ph - n * IRON_PASS_S) / IRON_PASS_S)
    if n % 2 == 0:
        return IRON_LEFT + (IRON_RIGHT - IRON_LEFT) * u, 1
    return IRON_RIGHT - (IRON_RIGHT - IRON_LEFT) * u, -1


def _faded(color: QColor, alpha: float) -> QColor:
    faded = QColor(color)
    faded.setAlphaF(clamp(alpha, 0.0, 1.0))
    return faded


def _wrinkle(x: float, amp: float) -> float:
    return amp * (math.sin(x * 0.52) * 0.65 + math.sin(x * 1.37 + 0.8) * 0.35)


def _wrinkle_amps(passes: int) -> tuple[float, float]:
    before = WRINKLE_START * WRINKLE_DECAY ** passes
    return before, before * WRINKLE_DECAY


def _ironed(x: float, ix: float, direction: int) -> bool:
    return x <= ix if direction > 0 else x >= ix


def _sheet_outline(ix: float, direction: int, before: float, after: float) -> QPainterPath:
    left, right, top, bottom = SHEET.left(), SHEET.right(), SHEET.top(), SHEET.bottom()
    steps = int((right - left) / 3)
    xs = [left + (right - left) * s / steps for s in range(steps + 1)]
    path = QPainterPath()
    for i, x in enumerate(xs):
        amp = after if _ironed(x, ix, direction) else before
        y = top + _wrinkle(x, amp)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    for x in reversed(xs):
        amp = after if _ironed(x, ix, direction) else before
        path.lineTo(x, bottom + _wrinkle(x + 9.0, amp) * 0.6)
    path.closeSubpath()
    return path


def _sheet(p: QPainter, ix: float, direction: int, passes: int, sheen: bool) -> None:
    before, after = _wrinkle_amps(passes)
    outline = _sheet_outline(ix, direction, before, after)
    if direction > 0:
        flat = QRectF(SHEET.left() - 4.0, SHEET.top() - 8.0, ix - SHEET.left() + 4.0, SHEET.height() + 16.0)
    else:
        flat = QRectF(ix, SHEET.top() - 8.0, SHEET.right() + 4.0 - ix, SHEET.height() + 16.0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPath(outline.translated(2.0, 2.0))
    p.setBrush(DULL)
    p.drawPath(outline)
    p.save()
    p.setClipRect(flat)
    p.setBrush(WHITE)
    p.drawPath(outline)
    p.restore()
    if sheen:
        x0, x1 = sorted((ix - direction * 27.0, ix - direction * 7.0))
        x0, x1 = max(x0, SHEET.left() + 2.0), min(x1, SHEET.right() - 2.0)
        if x1 - x0 >= 2.0:
            p.setBrush(_faded(SHEEN, 0.6))
            p.drawRoundedRect(QRectF(x0, SHEET.top() + 2.5, x1 - x0, SHEET.height() - 5.0), 3.0, 3.0)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.6, *_ROUND))
    p.drawPath(outline)
    for x0, y0, x1, y1 in CREASES:
        amp = after if _ironed((x0 + x1) / 2, ix, direction) else before
        strength = amp / WRINKLE_START
        if strength < 0.08:
            continue
        p.setPen(QPen(_faded(INK, 0.55 * strength), 0.9, *_ROUND))
        p.drawLine(QPointF(x0, y0 + _wrinkle(x0, amp)), QPointF(x1, y1 + _wrinkle(x1, amp)))
    font = comic.baloo(800, SHEET_PX)
    metrics = QFontMetricsF(font)
    p.setFont(font)
    x = SHEET.left() + 7.0
    for ch in SHEET_TEXT:
        flat_here = _ironed(x, ix, direction)
        amp = after if flat_here else before
        slope = (_wrinkle(x + 1.5, amp) - _wrinkle(x - 1.5, amp)) / 3.0
        p.save()
        p.translate(x, LINE_Y + _wrinkle(x, amp))
        p.rotate(math.degrees(math.atan(slope)) * 0.7)
        p.setPen(INK if flat_here else _faded(INK, 0.78))
        p.drawText(QPointF(0.0, 0.0), ch)
        p.restore()
        x += metrics.horizontalAdvance(ch)


def _iron(p: QPainter, x: float, sole_y: float, direction: int) -> None:
    p.save()
    p.translate(x, sole_y)
    p.scale(direction, 1.0)
    sole = QPainterPath(QPointF(-15.0, 0.0))
    sole.lineTo(12.0, 0.0)
    sole.lineTo(17.0, -2.3)
    sole.lineTo(12.0, -4.6)
    sole.lineTo(-15.0, -4.6)
    sole.closeSubpath()
    _ink_shape(p, sole, STEEL, 1.6, 1.4)
    body = QPainterPath(QPointF(-13.0, -4.6))
    body.lineTo(10.0, -4.6)
    body.cubicTo(QPointF(13.5, -5.5), QPointF(12.0, -11.0), QPointF(7.0, -12.5))
    body.lineTo(-9.0, -13.5)
    body.cubicTo(QPointF(-12.5, -13.5), QPointF(-13.5, -9.0), QPointF(-13.0, -4.6))
    body.closeSubpath()
    _ink_shape(p, body, YELLOW, 1.8, 1.4)
    handle = QPainterPath(QPointF(-8.0, -13.0))
    handle.cubicTo(QPointF(-8.0, -20.0), QPointF(5.0, -20.0), QPointF(5.0, -12.5))
    p.setPen(QPen(INK, 2.2, *_ROUND))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(handle)
    p.save()
    p.setOpacity(p.opacity() * 0.55)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(WHITE)
    p.drawEllipse(QPointF(-4.0, -9.5), 4.5, 1.6)
    p.restore()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawEllipse(QPointF(6.5, -8.5), 1.3, 1.3)
    p.setPen(QPen(INK, 2.0, *_ROUND))
    p.drawLine(QPointF(-15.0, 0.4), QPointF(16.0, 0.4))
    p.restore()


def _check(p: QPainter, x: float, y: float, s: float) -> None:
    path = QPainterPath(QPointF(x, y + s * 0.55))
    path.lineTo(x + s * 0.38, y + s * 0.92)
    path.lineTo(x + s, y + s * 0.08)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 3.2, *_ROUND))
    p.drawPath(path)


def _cloud(r: QRectF) -> QPainterPath:
    return QPainterPath(_cloud_at(r.x(), r.y(), r.width(), r.height()))


@functools.lru_cache(maxsize=8)
def _cloud_at(x: float, y: float, width: float, height: float) -> QPainterPath:
    r = QRectF(x, y, width, height)
    path = QPainterPath()
    path.addRoundedRect(r.adjusted(5, 5, -5, -5), 12, 12)
    n = max(3, int(r.width() / 24))
    for i in range(n):
        cx = r.left() + 14 + i * (r.width() - 28) / (n - 1)
        for cy in (r.top() + 9, r.bottom() - 9):
            bump = QPainterPath()
            bump.addEllipse(QPointF(cx, cy), 13, 9)
            path = path.united(bump)
    for cx in (r.left() + 9, r.right() - 9):
        side = QPainterPath()
        side.addEllipse(QPointF(cx, r.center().y()), 9, r.height() / 2 - 6)
        path = path.united(side)
    return path.simplified()


def _label_bubble(p: QPainter, body: QRectF, fill: QColor) -> None:
    cy = body.center().y()
    path = QPainterPath()
    path.addRoundedRect(body, 14, 14)
    tail = _polygon([(body.left() + 1, cy - 7), (body.left() - 11, cy + 2), (body.left() + 1, cy + 7)])
    _ink_shape(p, path.united(tail).simplified(), fill, 2.2)


def clock_label(elapsed: float) -> str:
    return f"{int(elapsed // 60)}:{int(elapsed % 60):02d}"


def _tick(elapsed: float, reduced: bool) -> float:
    whole = math.floor(elapsed)
    if reduced:
        return float(whole)
    k = clamp((elapsed - whole) / TICK_S, 0.0, 1.0)
    return whole - 1 + (1 - (1 - k) ** 3) + 0.22 * math.sin(k * math.pi) * (1 - k)


def _circle(cx: float, cy: float, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), r, r)
    return path


def _clock_digits(p: QPainter, right: float, cy: float, elapsed: float) -> None:
    path = _lettering(clock_label(elapsed), CLOCK_PX)
    box = path.boundingRect()
    path.translate(right - box.right(), cy - box.center().y())
    p.setPen(QPen(INK, 2.6, *_ROUND))
    p.setBrush(INK)
    p.drawPath(path.translated(1.2, 1.2))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(WHITE)
    p.drawPath(path)


def _hand(p: QPainter, cx: float, cy: float, angle: float, length: float, color: QColor, width: float,
          tail: float = 0.0) -> None:
    dx, dy = math.sin(angle), -math.cos(angle)
    p.setPen(QPen(color, width, *_ROUND))
    p.drawLine(QPointF(cx - dx * tail, cy - dy * tail), QPointF(cx + dx * length, cy + dy * length))


def _alarm_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy, r = 243.0, 15.0, 7.4
    since = elapsed % 60
    ring = not reduced and elapsed >= 60 and since < RING_S
    frac = elapsed - math.floor(elapsed)
    wobble = 0.0
    if ring:
        wobble = 11.0 * math.sin(since * math.tau * 9)
    elif not reduced:
        wobble = 6.0 * math.sin(frac * math.tau * 3) * math.exp(-frac * 9)
    p.save()
    p.translate(cx, cy + r)
    p.rotate(wobble)
    p.translate(-cx, -(cy + r))
    p.setPen(QPen(INK, 1.8, *_ROUND))
    p.drawLine(QPointF(cx - 4.2, cy + 5.6), QPointF(cx - 5.8, cy + 8.6))
    p.drawLine(QPointF(cx + 4.2, cy + 5.6), QPointF(cx + 5.8, cy + 8.6))
    for side in (-1, 1):
        a = math.radians(side * 42)
        bx, by = cx + math.sin(a) * (r + 1.2), cy - math.cos(a) * (r + 1.2)
        bell = QPainterPath()
        bell.moveTo(bx - 3.4 * math.cos(a), by - 3.4 * math.sin(a))
        bell.arcTo(QRectF(bx - 3.4, by - 3.4, 6.8, 6.8), -math.degrees(a), 180)
        bell.closeSubpath()
        _ink_shape(p, bell, YELLOW, 1.4, 1.2)
    p.setPen(QPen(INK, 1.4, *_ROUND))
    p.drawLine(QPointF(cx, cy - r - 1.0), QPointF(cx, cy - r - 2.6))
    _ink_shape(p, _circle(cx, cy, r), YELLOW, 1.9, 1.8)
    p.setBrush(WHITE)
    p.setPen(QPen(INK, 0.9))
    p.drawEllipse(QPointF(cx, cy), r - 2.2, r - 2.2)
    _hand(p, cx, cy, math.tau * ((elapsed / 60) % 12) / 12, 2.6, INK, 1.4)
    _hand(p, cx, cy, math.tau * (_tick(elapsed, reduced) % 60) / 60, 4.4, REC, 1.0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawEllipse(QPointF(cx, cy), 0.9, 0.9)
    p.restore()
    if ring:
        k = since / RING_S
        p.save()
        p.setOpacity(p.opacity() * (1.0 - prog(k, 0.7, 0.3)))
        _sfx(p, cx - 30, cy + 15, "RING!", 8 + 2 * EASE_OUT(min(1.0, k * 3)), -8, 2.2, 1.0)
        p.restore()
    _clock_digits(p, cx - r - 6.0, cy, elapsed)


def _pie_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy, r = 243.0, 14.0, 8.6
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawRoundedRect(QRectF(cx - 2.2, cy - r - 3.6, 4.4, 3.4), 1.0, 1.0)
    _ink_shape(p, _circle(cx, cy, r), WHITE, 2.0, 2.0)
    u = ((math.floor(elapsed) if reduced else elapsed) % 60) / 60
    inner = r - 1.6
    if u > 0:
        wedge = QPainterPath(QPointF(cx, cy))
        wedge.arcTo(QRectF(cx - inner, cy - inner, inner * 2, inner * 2), 90, -360 * u)
        wedge.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(YELLOW)
        p.drawPath(wedge)
    _hand(p, cx, cy, 0.0, r - 1.4, INK, 1.3)
    _hand(p, cx, cy, math.tau * u, r - 1.4, INK, 1.3)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawEllipse(QPointF(cx, cy), 1.2, 1.2)
    if not reduced and elapsed >= 60 and elapsed % 60 < SPARKLE_S:
        glow = math.sin((elapsed % 60) / SPARKLE_S * math.pi)
        _sparkle(p, cx + 8.5, cy - 8.5, 4.2 * glow)
        _sparkle(p, cx - 9.0, cy - 6.0, 2.8 * glow)
    _clock_digits(p, cx - r - 4.0, cy + 0.4, elapsed)


def _hourglass_shape(hw: float, top: float, neck: float) -> QPainterPath:
    glass = QPainterPath(QPointF(-hw, top))
    glass.lineTo(hw, top)
    glass.cubicTo(QPointF(hw, top + 4.5), QPointF(neck + 0.4, -1.6), QPointF(neck, 0))
    glass.cubicTo(QPointF(neck + 0.4, 1.6), QPointF(hw, -top - 4.5), QPointF(hw, -top))
    glass.lineTo(-hw, -top)
    glass.cubicTo(QPointF(-hw, -top - 4.5), QPointF(-neck - 0.4, 1.6), QPointF(-neck, 0))
    glass.cubicTo(QPointF(-neck - 0.4, -1.6), QPointF(-hw, top + 4.5), QPointF(-hw, top))
    glass.closeSubpath()
    return glass


def _hourglass(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy, hw, top = 244.0, 13.4, 5.2, -8.2
    minute = math.floor(elapsed / 60)
    within = elapsed - minute * 60
    flipping = not reduced and minute > 0 and within < FLIP_S
    u = 1.0 if flipping else clamp((math.floor(elapsed) if reduced else elapsed) % 60 / 60, 0.0, 1.0)
    p.save()
    p.translate(cx, cy)
    if flipping:
        p.rotate(180 * EASE_IN_OUT(within / FLIP_S))
    glass = _hourglass_shape(hw, top, 1.0)
    _ink_shape(p, glass, GLASS, 1.5, 1.5)
    p.save()
    p.setClipPath(glass)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(YELLOW)
    level = top + 1.4 + 6.6 * u
    p.drawRect(QRectF(-hw, level, hw * 2, -level))
    pile = 6.8 * u
    mound = QPainterPath(QPointF(-hw, -top))
    mound.lineTo(-hw, -top - pile * 0.45)
    mound.quadTo(QPointF(0, -top - pile * 1.25), QPointF(hw, -top - pile * 0.45))
    mound.lineTo(hw, -top)
    mound.closeSubpath()
    p.drawPath(mound)
    if u < 1.0:
        p.setPen(QPen(YELLOW.darker(115), 0.9))
        p.drawLine(QPointF(0, 0), QPointF(0, -top - pile))
        if not reduced:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(INK)
            for j in range(3):
                gy = ((elapsed * 9 + j / 3) % 1.0) * (-top - pile)
                p.drawEllipse(QPointF(0, gy), 0.45, 0.45)
    p.restore()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawRoundedRect(QRectF(-hw - 1.6, top - 2.2, hw * 2 + 3.2, 2.4), 1.0, 1.0)
    p.drawRoundedRect(QRectF(-hw - 1.6, -top - 0.2, hw * 2 + 3.2, 2.4), 1.0, 1.0)
    p.restore()
    _clock_digits(p, cx - 9.5, cy + 0.6, elapsed)


CLOCK_PAINTERS = {"wecker": _alarm_clock, "zeitring": _pie_clock, "sanduhr": _hourglass}


class Comic(HudStyle):
    key = "comic"
    live_words = True

    def __init__(self) -> None:
        super().__init__()
        self._words: list[_Word] = []
        self._count = 0
        self._next_spawn = 0.0
        self._lv = 0.0
        self._rng = random.Random()
        self.scene = SCENES[0]
        self.clock = CLOCKS[0]
        self._queue: deque[str] = deque(maxlen=4)
        self._spoken = 0

    def on_press(self, t: float, f: Frame) -> None:
        self._words = []
        self._count = 0
        self._next_spawn = t
        self._lv = 0.0
        self._queue.clear()
        self._spoken = 0
        self.scene = self._rng.choice(SCENES)
        self.clock = self._rng.choice(CLOCKS)

    def feed_words(self, t: float, words: list[str]) -> None:
        if self.mode == "rec":
            self._queue.extend(w for w in words if w)

    def scene_at(self, t: float, f: Frame) -> tuple[str, float]:
        step = 0 if f.reduced else max(0, int((t - self.rel_t) // SCENE_S))
        start = SCENES.index(self.scene)
        return SCENES[(start + step) % len(SCENES)], self.rel_t + step * SCENE_S

    def caption(self, t: float, f: Frame) -> str:
        key, t0 = self.scene_at(t, f)
        if key == "waesche":
            return "Schleudergang…" if t - t0 >= SPIN_AFTER_S else "Wäsche läuft…"
        return "gleich fertig" if key == "zahnraeder" else ""

    def sweating(self, t: float) -> bool:
        return self.mode == "proc" and t - self.rel_t >= SWEAT_AFTER_S

    def on_clear(self, f: Frame) -> None:
        self._words = []

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        if self.mode == "done" and t - self.end_t > DONE_S:
            self.mode = "hidden"
            return
        self._lv += (an.level - self._lv) * min(1.0, dt / 0.08)
        self._words = [w for w in self._words if t - w.born < LIFE_S]
        speaking = self.mode == "rec" and not an.clip and not an.silent and an.level > SPAWN_LEVEL
        if speaking and t >= self._next_spawn:
            lane = self._count % len(LANES)
            if self._queue:
                text = self._queue.popleft()
                fill = WORD_COLORS[self._spoken % len(WORD_COLORS)]
                self._spoken += 1
            else:
                text, fill = WORDS[lane], YELLOW
            text, size, width = _fitted_word(text, 11 + 13 * an.level)
            self._words.append(_Word(text, t, size, lane, width, QColor(fill)))
            self._count += 1
            self._next_spawn = t + SPAWN_S

    def paint(self, p: QPainter, t: float, f: Frame, tap, an) -> None:
        if self.mode == "rec":
            if an.clip:
                self._shout(p)
            elif an.silent:
                self._hint(p, "think", "Kein Signal", "Das Mikrofon liefert Stille.")
            else:
                self._talk(p, t, f)
        elif self.mode == "proc":
            self._think(p, t, f)
        elif self.mode == "done":
            self._zack(p, t, f)
        elif self.mode == "error":
            first, second = self.message_lines()
            self._hint(p, "sad", first or "Fehler", second)

    def _talk(self, p: QPainter, t: float, f: Frame) -> None:
        _mascot(p, "talk", self._lv)
        for word in self._words:
            tx, ty, angle = LANES[word.lane]
            tx = min(max(tx, TILE.right() + 2 + word.width / 2), W - 2 - word.width / 2)
            if f.reduced:
                x, y, scale, alpha = tx, ty, 1.0, 1.0
            else:
                age = t - word.born
                k = EASE_OUT(clamp(age / FLIGHT_S, 0.0, 1.0))
                x = MOUTH.x() + (tx - MOUTH.x()) * k
                y = MOUTH.y() + (ty - MOUTH.y()) * k - math.sin(k * math.pi) * 6
                scale = 0.55 + 0.45 * k
                alpha = 1.0 - prog(age, LIFE_S * 0.7, LIFE_S * 0.3)
            p.save()
            p.setOpacity(p.opacity() * alpha)
            _sfx(p, x, y, word.text, word.size * scale, angle, fill=word.fill)
            p.restore()
        CLOCK_PAINTERS.get(self.clock, _alarm_clock)(p, self.elapsed(t), f.reduced)

    def _shout(self, p: QPainter) -> None:
        _mascot(p, "shout")
        _ink_shape(p, _burst(166, 40, 90, 36, 16, 0.74), ALARM)
        _text(p, 166, 48, "ZU NAH!", comic.baloo(800, 22), INK, "center")

    def _think(self, p: QPainter, t: float, f: Frame) -> None:
        key, t0 = self.scene_at(t, f)
        title = "Politur" if f.polishing else "Erkennen"
        if key == "waesche":
            self._washing(p, t, f, t - t0, title)
        elif key == "zahnraeder":
            self._gears_scene(p, t, f, t - t0, title)
        else:
            self._ironing(p, f, t - t0, title)
        if self.sweating(t):
            _sweat(p, 0.3 if f.reduced else t - self.rel_t - SWEAT_AFTER_S)

    def _washing(self, p: QPainter, t: float, f: Frame, elapsed: float, title: str) -> None:
        spin = elapsed >= SPIN_AFTER_S
        age = 0.0 if f.reduced else elapsed
        _mascot_looking(p, _circling_look(age, 0.7 if spin else 1.4), "o" if spin else "line")
        _trail(p)
        _ink_shape(p, _cloud(CLOUD), THOUGHT, 2.2)
        _drum(p, age, spin, f.reduced)
        _text(p, 150, 31, title, comic.baloo(800, 15), INK)
        _text(p, 150, 47, self.caption(t, f), comic.baloo(600, 11), LABEL)

    def _gears_scene(self, p: QPainter, t: float, f: Frame, elapsed: float, title: str) -> None:
        hot = elapsed >= SMOKE_AFTER_S
        _mascot(p, "think")
        _trail(p)
        _ink_shape(p, _cloud(CLOUD), THOUGHT, 2.2)
        _gears(p, 115, 31, 0.0 if f.reduced else elapsed * 2 * math.pi * 0.55 * (1.9 if hot else 1.0))
        if hot and not f.reduced:
            for j in range(3):
                age = ((elapsed - SMOKE_AFTER_S) * 0.9 + j / 3) % 1.0
                _puff(p, 111 + j * 4 + age * 3, 19 - age * 12, 2.0 + age * 3.5, 1.0 - prog(age, 0.45, 0.55), SMOKE)
        _text(p, 137, 31, title, comic.baloo(800, 15), INK)
        _dots(p, 225, 26, 0.0 if f.reduced else t)
        _text(p, 137, 47, self.caption(t, f), comic.baloo(600, 11), LABEL)

    def _ironing(self, p: QPainter, f: Frame, elapsed: float, title: str) -> None:
        if f.reduced:
            ix, direction, passes = IRON_RIGHT, 1, 1
        else:
            (ix, direction), passes = _iron_pass(elapsed), int(elapsed // IRON_PASS_S)
        look = round((-12 + 24 * (ix - IRON_LEFT) / (IRON_RIGHT - IRON_LEFT)) / 3) * 3
        _mascot_looking(p, (look, 14), "smile")
        _trail(p)
        _ink_shape(p, _cloud(CLOUD), THOUGHT, 2.2)
        _sheet(p, ix, direction, passes, not f.reduced)
        if not f.reduced:
            for j in range(4):
                age = (elapsed + j * 0.3) % 1.2
                born_x, born_dir = _iron_pass(max(0.0, elapsed - age))
                _puff(p, born_x + 19.0 * born_dir, 40.0 - age * 14.0, 2.2 + age * 3.0,
                      (1.0 - prog(age, 0.5, 0.7)) * 0.95, WHITE)
            if elapsed > 0.2:
                for j in range(2):
                    cyc = (elapsed * 1.3 + j * 0.5) % 1.0
                    sx = ix - direction * (22 + j * 24)
                    if IRON_LEFT - 6 <= sx <= IRON_RIGHT + 6:
                        _sparkle(p, sx, SHEET.top() - 4 - j * 3, 3.4 * math.sin(cyc * math.pi))
        _text(p, 110, 23, title, comic.baloo(800, 15), INK)
        _iron(p, ix, LINE_Y - 5.0, direction)

    def _zack(self, p: QPainter, t: float, f: Frame) -> None:
        p.setOpacity(p.opacity() * (1.0 - prog(t, self.end_t + DONE_S - 0.2, 0.2)))
        _mascot(p, "wink")
        pop = 1.0 if f.reduced else 0.6 + 0.4 * EASE_OUT(prog(t, self.end_t, 0.15))
        p.save()
        p.translate(162, 40)
        p.scale(pop, pop)
        _ink_shape(p, _burst(0, 0, 88, 36, 12, 0.7), YELLOW)
        font = comic.baloo(800, 21)
        width = QFontMetricsF(font).horizontalAdvance("Zack!")
        start = -(width + 20) / 2
        _check(p, start, -8, 13)
        _text(p, start + 20, 21 * 0.36, "Zack!", font, INK)
        p.restore()

    def _hint(self, p: QPainter, face: str, first: str, second: str) -> None:
        _mascot(p, face)
        _label_bubble(p, HINT_BODY, TINT)
        bold, small = _hint_fonts()
        lines = error_lines(first, second)
        steps = [BOLD_STEP if is_bold else SMALL_STEP for _line, is_bold in lines]
        y = HINT_BODY.center().y() - sum(steps) / 2
        for (line, is_bold), step in zip(lines, steps):
            font = bold if is_bold else small
            _text(p, HINT_BODY.left() + 11, y + step * 0.8, line, font, INK if is_bold else LABEL)
            y += step
