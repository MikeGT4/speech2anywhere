# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import functools
import math
import random
from collections import deque
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtSvg import QSvgRenderer

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_OUT, W, Frame, HudStyle, clamp, hash2, prog

INK = cm.INK
YELLOW = cm.YELLOW
WHITE = cm.WHITE
TINT = cm.TINT
LABEL = cm.LABEL
ALARM = cm.ALARM
STEEL = cm.STEEL
SMOKE = cm.SMOKE
ROUND = cm._ROUND
TILE = cm.TILE
MOUTH = cm.MOUTH
CLOUD = cm.CLOUD
HINT_BODY = cm.HINT_BODY
SPAWN_LEVEL = cm.SPAWN_LEVEL
SPAWN_S = cm.SPAWN_S
LIFE_S = cm.LIFE_S
FLIGHT_S = cm.FLIGHT_S
DONE_S = cm.DONE_S
SCENE_S = cm.SCENE_S
SWEAT_AFTER_S = cm.SWEAT_AFTER_S
SWEAT_SHIFT = 7.5
ZACK_PX = 21
ZACK_MIN_PX = 9
ZACK_TEXT_W = 98.0
TILE_SVG = '<rect x="0" y="0" width="512" height="512" rx="102" ry="102" fill="#FFC400"/>'
BUBBLE_SVG = (f'<path d="{cm._BUBBLE}" fill="#FFFFFF" stroke="#111111" stroke-width="18" '
              'stroke-linejoin="round"/>')
_RENDERERS: dict[tuple, QSvgRenderer] = {}


def unit(i: int, salt: int) -> float:
    return hash2(i, salt) / 4294967295.0


def ellipse(cx: float, cy: float, rx: float, ry: float | None = None) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), rx, rx if ry is None else ry)
    return path


def polygon(points, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0) -> QPainterPath:
    path = QPainterPath(QPointF(dx + points[0][0] * scale, dy + points[0][1] * scale))
    for x, y in points[1:]:
        path.lineTo(dx + x * scale, dy + y * scale)
    path.closeSubpath()
    return path


def faded(color: QColor, alpha: float) -> QColor:
    out = QColor(color)
    out.setAlphaF(clamp(alpha, 0.0, 1.0) * color.alphaF())
    return out


def glow(p: QPainter, cx: float, cy: float, r: float, color: QColor, alpha: float) -> None:
    if alpha <= 0:
        return
    gradient = QRadialGradient(QPointF(cx, cy), r)
    gradient.setColorAt(0.0, faded(color, alpha))
    gradient.setColorAt(1.0, faded(color, 0.0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(gradient)
    p.drawEllipse(QPointF(cx, cy), r, r)


def sparkle(p: QPainter, cx: float, cy: float, r: float, fill: QColor = WHITE) -> None:
    if r <= 0.2:
        return
    points = []
    for i in range(8):
        a = math.pi * i / 4 - math.pi / 2
        k = r if i % 2 == 0 else r * 0.38
        points.append((cx + math.cos(a) * k, cy + math.sin(a) * k))
    p.setBrush(fill)
    p.setPen(QPen(INK, 1.0, *ROUND))
    p.drawPath(polygon(points))


def text(p: QPainter, x: float, y: float, s: str, px: int, weight: int = 800, color: QColor = INK) -> None:
    cm._text(p, x, y, s, comic.baloo(weight, px), color)


@functools.lru_cache(maxsize=8)
def zack_px(word: str) -> int:
    px = ZACK_PX
    while px > ZACK_MIN_PX and QFontMetricsF(comic.baloo(800, px)).horizontalAdvance(word) > ZACK_TEXT_W:
        px -= 1
    return px


@dataclass(frozen=True)
class Pose:
    kind: str
    level: float = 0.0
    t: float = 0.0
    look: tuple[int, int] = (0, 0)
    mouth: str = "line"
    reduced: bool = False


@dataclass
class Word:
    text: str
    born: float
    size: float
    lane: int
    width: float = 0.0
    fill: QColor = field(default_factory=lambda: QColor(YELLOW))


def _face_key(pose: Pose) -> tuple:
    if pose.kind == "look":
        return ("look", pose.look, pose.mouth)
    if pose.kind == "talk":
        return ("talk", round(clamp(pose.level, 0.0, 1.0) * 8))
    return (pose.kind, 0)


def _face_svg(key: tuple) -> str:
    if key[0] == "look":
        return cm._eye(200, *key[1]) + cm._eye(312, *key[1]) + cm._MOUTHS[key[2]]
    return cm._face(key[0], key[1] / 8)


class Saison(HudStyle):
    key = ""
    live_words = True
    SCENES: tuple[str, ...] = ("",)
    CLOCKS: tuple[str, ...] = ("",)
    LANES = cm.LANES
    WORDS = cm.WORDS
    WORD_FILLS = cm.WORD_COLORS
    ZACK_WORD = "Zack!"
    SILENCE = ("Kein Signal", "Das Mikrofon liefert Stille.")

    def __init__(self) -> None:
        super().__init__()
        self._words: list[Word] = []
        self._count = 0
        self._next_spawn = 0.0
        self._lv = 0.0
        self._rng = random.Random()
        self.scene = self.SCENES[0]
        self.clock = self.CLOCKS[0]
        self._queue: deque[str] = deque(maxlen=4)
        self._spoken = 0

    def on_press(self, t: float, f: Frame) -> None:
        self._words = []
        self._count = 0
        self._next_spawn = t
        self._lv = 0.0
        self._queue.clear()
        self._spoken = 0
        self.scene = self._rng.choice(self.SCENES)
        self.clock = self._rng.choice(self.CLOCKS)

    def feed_words(self, t: float, words: list[str]) -> None:
        if self.mode == "rec":
            self._queue.extend(w for w in words if w)

    def on_clear(self, f: Frame) -> None:
        self._words = []

    def scene_at(self, t: float, f: Frame) -> tuple[str, float]:
        step = 0 if f.reduced else max(0, int((t - self.rel_t) // SCENE_S))
        start = self.SCENES.index(self.scene)
        return self.SCENES[(start + step) % len(self.SCENES)], self.rel_t + step * SCENE_S

    def sweating(self, t: float) -> bool:
        return self.mode == "proc" and t - self.rel_t >= SWEAT_AFTER_S

    def done_alpha(self, t: float) -> float:
        return 1.0 - prog(t, self.end_t + DONE_S - 0.2, 0.2)

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        if self.mode == "done" and t - self.end_t > DONE_S:
            self.mode = "hidden"
            return
        self._lv += (an.level - self._lv) * min(1.0, dt / 0.08)
        self._words = [w for w in self._words if t - w.born < LIFE_S]
        speaking = self.mode == "rec" and not an.clip and not an.silent and an.level > SPAWN_LEVEL
        if speaking and t >= self._next_spawn:
            lane = self._count % len(self.LANES)
            if self._queue:
                word_text = self._queue.popleft()
                fill = self.WORD_FILLS[self._spoken % len(self.WORD_FILLS)]
                self._spoken += 1
            else:
                word_text, fill = self.WORDS[lane], YELLOW
            word_text, size, width = cm._fitted_word(word_text, 11 + 13 * an.level)
            self._words.append(Word(word_text, t, size, lane, width, QColor(fill)))
            self._count += 1
            self._next_spawn = t + SPAWN_S

    def pose(self, kind: str, t: float, f: Frame, level: float = 0.0, look: tuple[int, int] = (0, 0),
             mouth: str = "line") -> Pose:
        return Pose(kind, level, 0.0 if f.reduced else t, look, mouth, f.reduced)

    def svg_under(self, kind: str) -> str:
        return ""

    def svg_over(self, kind: str) -> str:
        return ""

    def accessory(self, p: QPainter, pose: Pose) -> None:
        pass

    def figure(self, p: QPainter, pose: Pose) -> None:
        key = _face_key(pose)
        full = (self.key,) + key
        renderer = _RENDERERS.get(full)
        if renderer is None:
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">' + TILE_SVG + BUBBLE_SVG
                   + self.svg_under(pose.kind) + _face_svg(key) + self.svg_over(pose.kind) + '</svg>')
            renderer = QSvgRenderer(svg.encode("utf-8"))
            _RENDERERS[full] = renderer
        renderer.render(p, TILE)
        self.accessory(p, pose)

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        pass

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        pass

    def paint_scene(self, p: QPainter, key: str, t: float, f: Frame, elapsed: float, title: str) -> None:
        pass

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        pass

    def hint_decor(self, p: QPainter) -> float:
        return 0.0

    def cloud(self, p: QPainter) -> None:
        cm._trail(p)
        cm._ink_shape(p, cm._cloud(CLOUD), TINT, 2.2)

    def paint(self, p: QPainter, t: float, f: Frame, tap, an) -> None:
        p.save()
        if self.mode == "done":
            p.setOpacity(p.opacity() * self.done_alpha(t))
        self.backdrop(p, t, f, an)
        p.restore()
        if self.mode == "rec":
            if an.clip:
                self.shout(p, t, f)
            elif an.silent:
                self.hint(p, t, f, "think", self.SILENCE[0], self.SILENCE[1])
            else:
                self.talk(p, t, f)
        elif self.mode == "proc":
            self.think(p, t, f)
        elif self.mode == "done":
            self.zack(p, t, f)
        elif self.mode == "error":
            first, second = self.message_lines()
            self.hint(p, t, f, "sad", first or "Fehler", second)

    def talk(self, p: QPainter, t: float, f: Frame) -> None:
        self.figure(p, self.pose("talk", t, f, self._lv))
        for word in self._words:
            tx, ty, angle = self.LANES[word.lane]
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
            cm._sfx(p, x, y, word.text, word.size * scale, angle, fill=word.fill)
            p.restore()
        self.paint_clock(p, self.elapsed(t), f.reduced)

    def shout(self, p: QPainter, t: float, f: Frame) -> None:
        self.figure(p, self.pose("shout", t, f, 1.0))
        cm._ink_shape(p, cm._burst(166, 40, 90, 36, 16, 0.74), ALARM)
        cm._text(p, 166, 48, "ZU NAH!", comic.baloo(800, 22), INK, "center")

    def think(self, p: QPainter, t: float, f: Frame) -> None:
        key, t0 = self.scene_at(t, f)
        self.paint_scene(p, key, t, f, t - t0, "Politur" if f.polishing else "Erkennen")
        if self.sweating(t):
            p.save()
            p.translate(SWEAT_SHIFT, 0.0)
            cm._sweat(p, 0.3 if f.reduced else t - self.rel_t - SWEAT_AFTER_S)
            p.restore()

    def zack(self, p: QPainter, t: float, f: Frame) -> None:
        p.save()
        p.setOpacity(p.opacity() * self.done_alpha(t))
        self.figure(p, self.pose("wink", t, f))
        pop = 1.0 if f.reduced else 0.6 + 0.4 * EASE_OUT(prog(t, self.end_t, 0.15))
        p.save()
        p.translate(162, 40)
        p.scale(pop, pop)
        cm._ink_shape(p, cm._burst(0, 0, 88, 36, 12, 0.7), YELLOW)
        px = zack_px(self.ZACK_WORD)
        font = comic.baloo(800, px)
        width = QFontMetricsF(font).horizontalAdvance(self.ZACK_WORD)
        check = 13 * px / ZACK_PX
        start = -(width + check + 7) / 2
        cm._check(p, start, -check * 0.62, check)
        cm._text(p, start + check + 7, px * 0.36, self.ZACK_WORD, font, INK)
        p.restore()
        self.zack_decor(p, t, f, 1.0 if f.reduced else prog(t, self.end_t, DONE_S))
        p.restore()

    def hint(self, p: QPainter, t: float, f: Frame, face: str, first: str, second: str) -> None:
        self.figure(p, self.pose(face, t, f))
        cm._label_bubble(p, HINT_BODY, TINT)
        shift = self.hint_decor(p)
        bold, small = cm._hint_fonts()
        lines = cm.error_lines(first, second)
        total = 0.0
        for _line, is_bold in lines:
            total += cm.BOLD_STEP if is_bold else cm.SMALL_STEP
        y = HINT_BODY.center().y() - total / 2 + shift
        for line, is_bold in lines:
            step = cm.BOLD_STEP if is_bold else cm.SMALL_STEP
            cm._text(p, HINT_BODY.left() + 11, y + step * 0.8, line, bold if is_bold else small,
                     INK if is_bold else LABEL)
            y += step
