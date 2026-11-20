# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_OUT, W, Frame, clamp, mono, prog
from kira.ui.hud.saison import (
    HINT_BODY, INK, LABEL, ROUND, SWEAT_AFTER_S, WHITE, YELLOW, Saison, ellipse, faded, polygon, sparkle, text, zack_px,
)
from kira.texte import tr

FLY_ROUTES = ((230.0, 20.0, 242.0, 12.0, 1.0), (98.0, 18.0, 88.0, 11.0, 0.9), (236.0, 56.0, 244.0, 66.0, 0.85),
              (106.0, 58.0, 94.0, 67.0, 0.8))
NEAR_TILE_LANES = ((100.0, 55.0, -10.0), cm.LANES[1], cm.LANES[2])


def rounded(x: float, y: float, w: float, h: float, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), r, r)
    return path


def ringed(p: QPainter, path: QPainterPath, fill, width: float = 1.4, ring: float = 3.8) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(WHITE, ring, *ROUND))
    p.drawPath(path)
    p.setPen(QPen(INK, width, *ROUND))
    p.setBrush(fill)
    p.drawPath(path)


def outlined(p: QPainter, path: QPainterPath, fill, width: float = 1.2) -> None:
    p.setPen(QPen(INK, width, *ROUND))
    p.setBrush(fill)
    p.drawPath(path)


def stroke(p: QPainter, x0: float, y0: float, x1: float, y1: float, color, width: float = 1.2) -> None:
    p.setPen(QPen(color, width, *ROUND))
    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


def ringed_line(p: QPainter, path: QPainterPath, color, width: float = 1.6, ring: float = 4.2) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(WHITE, ring, *ROUND))
    p.drawPath(path)
    p.setPen(QPen(INK, width + 1.4, *ROUND))
    p.drawPath(path)
    p.setPen(QPen(color, width, *ROUND))
    p.drawPath(path)


def heart(cx: float, cy: float, s: float) -> QPainterPath:
    path = QPainterPath(QPointF(cx, cy + s * 0.9))
    path.cubicTo(QPointF(cx - s * 1.3, cy + s * 0.1), QPointF(cx - s * 0.9, cy - s * 1.0), QPointF(cx, cy - s * 0.35))
    path.cubicTo(QPointF(cx + s * 0.9, cy - s * 1.0), QPointF(cx + s * 1.3, cy + s * 0.1), QPointF(cx, cy + s * 0.9))
    path.closeSubpath()
    return path


def check(p: QPainter, x: float, y: float, s: float, color=INK, width: float = 2.0) -> None:
    path = QPainterPath(QPointF(x, y + s * 0.55))
    path.lineTo(x + s * 0.38, y + s * 0.92)
    path.lineTo(x + s, y + s * 0.08)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(color, width, *ROUND))
    p.drawPath(path)


def badge_check(p: QPainter, x: float, y: float, r: float, fill, mark=INK) -> None:
    outlined(p, ellipse(x, y, r), fill, 1.2)
    check(p, x - r * 0.58, y - r * 0.62, r * 1.15, mark, 1.7)


def lettering(p: QPainter, x: float, y: float, s: str, px: float, angle: float = 0.0, fill=YELLOW,
              width: float = 2.0, shadow: float = 1.0) -> None:
    cm._sfx(p, x, y, s, px, angle, width, shadow, QColor(fill))


def pulse(frac: float, at: float, width: float) -> float:
    d = (frac - at) / width
    return math.exp(-d * d)


def twinkle(e: float, reduced: bool) -> float:
    return 1.0 if reduced else abs(math.sin(e * 4.0))


def fly_out(p: QPainter, t: float, f: Frame, k: float, draw, routes=FLY_ROUTES) -> None:
    for j, (sx, sy, ex, ey, s) in enumerate(routes):
        u = 1.0 if f.reduced else EASE_OUT(clamp(k * 1.8 - j * 0.1, 0.0, 1.0))
        if u <= 0:
            continue
        draw(p, sx + (ex - sx) * u, sy + (ey - sy) * u, s, 0.0 if f.reduced else t, j)


class Fachgebiet(Saison):
    LANES = NEAR_TILE_LANES
    CAPTIONS: dict[str, tuple[str, str, float]] = {}
    LOOKS: dict[str, tuple[tuple[int, int], str, str]] = {}
    TITLE_X = 150.0

    def caption(self, key: str, elapsed: float) -> str:
        before, after, at = self.CAPTIONS[key]
        return tr(after) if elapsed >= at else tr(before)

    def payoff(self, key: str) -> float:
        return self.CAPTIONS[key][2]

    def paint_scene(self, p: QPainter, key: str, t: float, f: Frame, elapsed: float, title: str) -> None:
        at = self.payoff(key)
        e = at + 0.6 if f.reduced else elapsed
        look, before, after = self.LOOKS[key]
        self.figure(p, self.pose("look", t, f, look=look, mouth=after if e >= at else before))
        self.cloud(p)
        p.save()
        getattr(self, "scene_" + key)(p, e, f.reduced)
        p.restore()
        text(p, self.TITLE_X, 31, title, 15)
        text(p, self.TITLE_X, 47, self.caption(key, e), 11, 600, LABEL)

    def hint_decor(self, p: QPainter) -> float:
        if self.mode == "error":
            p.save()
            self.error_decor(p, HINT_BODY.left(), HINT_BODY.top())
            p.restore()
        return 0.0

    def error_decor(self, p: QPainter, left: float, top: float) -> None:
        pass


EDEL_IVORY = QColor("#F7F2E7")
EDEL_GOLD = QColor("#C9A24E")
EDEL_GOLD_LIGHT = QColor("#E4C97E")
EDEL_GOLD_DARK = QColor("#8C6D22")
EDEL_STAMP = QColor("#B3262E")
HAIRLINE = QColor("#1A1410")
BRASS_HIGH = QColor("#F7E3A0")
BRASS_LOW = QColor("#7E5E1C")


def linear_brush(x0: float, y0: float, x1: float, y1: float, stops) -> QBrush:
    gradient = QLinearGradient(x0, y0, x1, y1)
    for at, color in stops:
        gradient.setColorAt(at, color)
    return QBrush(gradient)


def radial_brush(cx: float, cy: float, r: float, stops) -> QBrush:
    gradient = QRadialGradient(QPointF(cx, cy), r)
    for at, color in stops:
        gradient.setColorAt(at, color)
    return QBrush(gradient)


def brass_brush(x0: float, y0: float, x1: float, y1: float) -> QBrush:
    return linear_brush(x0, y0, x1, y1, ((0.0, BRASS_HIGH), (0.45, EDEL_GOLD), (1.0, BRASS_LOW)))


def filled(p: QPainter, path: QPainterPath, brush, line=HAIRLINE, width: float = 0.8) -> None:
    p.setPen(QPen(line, width, *ROUND) if line is not None else Qt.PenStyle.NoPen)
    p.setBrush(brush)
    p.drawPath(path)


def drop_shadow(p: QPainter, path: QPainterPath, dx: float = 1.6, dy: float = 2.2, alpha: float = 0.28) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    for k, a in ((1.0, alpha * 0.5), (0.6, alpha * 0.8)):
        p.setBrush(QColor(0, 0, 0, int(255 * a)))
        p.drawPath(path.translated(dx * k, dy * k))


def tile_path() -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(cm.TILE, cm.TILE.width() * 102 / 512, cm.TILE.height() * 102 / 512)
    return path


def mono_digits(p: QPainter, right: float, cy: float, elapsed: float, fill=EDEL_IVORY, edge=HAIRLINE) -> None:
    path = QPainterPath()
    path.addText(0, 0, mono(12.0, 600, 0.2), cm.clock_label(elapsed))
    box = path.boundingRect()
    path = path.translated(right - box.right(), cy - box.center().y())
    p.setPen(QPen(edge, 2.6, *ROUND))
    p.setBrush(edge)
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawPath(path)


def hourglass(p: QPainter, cx: float, cy: float, age: float, reduced: bool, size: float = 1.0) -> None:
    turn = 0.0 if reduced else (age / 1.8) % 1.0
    sand = clamp(turn / 0.8, 0.0, 1.0)
    p.save()
    p.translate(cx, cy)
    p.scale(size, size)
    p.rotate(180.0 * EASE_OUT(clamp((turn - 0.8) / 0.2, 0.0, 1.0)))
    glass = polygon(((-3.0, -4.0), (3.0, -4.0), (0.7, 0.0), (3.0, 4.0), (-3.0, 4.0), (-0.7, 0.0)))
    filled(p, glass, QColor(255, 255, 255, 150), HAIRLINE, 0.6)
    top = 3.4 * (1.0 - sand)
    if top > 0.2:
        filled(p, polygon(((-0.85 * top, -top), (0.85 * top, -top), (0.0, 0.0))), EDEL_GOLD, None)
    heap = 3.4 * sand
    if heap > 0.2:
        filled(p, polygon(((-0.85 * heap, 3.9), (0.85 * heap, 3.9), (0.0, 3.9 - heap * 0.8))), EDEL_GOLD, None)
    for y in (-4.6, 4.6):
        filled(p, rounded(-3.8, y - 0.7, 7.6, 1.4, 0.6), brass_brush(-3.8, y - 0.7, 3.8, y + 0.7), HAIRLINE, 0.5)
    p.restore()


class Edel(Fachgebiet):
    INK_COLOR = QColor("#3B2420")
    WORD_EDGE = 1.5
    HOURGLASS = (12.5, 16.0, 1.0)

    def tile(self, p: QPainter, pose) -> None:
        pass

    def emblem(self, p: QPainter, pose) -> None:
        pass

    def paint_tile(self, p: QPainter, pose) -> None:
        tile = tile_path()
        p.save()
        p.setClipPath(tile)
        self.tile(p, pose)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 70), 0.8))
        p.drawPath(tile)

    def mascot(self, p: QPainter, pose) -> None:
        self.emblem(p, pose)
        self.accessory(p, pose)

    def think(self, p: QPainter, t: float, f: Frame) -> None:
        key, t0 = self.scene_at(t, f)
        self.paint_scene(p, key, t, f, t - t0, tr("Politur") if f.polishing else tr("Erkennen"))
        if self.sweating(t):
            x, y, size = self.HOURGLASS
            hourglass(p, x, y, t - self.rel_t - SWEAT_AFTER_S, f.reduced, size)

    def paint_scene(self, p: QPainter, key: str, t: float, f: Frame, elapsed: float, title: str) -> None:
        at = self.payoff(key)
        e = at + 0.6 if f.reduced else elapsed
        look, before, after = self.LOOKS[key]
        self.figure(p, self.pose("look", t, f, look=look, mouth=after if e >= at else before))
        self.cloud(p)
        p.save()
        getattr(self, "scene_" + key)(p, e, f.reduced)
        p.restore()
        cm._text(p, self.TITLE_X, 31, title, comic.baloo(800, 15), self.INK_COLOR)
        cm._text(p, self.TITLE_X, 47, self.caption(key, e), comic.baloo(600, 11), faded(self.INK_COLOR, 0.8))

    def talk(self, p: QPainter, t: float, f: Frame) -> None:
        self.figure(p, self.pose("talk", t, f, self._lv))
        for word in self._words:
            tx, ty, angle = self.LANES[word.lane]
            tx = min(max(tx, cm.TILE.right() + 2 + word.width / 2), W - 2 - word.width / 2)
            if f.reduced:
                x, y, scale, alpha = tx, ty, 1.0, 1.0
            else:
                age = t - word.born
                k = EASE_OUT(clamp(age / cm.FLIGHT_S, 0.0, 1.0))
                x = cm.MOUTH.x() + (tx - cm.MOUTH.x()) * k
                y = cm.MOUTH.y() + (ty - cm.MOUTH.y()) * k - math.sin(k * math.pi) * 6
                scale = 0.55 + 0.45 * k
                alpha = 1.0 - prog(age, cm.LIFE_S * 0.7, cm.LIFE_S * 0.3)
            fill = word.fill
            if fill.name() == YELLOW.name():
                fill = self.WORD_FILLS[word.lane % len(self.WORD_FILLS)]
            p.save()
            p.setOpacity(p.opacity() * alpha)
            cm._sfx(p, x, y, word.text, word.size * scale, angle * 0.4, self.WORD_EDGE, 0.0, fill)
            p.restore()
        self.paint_clock(p, self.elapsed(t), f.reduced)

    def cloud(self, p: QPainter) -> None:
        for x, y, r in cm.TRAIL:
            p.setPen(QPen(self.INK_COLOR, 1.0))
            p.setBrush(EDEL_IVORY)
            p.drawEllipse(QPointF(x, y), r * 0.8, r * 0.8)
        p.setPen(QPen(self.INK_COLOR, 1.4))
        p.setBrush(EDEL_IVORY)
        p.drawRoundedRect(cm.CLOUD.adjusted(1.0, 2.0, -1.0, -2.0), 9.0, 9.0)
        p.setPen(QPen(faded(EDEL_GOLD, 0.8), 0.7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(cm.CLOUD.adjusted(4.0, 5.0, -4.0, -5.0), 6.5, 6.5)

    def shout(self, p: QPainter, t: float, f: Frame) -> None:
        self.figure(p, self.pose("shout", t, f, 1.0))
        p.save()
        p.translate(166.0, 40.0)
        p.rotate(-5.0)
        p.setPen(QPen(EDEL_STAMP, 2.4))
        p.setBrush(faded(EDEL_IVORY, 0.96))
        p.drawRoundedRect(QRectF(-60.0, -17.0, 120.0, 34.0), 5.0, 5.0)
        p.setPen(QPen(EDEL_STAMP, 0.9))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(-56.5, -13.5, 113.0, 27.0), 3.0, 3.0)
        cm._text(p, 0.0, 7.0, tr("ZU NAH!"), comic.baloo(800, 19), EDEL_STAMP, "center")
        p.restore()

    def zack(self, p: QPainter, t: float, f: Frame) -> None:
        p.save()
        p.setOpacity(p.opacity() * self.done_alpha(t))
        self.figure(p, self.pose("wink", t, f))
        pop = 1.0 if f.reduced else 0.86 + 0.14 * EASE_OUT(prog(t, self.end_t, 0.18))
        p.save()
        p.translate(170.0, 40.0)
        p.scale(pop, pop)
        p.setPen(QPen(self.INK_COLOR, 1.4))
        p.setBrush(EDEL_IVORY)
        p.drawRoundedRect(QRectF(-56.0, -13.0, 128.0, 26.0), 4.0, 4.0)
        p.setPen(QPen(faded(EDEL_GOLD, 0.9), 0.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(-53.0, -10.0, 122.0, 20.0), 2.5, 2.5)
        seal = QPainterPath()
        for i in range(32):
            a = math.pi * i / 16
            r = 15.5 if i % 2 == 0 else 13.8
            point = QPointF(-56.0 + math.cos(a) * r, math.sin(a) * r)
            if i == 0:
                seal.moveTo(point)
            else:
                seal.lineTo(point)
        seal.closeSubpath()
        filled(p, seal, brass_brush(-70.0, -14.0, -42.0, 14.0), EDEL_GOLD_DARK, 1.2)
        p.setPen(QPen(faded(EDEL_IVORY, 0.8), 0.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(-56.0, 0.0), 10.4, 10.4)
        check(p, -61.5, -5.6, 11.0, self.INK_COLOR, 2.2)
        word = tr(self.ZACK_WORD)
        px = min(18, zack_px(word))
        cm._text(p, 13.0, px * 0.36, word, comic.baloo(800, px), self.INK_COLOR, "center")
        p.restore()
        self.zack_decor(p, t, f, 1.0 if f.reduced else prog(t, self.end_t, cm.DONE_S))
        p.restore()

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        def draw(pp, x, y, size, moment, j):
            sparkle(pp, x, y, 2.6 * size, EDEL_GOLD_LIGHT)
        fly_out(p, t, f, k, draw, FLY_ROUTES)

    def hint(self, p: QPainter, t: float, f: Frame, face: str, first: str, second: str) -> None:
        self.figure(p, self.pose(face, t, f))
        body = HINT_BODY
        cy = body.center().y()
        p.setPen(QPen(self.INK_COLOR, 1.4, *ROUND))
        p.setBrush(EDEL_IVORY)
        p.drawRoundedRect(body, 10.0, 10.0)
        p.setPen(Qt.PenStyle.NoPen)
        tail = polygon(((body.left() + 2.0, cy - 6.0), (body.left() - 9.0, cy + 1.0), (body.left() + 2.0, cy + 6.0)))
        p.drawPath(tail)
        p.setPen(QPen(self.INK_COLOR, 1.4, *ROUND))
        p.drawLine(QPointF(body.left(), cy - 5.8), QPointF(body.left() - 9.0, cy + 1.0))
        p.drawLine(QPointF(body.left() - 9.0, cy + 1.0), QPointF(body.left(), cy + 5.8))
        p.setPen(QPen(faded(EDEL_GOLD, 0.8), 0.7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body.adjusted(3.5, 3.5, -3.5, -3.5), 7.0, 7.0)
        bold, small = cm._hint_fonts()
        lines = cm.error_lines(first, second)
        total = 0.0
        for _line, is_bold in lines:
            total += cm.BOLD_STEP if is_bold else cm.SMALL_STEP
        y = cy - total / 2
        for line_text, is_bold in lines:
            step = cm.BOLD_STEP if is_bold else cm.SMALL_STEP
            cm._text(p, body.left() + 12, y + step * 0.8, line_text, bold if is_bold else small,
                     self.INK_COLOR if is_bold else faded(self.INK_COLOR, 0.78))
            y += step
