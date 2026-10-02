# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import functools
import math
import random
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtSvg import QSvgRenderer

from kira.ui import _comic as comic
from kira.ui.hud.base import EASE_IN_OUT, EASE_OUT, Frame, HudStyle, clamp, prog

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

CLOUD = QRectF(94, 3, 158, 56)
TRAIL = ((76, 30, 3.0), (85, 22, 4.2))
DRUM = QPointF(121, 31)
DRUM_SCALE = 0.9
DRUM_WORDS = (("bla", 8.5, 8), ("bla", 9.5, 8), ("blubb", 6.0, 7))
SPIN_AFTER_S = 3.0
SMOKE_AFTER_S = 3.0
SWEAT_AFTER_S = 6.0
SCENES = ("waesche", "buegeln", "zahnraeder")
SCENE_S = 5.0
IRON_PASS_S = 1.5
IRON_SCALE = 1.1
IRON_LEFT, IRON_RIGHT = 108.0, 236.0
LINE_Y = 49.0
TEXT_DASHES = ((108, 126), (131, 141), (146, 170), (175, 189), (194, 214), (219, 236))


@dataclass
class _Word:
    text: str
    born: float
    size: float
    lane: int


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


def _sfx(p: QPainter, x: float, y: float, s: str, px: float, angle: float, width: float = 3.2,
         shadow: float = 1.6) -> None:
    path = QPainterPath()
    path.addText(0, 0, comic.baloo(800, max(1, round(px))), s)
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
    p.setBrush(YELLOW)
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
        _ink_shape(p, dot, WHITE, 1.8, 1.5)


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


def _text_line(p: QPainter, ix: float, direction: int, passes: int) -> None:
    before = 4.5 * 0.42 ** passes
    after = before * 0.42
    p.setPen(QPen(INK, 3.0, *_ROUND))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for x0, x1 in TEXT_DASHES:
        steps = max(2, (x1 - x0) // 2)
        path = QPainterPath()
        for s in range(steps + 1):
            x = x0 + (x1 - x0) * s / steps
            ironed = x <= ix if direction > 0 else x >= ix
            y = LINE_Y + (after if ironed else before) * (math.sin(x * 0.95) * 0.7 + math.sin(x * 2.3 + 1.0) * 0.3)
            if s == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        p.drawPath(path)


def _iron(p: QPainter, x: float, sole_y: float, direction: int) -> None:
    p.save()
    p.translate(x, sole_y)
    p.scale(direction * IRON_SCALE, IRON_SCALE)
    body = QPainterPath(QPointF(-11, 0))
    body.lineTo(11, 0)
    body.cubicTo(QPointF(6, -4), QPointF(2, -9), QPointF(-6, -10))
    body.cubicTo(QPointF(-10, -10), QPointF(-11, -6), QPointF(-11, 0))
    body.closeSubpath()
    _ink_shape(p, body, YELLOW, 1.8, 1.4)
    handle = QPainterPath(QPointF(-7, -10))
    handle.cubicTo(QPointF(-7, -16), QPointF(2, -16), QPointF(2, -9))
    p.setPen(QPen(INK, 1.8, *_ROUND))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(handle)
    p.setPen(QPen(INK, 2.2, *_ROUND))
    p.drawLine(QPointF(-11, 0.6), QPointF(11, 0.6))
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


def _timer(p: QPainter, x: float, y: float, s: str) -> None:
    font = comic.baloo(700, 10)
    w = QFontMetricsF(font).horizontalAdvance(s) + 22
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawRoundedRect(QRectF(x - w, y, w, 16), 8, 8)
    p.setBrush(REC)
    p.drawEllipse(QPointF(x - w + 9, y + 8), 3.2, 3.2)
    _text(p, x - w + 16, y + 11.8, s, font, WHITE)


class Comic(HudStyle):
    key = "comic"

    def __init__(self) -> None:
        super().__init__()
        self._words: list[_Word] = []
        self._count = 0
        self._next_spawn = 0.0
        self._lv = 0.0
        self._rng = random.Random()
        self.scene = SCENES[0]

    def on_press(self, t: float, f: Frame) -> None:
        self._words = []
        self._count = 0
        self._next_spawn = t
        self._lv = 0.0
        self.scene = self._rng.choice(SCENES)

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
            self._words.append(_Word(WORDS[lane], t, 11 + 13 * an.level, lane))
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
            _sfx(p, x, y, word.text, word.size * scale, angle)
            p.restore()
        elapsed = self.elapsed(t)
        _timer(p, 252, 3, f"{int(elapsed // 60)}:{int(elapsed % 60):02d}")

    def _shout(self, p: QPainter) -> None:
        _mascot(p, "shout")
        _ink_shape(p, _burst(166, 40, 90, 36, 16, 0.74), YELLOW)
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
        _ink_shape(p, _cloud(CLOUD), WHITE, 2.2)
        _drum(p, age, spin, f.reduced)
        _text(p, 150, 31, title, comic.baloo(800, 15), INK)
        _text(p, 150, 47, self.caption(t, f), comic.baloo(600, 11), LABEL)

    def _gears_scene(self, p: QPainter, t: float, f: Frame, elapsed: float, title: str) -> None:
        hot = elapsed >= SMOKE_AFTER_S
        _mascot(p, "think")
        _trail(p)
        _ink_shape(p, _cloud(CLOUD), WHITE, 2.2)
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
        _ink_shape(p, _cloud(CLOUD), WHITE, 2.2)
        _text_line(p, ix, direction, passes)
        if not f.reduced:
            for j in range(4):
                age = (elapsed + j * 0.3) % 1.2
                born_x = _iron_pass(max(0.0, elapsed - age))[0]
                _puff(p, born_x + 8 * direction, 31 - age * 12, 2.4 + age * 3.0,
                      (1.0 - prog(age, 0.5, 0.7)) * 0.95, WHITE)
            if elapsed > 0.2:
                for j in range(2):
                    cyc = (elapsed * 1.3 + j * 0.5) % 1.0
                    sx = ix - direction * (14 + j * 22)
                    if IRON_LEFT <= sx <= IRON_RIGHT:
                        _sparkle(p, sx, LINE_Y - 9 - j * 3, 3.6 * math.sin(cyc * math.pi))
        _text(p, 110, 23, title, comic.baloo(800, 15), INK)
        _iron(p, ix, LINE_Y - 3.5, direction)

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
