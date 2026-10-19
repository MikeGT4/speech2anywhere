# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import functools
import math
from collections import deque
from dataclasses import dataclass, field, replace

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient,
)
from kira._resources import assets_dir
from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud import fighter
from kira.ui.hud.base import EASE_OUT, H, W, Frame, HudStyle, clamp, hash2, prog

INK = QColor(comic.INK)
PAPER = QColor("#FFFFFF")
YELLOW = QColor(comic.YELLOW)
ALARM = QColor(comic.RED)
LABEL = QColor(comic.LABEL)
REC = QColor("#E8590C")
WORD_FILLS = (QColor(comic.YELLOW), QColor(comic.YELLOW_HOVER), QColor("#FFA24D"))
_ROUND = cm._ROUND

PANEL = QRectF(1.5, 1.5, W - 3.0, H - 3.0)
FRAME_W = 3.0
FIGURE = QRectF(3.0, 2.0, 76.0, 76.0)
FOCUS = QPointF(41.0, 40.0)
CENTER = QPointF(156.0, 42.0)
LINE_COUNT = 84
LINE_TURN_S = 40.0
LINE_INNER = (44.0, 112.0)
LINE_OUTER = 240.0
TONE_STEP = 4.6
TONE_FROM_X = 138.0
LANES = ((108.0, 55.0, -7.0), (158.0, 29.0, 4.0), (214.0, 53.0, -5.0))
WORDS = ("HA!", "HU!", "KIAI!")
SPAWN_LEVEL = 0.3
SPAWN_S = 0.34
SHAKE_PX = 1.2
LIFE_S = 1.0
FLIGHT_S = 0.3
EXIT_S = 0.15
IMPACT_S = 0.26
DONE_S = 0.7
MAX_WORD_W = 84.0
MIN_WORD_PX = 9
BOB_S = 2.8
SWIRL_TURN_S = 1.1
NARRATION = QRectF(202.0, 6.0, 50.0, 16.0)
STRIP = QRectF(236.0, 6.0, 18.0, 68.0)
HINT = QRectF(84.0, 10.0, 134.0, 60.0)
RUMBLE = ((99.0, 20.0, 15.0), (101.0, 42.0, 18.0), (103.0, 64.0, 21.0))
SWEAT_AFTER_S = cm.SWEAT_AFTER_S
_FONT_FILES = {"sfx": "Bangers-Regular.ttf", "jp": "MangaGothicJP.ttf"}
_families: dict[str, str] = {}


@dataclass
class _Word:
    text: str
    born: float
    size: float
    lane: int
    origin: tuple[float, float]
    width: float = 0.0
    fill: QColor = field(default_factory=lambda: QColor(comic.YELLOW))


def load_fonts() -> dict[str, str]:
    if _families:
        return _families
    for key, name in _FONT_FILES.items():
        path = assets_dir() / "fonts" / name
        font_id = QFontDatabase.addApplicationFont(str(path)) if path.exists() else -1
        found = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        _families[key] = found[0] if found else ""
    return _families


def sfx_font(px: float) -> QFont:
    family = load_fonts()["sfx"]
    if not family:
        return comic.baloo(800, max(1, round(px)))
    font = QFont(family)
    font.setPixelSize(max(1, round(px)))
    return font


def jp_font(px: float) -> QFont | None:
    family = load_fonts()["jp"]
    if not family:
        return None
    font = QFont(family)
    font.setPixelSize(max(1, round(px)))
    return font


def _alpha(color: QColor, a: float) -> QColor:
    faded = QColor(color)
    faded.setAlphaF(clamp(a, 0.0, 1.0))
    return faded


def _unit(i: int, salt: int) -> float:
    return (hash2(i, salt) % 1000) / 999.0


def _text_path(s: str, font: QFont) -> QPainterPath:
    path = QPainterPath()
    path.addText(0, 0, font, s)
    box = path.boundingRect()
    path.translate(-box.center().x(), -box.center().y())
    return path


def strike_origin(clip: str) -> tuple[float, float]:
    x, y = fighter.strike_point(clip)
    scale = FIGURE.width() / fighter.VIEW
    return FIGURE.x() + x * scale, FIGURE.y() + y * scale


def _figure(p: QPainter, pose: fighter.Pose, level: float = 0.0, t: float = 0.0, dx: float = 0.0,
            dy: float = 0.0) -> None:
    fighter.draw(p, FIGURE.translated(dx, dy), pose, level, t)


def _aura(p: QPainter, cx: float, cy: float, radius: float, alpha: float) -> None:
    glow = QRadialGradient(QPointF(cx, cy), radius)
    glow.setColorAt(0.0, _alpha(YELLOW, alpha))
    glow.setColorAt(0.55, _alpha(YELLOW, alpha * 0.5))
    glow.setColorAt(1.0, _alpha(YELLOW, 0.0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QPointF(cx, cy), radius, radius)


@functools.lru_cache(maxsize=1)
def _focus_lines() -> QPainterPath:
    path = QPainterPath()
    step = 2 * math.pi / LINE_COUNT
    for i in range(LINE_COUNT):
        a = i * step + _unit(i, 1) * step * 0.9
        r0 = LINE_INNER[0] + (LINE_INNER[1] - LINE_INNER[0]) * _unit(i, 2) ** 2
        half = 0.55 + 0.9 * _unit(i, 3)
        ca, sa = math.cos(a), math.sin(a)
        path.addPolygon(QPolygonF([
            QPointF(ca * r0, sa * r0),
            QPointF(ca * LINE_OUTER - sa * half, sa * LINE_OUTER + ca * half),
            QPointF(ca * LINE_OUTER + sa * half, sa * LINE_OUTER - ca * half),
        ]))
        path.closeSubpath()
    return path


@functools.lru_cache(maxsize=1)
def _screentone() -> QPainterPath:
    path = QPainterPath()
    inner = PANEL.adjusted(3.0, 3.0, -3.0, -3.0)
    row = 0
    y = inner.top() + 2.0
    while y < inner.bottom() - 1.0:
        x = inner.left() + 2.0 + (TONE_STEP / 2 if row % 2 else 0.0)
        while x < inner.right() - 1.0:
            k = clamp((x - TONE_FROM_X) / (inner.right() - TONE_FROM_X), 0.0, 1.0)
            radius = 1.15 * k ** 0.75
            if radius > 0.2:
                path.addEllipse(QPointF(x, y), radius, radius)
            x += TONE_STEP
        y += TONE_STEP * 0.87
        row += 1
    return path


def _panel(p: QPainter) -> None:
    p.setPen(QPen(INK, FRAME_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    p.setBrush(PAPER)
    p.drawRect(PANEL)


def _tone(p: QPainter, alpha: float) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_alpha(INK, alpha))
    p.drawPath(_screentone())


def _focus(p: QPainter, t: float, alpha: float, turn_s: float, reduced: bool) -> None:
    if alpha <= 0.0:
        return
    p.save()
    p.setClipRect(PANEL.adjusted(1.5, 1.5, -1.5, -1.5))
    p.translate(FOCUS)
    if not reduced:
        p.rotate(360.0 * (t % turn_s) / turn_s)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_alpha(INK, alpha))
    p.drawPath(_focus_lines())
    p.restore()


def _gloom(p: QPainter, alpha: float) -> None:
    p.setPen(QPen(_alpha(INK, alpha), 1.1, *_ROUND))
    for i in range(14):
        x = 86.0 + i * 12.0 + _unit(i, 4) * 6.0
        p.drawLine(QPointF(x, PANEL.top() + 1.5), QPointF(x, PANEL.top() + 6.0 + _unit(i, 5) * 14.0))


def _ghost(p: QPainter, x: float, y: float, s: str, px: float, angle: float, alpha: float) -> None:
    font = jp_font(px)
    if font is None:
        return
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_alpha(INK, alpha))
    p.drawPath(_text_path(s, font))
    p.restore()


def _rumble(p: QPainter, alpha: float) -> None:
    for x, y, px in RUMBLE:
        _ghost(p, x, y, "ゴ", px, -14.0, alpha)


def _lettering(p: QPainter, x: float, y: float, s: str, px: float, angle: float, fill: QColor,
               scale: float = 1.0, alpha: float = 1.0, outline: float = 2.8, shadow: float = 2.0,
               edge: QColor = INK, font: QFont | None = None) -> None:
    path = _text_path(s, font or sfx_font(px))
    p.save()
    p.setOpacity(p.opacity() * alpha)
    p.translate(x, y)
    p.rotate(angle)
    p.scale(scale, scale)
    p.setPen(QPen(edge, outline, *_ROUND))
    p.setBrush(edge)
    if shadow > 0:
        p.drawPath(path.translated(shadow, shadow))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawPath(path)
    p.restore()


def _impact(p: QPainter, x: float, y: float, r: float, k: float) -> None:
    p.save()
    p.setOpacity(p.opacity() * (1.0 - k))
    p.setPen(QPen(INK, 1.3, *_ROUND))
    for i in range(7):
        a = -math.pi / 2 + i * 2 * math.pi / 7 + 0.3
        r0 = r + 2.0 + 10.0 * k
        r1 = r0 + 2.0 + 5.0 * (1.0 - k)
        p.drawLine(QPointF(x + math.cos(a) * r0, y + math.sin(a) * r0 * 0.7),
                   QPointF(x + math.cos(a) * r1, y + math.sin(a) * r1 * 0.7))
    p.restore()


def _word_width(text: str, px: float) -> float:
    return _text_path(text, sfx_font(px)).boundingRect().width()


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


def _box(p: QPainter, rect: QRectF, width: float = 2.2, shadow: float = 2.5) -> None:
    path = QPainterPath()
    path.addRect(rect)
    cm._ink_shape(p, path, PAPER, width, shadow)


def _narration(p: QPainter, elapsed: float) -> None:
    _box(p, NARRATION, 1.8, 2.0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(REC)
    p.drawEllipse(QPointF(NARRATION.left() + 9.0, NARRATION.center().y()), 3.2, 3.2)
    label = f"{int(elapsed // 60)}:{int(elapsed % 60):02d}"
    p.setBrush(INK)
    p.drawPath(_text_path(label, sfx_font(12)).translated(NARRATION.left() + 32.0, NARRATION.center().y() + 0.5))


def _vertical(p: QPainter, rect: QRectF, text: str, font: QFont, color: QColor = INK) -> None:
    pitch = min(font.pixelSize() * 1.08, rect.height() / max(1, len(text)))
    y = rect.center().y() - pitch * (len(text) - 1) / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    for ch in text:
        path = QPainterPath()
        path.addText(0, 0, font, ch)
        box = path.boundingRect()
        p.save()
        p.translate(rect.center().x(), y)
        if ch == "ー":
            p.rotate(90)
        p.drawPath(path.translated(-box.center().x(), -box.center().y()))
        p.restore()
        y += pitch


def _strip(p: QPainter, latin: str, jp: str) -> None:
    _box(p, STRIP, 2.0, 2.0)
    font = jp_font(11)
    if font is None:
        _vertical(p, STRIP.adjusted(0, 4, 0, -4), latin, sfx_font(9.5))
    else:
        _vertical(p, STRIP.adjusted(0, 4, 0, -4), jp, font)


def _swirl(p: QPainter, cx: float, cy: float, t: float, reduced: bool) -> None:
    p.save()
    p.translate(cx, cy)
    _aura(p, 0.0, 0.0, 36.0, 0.95)
    if not reduced:
        p.rotate(360.0 * (t % SWIRL_TURN_S) / SWIRL_TURN_S)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_alpha(INK, 0.42))
    outer, inner = QRectF(-32, -32, 64, 64), QRectF(-14, -14, 28, 28)
    for i in range(12):
        a0 = i * 30.0
        path = QPainterPath()
        path.arcMoveTo(outer, a0)
        path.arcTo(outer, a0, 7.0)
        path.arcTo(inner, a0 + 7.0, -7.0)
        path.closeSubpath()
        p.drawPath(path)
    p.restore()


def _wrap(text: str, metrics: QFontMetricsF, width: float, limit: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and metrics.horizontalAdvance(f"{lines[-1]} {word}") <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    if len(lines) > limit:
        rest = " ".join(lines[limit - 1:])
        lines = lines[:limit - 1] + [metrics.elidedText(rest, Qt.TextElideMode.ElideRight, width)]
    return lines


def _caption(p: QPainter, first: str, second: str) -> None:
    _box(p, HINT)
    bold, small = cm._hint_fonts()
    width = HINT.width() - 18.0
    lines = [(line, True) for line in _wrap(first, QFontMetricsF(bold), width, 2)]
    if second:
        lines += [(line, False) for line in _wrap(second, QFontMetricsF(small), width, 2)]
    steps = [cm.BOLD_STEP if is_bold else cm.SMALL_STEP for _line, is_bold in lines]
    y = HINT.center().y() - sum(steps) / 2
    for (line, is_bold), step in zip(lines, steps):
        cm._text(p, HINT.left() + 10.0, y + step * 0.8, line, bold if is_bold else small, INK if is_bold else LABEL)
        y += step


class Manga(HudStyle):
    key = "manga"
    live_words = True

    def __init__(self) -> None:
        super().__init__()
        self._words: list[_Word] = []
        self._count = 0
        self._next_spawn = 0.0
        self._lv = 0.0
        self._queue: deque[str] = deque(maxlen=4)
        self._clip = ""
        self._clip_t0 = -9.0
        self._clip_start = fighter.STANCE
        self._block_t0 = -9.0
        self._listen_t0 = -9.0
        self._was_clip = False
        self._was_silent = False

    def on_press(self, t: float, f: Frame) -> None:
        self._words = []
        self._count = 0
        self._next_spawn = t
        self._lv = 0.0
        self._queue.clear()
        self._clip = ""
        self._clip_t0 = -9.0
        self._clip_start = fighter.STANCE
        self._was_clip = False
        self._was_silent = False

    def feed_words(self, t: float, words: list[str]) -> None:
        if self.mode == "rec":
            self._queue.extend(w for w in words if w)

    def on_clear(self, f: Frame) -> None:
        self._words = []

    def sweating(self, t: float) -> bool:
        return self.mode == "proc" and t - self.rel_t >= SWEAT_AFTER_S

    def pose(self, t: float, f: Frame) -> fighter.Pose:
        if f.reduced:
            return fighter.STANCE
        if self._clip and t - self._clip_t0 < fighter.duration(self._clip):
            return fighter.clip_pose(self._clip, t - self._clip_t0, self._clip_start)
        return fighter.idle("stance", t)

    def striking(self, t: float) -> bool:
        return bool(self._clip) and t - self._clip_t0 < fighter.duration(self._clip)

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        if self.mode == "done" and t - self.end_t > DONE_S:
            self.mode = "hidden"
            return
        self._lv += (an.level - self._lv) * min(1.0, dt / 0.08)
        self._words = [w for w in self._words if t - w.born < LIFE_S]
        if an.clip and not self._was_clip:
            self._block_t0 = t
        if an.silent and not self._was_silent:
            self._listen_t0 = t
        self._was_clip, self._was_silent = bool(an.clip), bool(an.silent)
        speaking = self.mode == "rec" and not an.clip and not an.silent and an.level > SPAWN_LEVEL
        if speaking and t >= self._next_spawn:
            lane = self._count % len(LANES)
            self._clip_start = self.pose(t, f)
            self._clip = fighter.STRIKES[self._count % len(fighter.STRIKES)]
            self._clip_t0 = t
            if self._queue:
                text = self._queue.popleft().upper()
                fill = WORD_FILLS[self._count % len(WORD_FILLS)]
            else:
                text, fill = WORDS[lane], YELLOW
            text, size, width = _fitted_word(text, 12 + 12 * an.level)
            self._words.append(_Word(text, t, size, lane, strike_origin(self._clip), width, QColor(fill)))
            self._count += 1
            self._next_spawn = t + SPAWN_S

    def paint(self, p: QPainter, t: float, f: Frame, tap, an) -> None:
        if self.mode == "rec":
            if an.clip:
                self._shout(p, t, f)
            elif an.silent:
                self._silence(p, t, f)
            else:
                self._talk(p, t, f)
        elif self.mode == "proc":
            self._think(p, t, f)
        elif self.mode == "done":
            self._zack(p, t, f)
        elif self.mode == "error":
            self._fail(p, t, f)

    def _talk(self, p: QPainter, t: float, f: Frame) -> None:
        _panel(p)
        _tone(p, 0.15)
        _ghost(p, 160.0, 44.0, "ペラペラ", 30, -8.0, 0.09)
        _focus(p, t, 0.14 + 0.3 * self._lv, LINE_TURN_S, f.reduced)
        _figure(p, self.pose(t, f), self._lv, t)
        for word in self._words:
            tx, ty, angle = LANES[word.lane]
            tx = min(max(tx, 84.0 + word.width / 2), 250.0 - word.width / 2)
            if f.reduced:
                _lettering(p, tx, ty, word.text, word.size, angle, word.fill)
                continue
            age = t - word.born
            k = EASE_OUT(clamp(age / FLIGHT_S, 0.0, 1.0))
            x = word.origin[0] + (tx - word.origin[0]) * k
            y = word.origin[1] + (ty - word.origin[1]) * k - math.sin(k * math.pi) * 8.0
            scale = 0.45 + 0.55 * k
            alpha = clamp(age / 0.05, 0.0, 1.0)
            left = LIFE_S - age
            if left < EXIT_S:
                e = 1.0 - left / EXIT_S
                alpha *= 1.0 - e
                scale *= 1.0 - 0.12 * e
            _lettering(p, x, y, word.text, word.size, angle * k, word.fill, scale, alpha)
            if FLIGHT_S <= age < FLIGHT_S + IMPACT_S:
                _impact(p, tx, ty, word.width / 2 + 4.0, (age - FLIGHT_S) / IMPACT_S)
        _narration(p, self.elapsed(t))

    def _shout(self, p: QPainter, t: float, f: Frame) -> None:
        _panel(p)
        _focus(p, t, 0.55, 2.0, f.reduced)
        if f.reduced:
            _figure(p, fighter.BLOCK)
        else:
            age = t - self._block_t0
            shake = SHAKE_PX * math.sin(2 * math.pi * 14.0 * t) if age >= fighter.duration("block") else 0.0
            _figure(p, fighter.clip_pose("block", age), 0.0, t, shake)
        cm._ink_shape(p, cm._burst(CENTER.x() - 4.0, CENTER.y(), 76.0, 33.0, 16, 0.74), ALARM)
        _lettering(p, CENTER.x() - 4.0, CENTER.y() + 1.0, "ZU NAH!", 22, -3.0, INK, outline=2.0, shadow=0.0, edge=PAPER)
        _strip(p, "ZU NAH", "ギャー")

    def _silence(self, p: QPainter, t: float, f: Frame) -> None:
        _panel(p)
        _tone(p, 0.15)
        _focus(p, t, 0.08, LINE_TURN_S, f.reduced)
        if f.reduced:
            _figure(p, fighter.LISTEN)
        else:
            age = t - self._listen_t0
            pose = fighter.clip_pose("listen", age)
            if age >= fighter.duration("listen"):
                pose = fighter.wobble(pose, t, 5.0, 0.55)
            _figure(p, pose, 0.0, t)
        _lettering(p, 70.0, 11.0, "?", 15, 12.0, INK, outline=2.0, shadow=0.0, edge=PAPER)
        _caption(p, "Kein Signal", "Das Mikrofon liefert Stille.")
        _strip(p, "STILLE", "シーン")

    def _think(self, p: QPainter, t: float, f: Frame) -> None:
        _panel(p)
        _tone(p, 0.15)
        _rumble(p, 0.16)
        _focus(p, t, 0.12, LINE_TURN_S, f.reduced)
        bob = 0.0 if f.reduced else math.sin(t * 2 * math.pi / BOB_S) * 1.6
        _aura(p, FOCUS.x(), FOCUS.y() + 8.0, 40.0, 0.8)
        _figure(p, fighter.MEDITATE if f.reduced else fighter.idle("meditate", t), 0.0, t, 0.0, bob)
        _swirl(p, CENTER.x(), CENTER.y(), t, f.reduced)
        title = "POLITUR" if f.polishing else "ERKENNEN"
        _lettering(p, CENTER.x(), CENTER.y() + 1.0, title, 18, 0.0, PAPER, outline=2.6, shadow=1.6)
        cm._dots(p, CENTER.x(), CENTER.y() + 23.0, 0.0 if f.reduced else t)
        _strip(p, "DENKT", "ウーン")
        if self.sweating(t):
            age = 0.3 if f.reduced else t - self.rel_t - SWEAT_AFTER_S
            for j in range(2):
                cyc = (age / 1.3 + j * 0.5) % 1.0
                cm._plewd(p, 62.0 + cyc * 5.0 + j * 6.0, 10.0 + cyc * 9.0 + bob - j * 4.0, 4.4, 24.0 + j * 14.0,
                          1.0 - prog(cyc, 0.55, 0.45))

    def _zack(self, p: QPainter, t: float, f: Frame) -> None:
        p.setOpacity(p.opacity() * (1.0 - prog(t, self.end_t + DONE_S - 0.2, 0.2)))
        _panel(p)
        _tone(p, 0.15)
        flash = 1.0 if f.reduced else 1.0 - prog(t, self.end_t, 0.5)
        _focus(p, t, 0.12 + 0.45 * flash, LINE_TURN_S, f.reduced)
        pop = 1.0 if f.reduced else EASE_OUT(prog(t, self.end_t, 0.15))
        _figure(p, fighter.VICTORY if f.reduced else fighter.clip_pose("victory", t - self.end_t), 0.0, t)
        p.save()
        p.translate(CENTER)
        p.scale(0.6 + 0.4 * pop, 0.6 + 0.4 * pop)
        cm._ink_shape(p, cm._burst(0, 0, 80.0, 33.0, 12, 0.7), YELLOW)
        font = sfx_font(24)
        width = QFontMetricsF(font).horizontalAdvance("ZACK!")
        start = -(width + 20) / 2
        cm._check(p, start, -9.0, 14.0)
        cm._text(p, start + 20.0, 24 * 0.36, "ZACK!", font, INK)
        p.restore()
        stamp = 1.0 if f.reduced else EASE_OUT(prog(t, self.end_t + 0.1, 0.3))
        font_jp = jp_font(12)
        if stamp > 0 and font_jp is not None:
            _lettering(p, 232.0, 18.0, "ドン", 12, -13.0, PAPER, 1.0 + 1.2 * (1.0 - stamp), stamp, 1.6, 1.2,
                       font=font_jp)

    def _fail(self, p: QPainter, t: float, f: Frame) -> None:
        _panel(p)
        _tone(p, 0.22)
        _gloom(p, 0.45)
        if f.reduced:
            _figure(p, fighter.KO, 0.0, 0.0)
        else:
            age = t - self.end_t
            pose = fighter.clip_pose("ko", age)
            if age >= fighter.duration("ko"):
                pose = fighter.wobble(pose, t, 4.0, 0.9)
            _figure(p, pose, 0.0, t)
        first, second = self.message_lines()
        _caption(p, first or "Fehler", second)
        _strip(p, "FEHLER", "ガーン")
