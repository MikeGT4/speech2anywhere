# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_IN_OUT, EASE_OUT, Frame, clamp, prog
from kira.ui.hud.fachgebiet import (
    FLY_ROUTES, Fachgebiet, check, fly_out, outlined, ringed, ringed_line, rounded, stroke,
)
from kira.ui.hud.saison import INK, WHITE, Pose, ellipse, faded, polygon, sparkle
from kira.texte import N_, tr

MONEY = QColor("#2E9E5B")
MONEY_DARK = QColor("#1F7A43")
MONEY_LIGHT = QColor("#BFF0C9")
GOLD = QColor("#F2B705")
GOLD_DARK = QColor("#B88600")
GOLD_LIGHT = QColor("#FFE08A")
LOSS = QColor("#E5484D")
REGISTER = QColor("#3B4651")
REGISTER_LIGHT = QColor("#5B6A78")
DISPLAY = QColor("#1E2A22")
DIGIT = QColor("#7CF0A4")
CALCULATOR = QColor("#E9ECEF")

STACK_AT = QPointF(82.0, 74.0)
COIN_CLOCK = (245.0, 14.0)
STACK_MAX = 7
DROP_S = 0.22
CHART = ((0.0, 0.18), (0.14, 0.32), (0.27, 0.24), (0.42, 0.48), (0.55, 0.42), (0.7, 0.66), (0.83, 0.6), (1.0, 0.92))


def stacked_coin(p: QPainter, x: float, y: float, rx: float, ry: float, face: bool = True) -> None:
    side = QPainterPath(QPointF(x - rx, y))
    side.lineTo(x - rx, y + 2.2)
    side.arcTo(QRectF(x - rx, y + 2.2 - ry, 2 * rx, 2 * ry), 180, 180)
    side.lineTo(x + rx, y)
    side.closeSubpath()
    outlined(p, side, GOLD_DARK, 1.1)
    outlined(p, ellipse(x, y, rx, ry), GOLD, 1.1)
    if face:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(faded(GOLD_DARK, 0.9), 0.7))
        p.drawPath(ellipse(x, y, rx * 0.7, ry * 0.7))


def face_coin(p: QPainter, x: float, y: float, r: float, squeeze: float = 1.0) -> None:
    p.save()
    p.translate(x, y)
    p.scale(max(0.14, squeeze), 1.0)
    cm._ink_shape(p, ellipse(0, 0, r), GOLD, 1.6, 1.4)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(GOLD_DARK, 0.9))
    p.drawPath(ellipse(0, 0, r - 2.0))
    if squeeze > 0.45:
        one = QPainterPath()
        one.addText(0, 0, comic.baloo(800, max(6, round(r * 1.25))), "1")
        box = one.boundingRect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(GOLD_DARK)
        p.drawPath(one.translated(-box.center().x(), -box.center().y()))
    p.restore()


def _tie(p: QPainter, angle: float, dy: float, glint: bool) -> None:
    p.save()
    p.translate(35.6, 60.5 + dy)
    for side in (-1, 1):
        ringed(p, polygon(((side * 1.6, -1.2), (side * 7.0, -1.8), (side * 4.6, 3.4))), WHITE, 1.1, 3.0)
    p.rotate(angle)
    blade = polygon(((-1.9, 3.0), (1.9, 3.0), (3.8, 9.6), (0.0, 12.4), (-3.8, 9.6)))
    ringed(p, blade, MONEY, 1.3, 3.4)
    p.save()
    p.setClipPath(blade)
    p.setPen(QPen(GOLD_LIGHT, 1.2))
    for k in range(3):
        p.drawLine(QPointF(-6.0, 3.5 + k * 3.6), QPointF(6.0, 8.0 + k * 3.6))
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.3))
    p.drawPath(blade)
    ringed(p, polygon(((-2.6, -1.0), (2.6, -1.0), (1.8, 3.2), (-1.8, 3.2))), MONEY_DARK, 1.3, 3.0)
    if glint:
        sparkle(p, 5.0, 6.0, 3.0, WHITE)
    p.restore()


def _coin_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = COIN_CLOCK
    frac = elapsed - math.floor(elapsed)
    squeeze = 1.0 if reduced else abs(math.cos(math.pi * EASE_IN_OUT(clamp(frac / 0.45, 0.0, 1.0))))
    face_coin(p, cx, cy, 8.0, squeeze)
    since = elapsed % 60
    if not reduced and elapsed >= 60 and since < 0.7:
        k = since / 0.7
        p.save()
        p.setOpacity(p.opacity() * (1.0 - prog(k, 0.7, 0.3)))
        cm._sfx(p, cx - 30, cy + 15, tr("KA-CHING!"), 7 + 2 * EASE_OUT(min(1.0, k * 3)), -8, 2.2, 1.0)
        p.restore()
    cm._clock_digits(p, cx - 11.5, cy + 0.4, elapsed)


class Wirtschaft(Fachgebiet):
    key = "wirtschaft"
    SCENES = ("kurs", "kasse", "rechner")
    CLOCKS = ("muenze",)
    WORDS = (N_("bla"), N_("Ka-ching!"), N_("bla"))
    WORD_FILLS = (QColor(comic.YELLOW_HOVER), MONEY_LIGHT, GOLD_LIGHT)
    ZACK_WORD = N_("Gebongt!")
    SILENCE = (N_("Kein Signal"), N_("Flaute im Mikrofon."))
    CAPTIONS = {
        "kurs": (N_("Kurs steigt …"), N_("Allzeithoch!"), 2.3),
        "kasse": (N_("wird gebucht …"), N_("verbucht!"), 2.4),
        "rechner": (N_("wird gerechnet …"), N_("rechnet sich!"), 2.4),
    }
    LOOKS = {
        "kurs": ((10, 4), "line", "o"),
        "kasse": ((10, 12), "line", "smile"),
        "rechner": ((10, 8), "line", "smile"),
    }

    def __init__(self) -> None:
        super().__init__()
        self._drops: list[float] = []
        self._seen = 0

    def on_press(self, t: float, f: Frame) -> None:
        super().on_press(t, f)
        self._drops = [t - 1.0]
        self._seen = 0

    def on_clear(self, f: Frame) -> None:
        super().on_clear(f)
        self._drops = []

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        super().step(t, dt, f, tap, an)
        while self._seen < self._count:
            if len(self._drops) < STACK_MAX:
                self._drops.append(t)
            self._seen += 1

    def accessory(self, p: QPainter, pose: Pose) -> None:
        angle, dy, glint = 0.0, 0.0, False
        if pose.kind == "talk":
            if not pose.reduced:
                angle = 10.0 * pose.level * math.sin(pose.t * 7.0)
        elif pose.kind == "shout":
            angle = -62.0 + (0.0 if pose.reduced else 12.0 * math.sin(pose.t * 29.0))
        elif pose.kind == "wink":
            glint = True
        elif pose.kind == "sad":
            angle, dy = 16.0, 1.0
        else:
            angle = 0.0 if pose.reduced else 3.0 * math.sin(pose.t * 1.6)
        _tie(p, angle, dy, glint)

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        shake = 0.0
        if self.mode == "rec" and an.clip and not f.reduced:
            shake = math.sin(t * 61.0) * 1.2
        drops = self._drops or [t - 1.0]
        for i, born in enumerate(drops):
            landed = 1.0 if f.reduced else EASE_OUT(clamp((t - born) / DROP_S, 0.0, 1.0))
            y = STACK_AT.y() - 4.0 - i * 3.0 - (1.0 - landed) * 18.0
            wobble = 0.0
            if i == len(drops) - 1 and self.mode == "rec" and not f.reduced:
                wobble = math.sin(t * 13.0) * 1.2 * self._lv
            p.save()
            p.setOpacity(p.opacity() * min(1.0, 0.2 + landed * 1.5))
            stacked_coin(p, STACK_AT.x() + wobble + shake * i / STACK_MAX, y, 9.0, 3.0, i == len(drops) - 1)
            p.restore()

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _coin_clock(p, elapsed, reduced)

    def scene_kurs(self, p: QPainter, e: float, reduced: bool) -> None:
        x0, y0, x1, y1 = 100.0, 12.0, 143.0, 47.0
        at = self.payoff("kurs")
        p.setPen(QPen(faded(MONEY, 0.25), 0.8))
        for k in range(1, 4):
            p.drawLine(QPointF(x0 + 2, y1 - k * 8.5), QPointF(x1, y1 - k * 8.5))
        stroke(p, x0, y0, x0, y1, INK, 1.6)
        stroke(p, x0, y1, x1 + 1.0, y1, INK, 1.6)
        drawn = 1.0 if reduced else clamp(e / (at - 0.1), 0.0, 1.0)
        span_x, span_y = x1 - x0 - 6.0, y1 - y0 - 6.0
        points = [QPointF(x0 + 3.0 + u * span_x, y1 - 3.0 - v * span_y) for u, v in CHART]
        line = QPainterPath(points[0])
        head = points[0]
        for i in range(1, len(CHART)):
            u0, u1 = CHART[i - 1][0], CHART[i][0]
            if drawn >= u1:
                line.lineTo(points[i])
                head = points[i]
                continue
            k = (drawn - u0) / (u1 - u0)
            head = QPointF(points[i - 1].x() + (points[i].x() - points[i - 1].x()) * k,
                           points[i - 1].y() + (points[i].y() - points[i - 1].y()) * k)
            line.lineTo(head)
            break
        ringed_line(p, line, MONEY, 2.0, 4.6)
        outlined(p, ellipse(head.x(), head.y(), 2.3), MONEY, 1.0)
        if e >= at:
            pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.2, 0.0, 1.0))
            p.save()
            p.translate(x1 - 2.0, y0 + 2.0)
            p.scale(pop, pop)
            cm._ink_shape(p, polygon(((0.0, -7.0), (6.0, 1.0), (2.2, 1.0), (2.2, 7.0), (-2.2, 7.0), (-2.2, 1.0),
                                      (-6.0, 1.0))), MONEY, 1.3, 1.2)
            p.restore()

    def scene_kasse(self, p: QPainter, e: float, reduced: bool) -> None:
        cx, cy = 121.0, 31.0
        at = self.payoff("kasse")
        opened = e >= at
        out = (1.0 if reduced else EASE_OUT(clamp((e - at) / 0.25, 0.0, 1.0))) if opened else 0.0
        drawer = rounded(cx - 15.0 + out * 4.0, cy + 10.0 + out * 4.0, 30.0, 7.0, 1.6)
        cm._ink_shape(p, drawer, REGISTER_LIGHT, 1.4, 1.2)
        if out > 0:
            for k in range(3):
                stacked_coin(p, cx - 7.0 + k * 7.0 + out * 4.0, cy + 11.0 + out * 4.0, 3.2, 1.1, False)
        body = polygon(((cx - 18.0, cy + 11.0), (cx + 18.0, cy + 11.0), (cx + 15.0, cy - 6.0), (cx - 15.0, cy - 6.0)))
        cm._ink_shape(p, body, REGISTER, 1.6, 1.4)
        outlined(p, rounded(cx - 4.0, cy - 18.0, 16.0, 8.0, 1.6), REGISTER, 1.2)
        outlined(p, rounded(cx - 2.6, cy - 16.6, 13.2, 5.2, 1.0), DISPLAY, 0.9)
        if opened:
            check(p, cx + 1.4, cy - 16.2, 4.6, DIGIT, 1.2)
        else:
            p.setFont(comic.baloo(800, 6))
            p.setPen(DIGIT)
            p.drawText(QPointF(cx - 1.4, cy - 12.2), str(int((e * 13) % 90) + 10))
        stroke(p, cx + 4.0, cy - 10.0, cx + 4.0, cy - 6.0, INK, 1.4)
        pressed = -1 if reduced or opened else int(e / 0.2) % 6
        for i in range(6):
            kx = cx - 11.0 + (i % 3) * 8.0
            ky = cy - 2.0 + (i // 3) * 6.0
            down = 1.0 if i == pressed else 0.0
            outlined(p, rounded(kx - 2.8, ky - 1.8 + down, 5.6, 3.6, 1.0), MONEY_LIGHT if i == pressed else WHITE, 0.9)
        if opened and not reduced and e < at + 0.8:
            k = (e - at) / 0.8
            p.save()
            p.setOpacity(p.opacity() * (1.0 - prog(k, 0.7, 0.3)))
            cm._sfx(p, cx - 8.0, cy - 22.0, tr("KA-CHING!"), 7.0 + 2.0 * EASE_OUT(min(1.0, k * 3)), -10, 1.8, 0.9)
            p.restore()

    def scene_rechner(self, p: QPainter, e: float, reduced: bool) -> None:
        cx, cy = 121.0, 36.0
        at = self.payoff("rechner")
        grow = 1.0 if reduced else clamp(e / at, 0.0, 1.0)
        tape_h = 6.0 + grow * 20.0
        outlined(p, rounded(cx - 7.0, cy - 9.0 - tape_h, 14.0, tape_h + 2.0, 0.8), WHITE, 1.1)
        for k in range(int(tape_h / 4.2)):
            y = cy - 11.0 - k * 4.2
            stroke(p, cx - 4.0, y, cx + 2.5 - (k % 3) * 1.6, y, faded(INK, 0.55), 0.9)
        if e >= at:
            y = cy - 9.0 - tape_h + 4.0
            stroke(p, cx - 4.5, y + 2.0, cx + 4.5, y + 2.0, INK, 0.8)
            stroke(p, cx - 4.5, y + 3.2, cx + 4.5, y + 3.2, INK, 0.8)
            check(p, cx - 3.0, y - 4.6, 5.6, MONEY, 1.6)
        cm._ink_shape(p, rounded(cx - 15.0, cy - 9.0, 30.0, 20.0, 3.0), CALCULATOR, 1.6, 1.4)
        pressed = -1 if reduced or e >= at else int(e / 0.18) % 8
        for i in range(8):
            kx = cx - 10.5 + (i % 4) * 7.0
            ky = cy - 4.0 + (i // 4) * 6.4
            fill = GOLD_LIGHT if i == pressed else MONEY if i == 7 else WHITE
            outlined(p, rounded(kx - 2.6, ky - 1.8 + (0.8 if i == pressed else 0.0), 5.2, 3.8, 1.0), fill, 0.9)

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        def draw(pp, x, y, size, moment, j):
            face_coin(pp, x, y, 5.0 * size, 1.0 if f.reduced else abs(math.cos(moment * 5 + j)))
        fly_out(p, t, f, k, draw, FLY_ROUTES)

    def error_decor(self, p: QPainter, left: float, top: float) -> None:
        x, y = left + 4.0, top - 2.0
        ringed(p, rounded(x, y, 15.0, 12.0, 2.4), WHITE, 1.2, 3.0)
        fall = QPainterPath(QPointF(x + 2.5, y + 3.0))
        fall.lineTo(x + 6.0, y + 6.0)
        fall.lineTo(x + 8.5, y + 4.6)
        fall.lineTo(x + 12.4, y + 9.2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(LOSS, 1.5))
        p.drawPath(fall)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(LOSS)
        p.drawPath(polygon(((x + 13.4, y + 10.4), (x + 9.8, y + 9.8), (x + 12.8, y + 6.8))))
