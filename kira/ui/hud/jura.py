# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from kira.ui.hud.base import EASE_OUT, clamp, mono
from kira.ui.hud.comic import TILE
from kira.ui.hud.fachgebiet import (
    EDEL_GOLD, EDEL_GOLD_DARK, EDEL_GOLD_LIGHT, EDEL_IVORY, HAIRLINE, BRASS_HIGH, BRASS_LOW, Edel, brass_brush,
    drop_shadow, filled, linear_brush, mono_digits, radial_brush, rounded,
)
from kira.ui.hud.saison import ROUND, WHITE, Pose, ellipse, faded, polygon, sparkle
from kira.texte import N_

WALNUT = QColor("#3B2A21")
WALNUT_LIGHT = QColor("#5A4334")
WALNUT_DEEP = QColor("#24180F")
OXBLOOD = QColor("#6A1E28")
OXBLOOD_LIGHT = QColor("#8B2C38")
OXBLOOD_DEEP = QColor("#3E0F16")
PARCHMENT = QColor("#F6EED9")
PARCHMENT_DEEP = QColor("#E6D8BA")
CREAM = QColor("#F5EFE2")
DIAL_SHADE = QColor("#D9CFBA")
WRITING = QColor("#2B2420")
CHAIN = QColor("#8C6D2A")
GRAIN = QColor(255, 235, 210, 26)

PIVOT = QPointF(35.0, 27.5)
BEAM_HALF = 20.0
PAN_DROP = 17.0
DIAL_CLOCK = (244.0, 14.0)
DAYS = (26, 27, 28, 29, 30)


def beam_tilt(pose: Pose) -> float:
    t = 0.0 if pose.reduced else pose.t
    if pose.kind == "talk":
        return 0.0 if pose.reduced else 11.0 * pose.level * math.sin(t * 2.6)
    if pose.kind == "shout":
        return 0.0 if pose.reduced else 15.0 * math.sin(t * 18.0)
    if pose.kind == "sad":
        return 13.0
    if pose.kind == "wink":
        return 0.0
    tilt = 0.0 if pose.reduced else 3.0 * math.sin(t * 1.3)
    if pose.kind == "look":
        tilt += pose.look[0] * 0.15
    return tilt


def _walnut(p: QPainter, box: QRectF) -> None:
    p.fillRect(box, linear_brush(0, box.top(), 0, box.bottom(), ((0.0, WALNUT_LIGHT), (1.0, WALNUT))))
    p.setPen(QPen(GRAIN, 0.7))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for k in range(12):
        x = box.left() + 4 + k * 5.4
        grain = QPainterPath(QPointF(x, box.top()))
        grain.cubicTo(QPointF(x + 2.0, box.top() + 20), QPointF(x - 2.0, box.top() + 44),
                      QPointF(x + 1.0, box.bottom()))
        p.drawPath(grain)


def _pan(p: QPainter, ex: float, ey: float) -> None:
    py = ey + PAN_DROP
    p.setPen(QPen(CHAIN, 0.6))
    for dx in (-4.4, 0.0, 4.4):
        p.drawLine(QPointF(ex, ey), QPointF(ex + dx, py))
    pan = QPainterPath(QPointF(ex - 6.4, py))
    pan.cubicTo(QPointF(ex - 5.6, py + 4.6), QPointF(ex + 5.6, py + 4.6), QPointF(ex + 6.4, py))
    pan.closeSubpath()
    drop_shadow(p, pan, 1.0, 1.6, 0.25)
    filled(p, pan, brass_brush(ex - 6, py, ex + 6, py + 4), HAIRLINE, 0.7)
    p.setPen(QPen(BRASS_HIGH, 0.6))
    p.drawLine(QPointF(ex - 5.6, py + 0.4), QPointF(ex + 5.6, py + 0.4))


def _dial_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = DIAL_CLOCK
    drop_shadow(p, ellipse(cx, cy, 8.8), 1.0, 1.4, 0.3)
    filled(p, ellipse(cx, cy, 8.8), brass_brush(cx - 8, cy - 8, cx + 8, cy + 8), HAIRLINE, 0.8)
    filled(p, ellipse(cx, cy, 6.8), radial_brush(cx - 2, cy - 2, 9, ((0.0, WHITE), (1.0, CREAM))), BRASS_LOW, 0.5)
    p.setPen(QPen(HAIRLINE, 0.6))
    for k in range(12):
        a = math.tau * k / 12
        inner = 5.0 if k % 3 == 0 else 5.6
        p.drawLine(QPointF(cx + math.sin(a) * inner, cy - math.cos(a) * inner),
                   QPointF(cx + math.sin(a) * 6.3, cy - math.cos(a) * 6.3))
    seconds = (math.floor(elapsed) if reduced else elapsed) % 60
    a = math.tau * seconds / 60
    p.setPen(QPen(OXBLOOD, 1.1, *ROUND))
    p.drawLine(QPointF(cx - math.sin(a) * 1.4, cy + math.cos(a) * 1.4),
               QPointF(cx + math.sin(a) * 5.8, cy - math.cos(a) * 5.8))
    filled(p, ellipse(cx, cy, 1.1), brass_brush(cx - 1, cy - 1, cx + 1, cy + 1), HAIRLINE, 0.4)
    since = elapsed % 60
    if not reduced and elapsed >= 60 and since < 0.6:
        sparkle(p, cx + 6.0, cy - 6.0, 3.0 * math.sin(since / 0.6 * math.pi), WHITE)
    mono_digits(p, cx - 12.0, cy + 0.4, elapsed)


def _seal(p: QPainter, cx: float, cy: float, r: float) -> None:
    wax = QPainterPath()
    for i in range(16):
        a = math.tau * i / 16
        rr = r + (0.55 if i % 2 == 0 else -0.35)
        point = QPointF(cx + math.cos(a) * rr, cy + math.sin(a) * rr)
        if i == 0:
            wax.moveTo(point)
        else:
            wax.lineTo(point)
    wax.closeSubpath()
    for side in (-1, 1):
        tail = polygon(((cx + side * 1.4, cy + r * 0.6), (cx + side * 4.4, cy + r + 4.6),
                        (cx + side * 2.2, cy + r + 3.4), (cx + side * 0.2, cy + r + 4.8),
                        (cx - side * 0.8, cy + r * 0.6)))
        filled(p, tail, OXBLOOD, OXBLOOD_DEEP, 0.5)
    drop_shadow(p, wax, 0.8, 1.2, 0.35)
    wax_brush = radial_brush(cx - r * 0.3, cy - r * 0.3, r * 1.4, ((0.0, OXBLOOD_LIGHT), (1.0, OXBLOOD_DEEP)))
    filled(p, wax, wax_brush, OXBLOOD_DEEP, 0.5)
    p.setPen(QPen(faded(OXBLOOD_DEEP, 0.9), 0.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx, cy), r * 0.68, r * 0.68)
    glyph = QPainterPath()
    glyph.addText(0, 0, mono(r * 1.6, 600, 0.0), "§")
    box = glyph.boundingRect()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(OXBLOOD_DEEP)
    p.drawPath(glyph.translated(cx - box.center().x(), cy - box.center().y()))


def _knob(p: QPainter, cx: float, cy: float, r: float) -> None:
    shine = radial_brush(cx - r * 0.25, cy - r * 0.3, r * 1.25, ((0.0, BRASS_HIGH), (1.0, BRASS_LOW)))
    filled(p, ellipse(cx, cy, r), shine)


def _day(p: QPainter, cx: float, cy: float, day: int) -> None:
    digits = QPainterPath()
    digits.addText(0, 0, mono(17.0, 600, 0.0), str(day))
    box = digits.boundingRect()
    filled(p, digits.translated(cx - box.center().x(), cy - box.center().y()), WRITING, None)


class Jura(Edel):
    key = "jura"
    SCENES = ("akte", "gesetz", "kalender")
    CLOCKS = ("kanzleiuhr",)
    WORDS = (N_("bla"), N_("Einspruch!"), N_("bla"))
    WORD_FILLS = (EDEL_IVORY, EDEL_GOLD_LIGHT, QColor("#E9DCC0"))
    ZACK_WORD = N_("Recht so!")
    SILENCE = (N_("Kein Signal"), N_("Das Mikrofon verweigert die Aussage."))
    INK_COLOR = QColor("#3B2420")
    FIGURE_SCALE = 0.9907
    FIGURE_SHIFT = (-0.372, -4.396)
    HOURGLASS = (14.25, 13.75, 0.8)
    CAPTIONS = {
        "akte": (N_("fertigt aus …"), N_("ausgefertigt!"), 2.4),
        "gesetz": (N_("schlägt nach …"), N_("§ gefunden!"), 2.3),
        "kalender": (N_("Frist läuft …"), N_("fristgerecht!"), 2.4),
    }
    LOOKS = {
        "akte": ((10, 10), "line", "smile"),
        "gesetz": ((10, 8), "line", "o"),
        "kalender": ((10, 6), "line", "smile"),
    }

    def tile(self, p: QPainter, pose: Pose) -> None:
        _walnut(p, TILE)

    def emblem(self, p: QPainter, pose: Pose) -> None:
        plinth = rounded(18.0, 63.0, 34.0, 7.0, 2.0)
        drop_shadow(p, plinth)
        filled(p, plinth, linear_brush(0, 63, 0, 70, ((0.0, WALNUT_LIGHT), (1.0, WALNUT_DEEP))))
        filled(p, polygon(((28.0, 63.0), (42.0, 63.0), (39.0, 59.5), (31.0, 59.5))), brass_brush(28, 59, 42, 63))
        filled(p, rounded(33.9, 26.0, 2.2, 34.0, 1.0), brass_brush(33.9, 0, 36.1, 0))
        dial = QPainterPath(QPointF(27.0, 27.5))
        dial.arcTo(QRectF(27.0, 19.5, 16.0, 16.0), 180, -180)
        dial.closeSubpath()
        filled(p, dial, linear_brush(0, 19, 0, 28, ((0.0, CREAM), (1.0, DIAL_SHADE))), HAIRLINE, 0.7)
        p.setPen(QPen(HAIRLINE, 0.5))
        for k in range(7):
            a = math.radians(180 - 30 * k)
            p.drawLine(QPointF(35 + math.cos(a) * 7.6, 27.5 - math.sin(a) * 7.6),
                       QPointF(35 + math.cos(a) * 6.4, 27.5 - math.sin(a) * 6.4))

    def accessory(self, p: QPainter, pose: Pose) -> None:
        tilt = beam_tilt(pose)
        rad = math.radians(tilt)
        needle = math.radians(-90 + tilt)
        p.setPen(QPen(OXBLOOD, 0.9, *ROUND))
        p.drawLine(PIVOT, QPointF(PIVOT.x() + math.cos(needle) * 7.0, PIVOT.y() + math.sin(needle) * 7.0))
        for side in (-1, 1):
            _pan(p, PIVOT.x() + side * BEAM_HALF * math.cos(rad), PIVOT.y() + side * BEAM_HALF * math.sin(rad))
        beam = QPainterPath(QPointF(PIVOT.x() - 20.6 * math.cos(rad), PIVOT.y() - 20.6 * math.sin(rad)))
        beam.lineTo(PIVOT.x() + 20.6 * math.cos(rad), PIVOT.y() + 20.6 * math.sin(rad))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for color, width, lift in ((HAIRLINE, 3.4, 0.0), (EDEL_GOLD, 2.2, 0.0), (BRASS_HIGH, 0.6, -0.6)):
            p.setPen(QPen(color, width, *ROUND))
            p.drawPath(beam.translated(0, lift))
        _knob(p, PIVOT.x(), PIVOT.y(), 2.4)
        _knob(p, 35.0, 23.0, 1.8)
        if pose.kind == "wink":
            sparkle(p, 50.0, 22.0, 2.8, WHITE)

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _dial_clock(p, elapsed, reduced)

    def scene_akte(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, w, h = 104.0, 9.0, 34.0, 42.0
        at = self.payoff("akte")
        sheet = rounded(x0, y0, w, h, 1.5)
        drop_shadow(p, sheet, 1.4, 1.8, 0.22)
        filled(p, sheet, linear_brush(x0, y0, x0 + w, y0 + h, ((0.0, PARCHMENT), (1.0, PARCHMENT_DEEP))), HAIRLINE, 0.7)
        written = 1.0 if reduced else clamp(e / (at - 0.2), 0.0, 1.0)
        lengths = (24.0, 20.0, 25.0, 17.0, 12.0)
        pen_at = None
        for k, length in enumerate(lengths):
            part = clamp(written * len(lengths) - k, 0.0, 1.0)
            if part <= 0:
                continue
            y = y0 + 9.0 + k * 5.6
            x = x0 + 4.5
            p.setPen(QPen(WRITING, 0.9, *ROUND))
            p.drawLine(QPointF(x, y), QPointF(x + length * part, y))
            if 0.0 < part < 1.0:
                pen_at = QPointF(x + length * part, y)
        if pen_at is not None and not reduced:
            p.save()
            p.translate(pen_at)
            p.rotate(-40)
            barrel = linear_brush(0, -1.5, 0, 1.5, ((0.0, QColor("#3A3A3E")), (1.0, HAIRLINE)))
            filled(p, rounded(2.4, -1.5, 13.0, 3.0, 1.4), barrel)
            filled(p, rounded(8.0, -1.6, 1.4, 3.2, 0.4), brass_brush(8, -1.6, 9.4, 1.6), None)
            filled(p, polygon(((0.0, 0.0), (2.6, -1.3), (2.6, 1.3))), brass_brush(0, -1.3, 2.6, 1.3), HAIRLINE, 0.4)
            p.restore()
        if e >= at:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.22, 0.0, 1.0))
            p.save()
            p.translate(x0 + w - 7.0, y0 + h - 9.0)
            p.scale(pop, pop)
            _seal(p, 0.0, 0.0, 6.0)
            p.restore()

    def scene_gesetz(self, p: QPainter, e: float, reduced: bool) -> None:
        cx, cy = 121.0, 31.0
        at = self.payoff("gesetz")
        cover = polygon(((cx - 22.0, cy - 12.0), (cx, cy - 9.5), (cx + 22.0, cy - 12.0), (cx + 22.0, cy + 14.0),
                         (cx, cy + 16.5), (cx - 22.0, cy + 14.0)))
        drop_shadow(p, cover, 1.4, 1.8, 0.3)
        leather = linear_brush(cx - 22, 0, cx + 22, 0, ((0.0, OXBLOOD_DEEP), (0.5, OXBLOOD), (1.0, OXBLOOD_DEEP)))
        filled(p, cover.translated(0, 1.6), leather, HAIRLINE, 0.7)
        for side in (-1, 1):
            page = polygon(((cx, cy - 10.5), (cx + side * 20.0, cy - 13.0), (cx + side * 20.0, cy + 12.0),
                            (cx, cy + 14.5)))
            paper = linear_brush(cx, 0, cx + side * 20, 0, ((0.0, PARCHMENT_DEEP), (0.3, PARCHMENT), (1.0, CREAM)))
            filled(p, page, paper, HAIRLINE, 0.6)
            p.setPen(QPen(faded(WRITING, 0.35), 0.7))
            for k in range(5 if side < 0 else 2):
                y = cy - 6.5 + k * 4.0
                p.drawLine(QPointF(cx + side * 4.0, y + 0.4), QPointF(cx + side * 16.5, y - 0.5))
        if not reduced and e < at - 0.15:
            k = (e / 0.36) % 1.0
            span = 20.0 * math.cos(k * math.pi)
            lift = math.sin(k * math.pi) * 6.0
            flap = polygon(((cx, cy - 10.5), (cx + span, cy - 13.0 - lift), (cx + span, cy + 12.0 - lift),
                            (cx, cy + 14.5)))
            filled(p, flap, CREAM, HAIRLINE, 0.6)
        ribbon = QPainterPath(QPointF(cx + 1.0, cy - 10.0))
        ribbon.cubicTo(QPointF(cx + 2.0, cy), QPointF(cx + 1.0, cy + 10.0), QPointF(cx + 3.0, cy + 20.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(HAIRLINE, 2.4))
        p.drawPath(ribbon)
        p.setPen(QPen(EDEL_GOLD, 1.4))
        p.drawPath(ribbon)
        if e >= at:
            glow_k = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.25, 0.0, 1.0))
            glyph = QPainterPath()
            glyph.addText(0, 0, mono(15.0, 600, 0.0), "§")
            box = glyph.boundingRect()
            glyph = glyph.translated(cx + 10.5 - box.center().x(), cy + 1.0 - box.center().y())
            p.save()
            p.setOpacity(p.opacity() * glow_k)
            filled(p, glyph, brass_brush(cx + 5, cy - 7, cx + 16, cy + 9), EDEL_GOLD_DARK, 0.4)
            p.restore()
            sparkle(p, cx + 18.0, cy - 12.0, 2.6 if reduced else 2.6 * abs(math.sin(e * 4.0)), WHITE)

    def scene_kalender(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, w, h = 105.0, 15.0, 32.0, 32.0
        at = self.payoff("kalender")
        block = rounded(x0, y0, w, h, 2.0)
        drop_shadow(p, block, 1.4, 1.8, 0.25)
        for k in (2.0, 1.0):
            filled(p, rounded(x0 + k, y0 + k, w, h, 2.0), PARCHMENT_DEEP, HAIRLINE, 0.5)
        filled(p, block, linear_brush(x0, y0, x0, y0 + h, ((0.0, CREAM), (1.0, PARCHMENT))), HAIRLINE, 0.7)
        p.save()
        p.setClipPath(block)
        p.fillRect(QRectF(x0, y0, w, 7.0), linear_brush(0, y0, 0, y0 + 7, ((0.0, OXBLOOD_LIGHT), (1.0, OXBLOOD))))
        p.restore()
        binder = rounded(x0 + 3.0, y0 - 3.0, w - 6.0, 4.0, 1.6)
        filled(p, binder, brass_brush(x0, y0 - 3, x0 + w, y0 + 1), HAIRLINE, 0.6)
        for rx in (x0 + 9.0, x0 + w - 9.0):
            filled(p, ellipse(rx, y0 + 0.5, 1.4), HAIRLINE, None)
        step = at / (len(DAYS) - 1)
        if reduced or e >= at:
            flips, k = len(DAYS) - 1, 1.0
        else:
            flips = min(len(DAYS) - 1, int(e / step + 1e-6))
            k = e / step - flips
        _day(p, x0 + w / 2, y0 + 19.5, DAYS[flips])
        if 0 < flips and k < 0.45:
            u = clamp(k / 0.45, 0.0, 1.0)
            fold = 1.0 - u * u
            p.save()
            p.translate(x0, y0 + 7.0)
            p.scale(1.0, fold)
            sheet = rounded(0.0, 0.0, w, h - 7.0, 1.5)
            filled(p, sheet, linear_brush(0, 0, 0, h - 7.0, ((0.0, PARCHMENT), (1.0, CREAM))), HAIRLINE, 0.6)
            _day(p, w / 2, 12.5, DAYS[flips - 1])
            p.restore()
            p.setPen(QPen(faded(HAIRLINE, 0.35 * (1.0 - fold)), 1.2))
            edge = y0 + 7.6 + (h - 7.0) * fold
            p.drawLine(QPointF(x0 + 1.0, edge), QPointF(x0 + w - 1.0, edge))
        elif flips < len(DAYS) - 1 and k >= 0.45:
            c = 1.5 + 3.5 * (k - 0.45) / 0.55
            fold = polygon(((x0 + w - c, y0 + h), (x0 + w, y0 + h - c), (x0 + w - c, y0 + h - c)))
            filled(p, fold, PARCHMENT_DEEP, HAIRLINE, 0.5)
        if e >= at:
            ring = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.25, 0.0, 1.0))
            p.setPen(QPen(faded(OXBLOOD, 0.95), 1.4, *ROUND))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(x0 + w / 2 - 12.5, y0 + 10.5, 25.0, 18.0), 90 * 16, int(-360 * 16 * ring))
            sparkle(p, x0 + w - 1.0, y0 + 9.0, 2.6 if reduced else 2.6 * abs(math.sin(e * 4.0)), WHITE)
