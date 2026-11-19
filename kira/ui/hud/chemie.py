# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from kira.ui import _comic as comic
from kira.ui.hud import comic as cm
from kira.ui.hud.base import Frame, clamp
from kira.ui.hud.fachgebiet import FLY_ROUTES, Fachgebiet, fly_out, outlined, ringed, rounded, stroke, twinkle
from kira.ui.hud.saison import INK, ROUND, STEEL, WHITE, YELLOW, Pose, ellipse, faded, polygon, sparkle
from kira.texte import N_

GLASS = QColor("#E3F4FB")
TURQUOISE = QColor("#2EC4B6")
MAGENTA = QColor("#E8457A")
MAGENTA_LIGHT = QColor("#FFB3D1")
LIME = QColor("#8BD346")
MINT = QColor("#A6F0D8")
OXYGEN = QColor("#E5484D")
STRAP = QColor("#2B2B31")
LENS = QColor("#CFF3FF")
GOGGLE_FRAME = QColor("#2EA38F")
RACK_WOOD = QColor("#B07A44")
CRYSTAL = (QColor("#E8F7FF"), QColor("#BDE7FF"), QColor("#93D3F5"), QColor("#D3F0FF"))
SOOT = QColor("#7A7A80")
SOOT_LIGHT = QColor("#9A9AA0")
CLEAR_LIQUID = (242, 250, 255)

RACK_AT = QPointF(82.0, 66.0)
ELEMENT_CLOCK = (245.0, 14.0)
GOGGLES_AT = (35.0, 17.5)
IDLE_LEVELS = (0.42, 0.34, 0.5)
STILL_LEVELS = (0.55, 0.4, 0.7)
TUBE_COLORS = (TURQUOISE, MAGENTA, LIME)
ELEMENTS = tuple(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb "
    "Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au "
    "Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts "
    "Og".split())


def element_of_second(elapsed: float) -> tuple[int, str]:
    second = int(math.floor(elapsed))
    number = 1 if second <= 0 else (second - 1) % len(ELEMENTS) + 1
    return number, ELEMENTS[number - 1]


def _goggles(p: QPainter, x: float, y: float, angle: float, glint: bool) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    strap = QPainterPath(QPointF(-19.0, 5.0))
    strap.cubicTo(QPointF(-10.0, 0.5), QPointF(10.0, 0.5), QPointF(19.0, 5.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for color, width in ((WHITE, 5.4), (INK, 3.6), (STRAP, 1.6)):
        p.setPen(QPen(color, width, *ROUND))
        p.drawPath(strap)
    for side in (-1, 1):
        lens_x = side * 7.2
        ringed(p, ellipse(lens_x, -1.0, 6.4, 5.4), GOGGLE_FRAME, 1.5, 4.0)
        outlined(p, ellipse(lens_x, -1.0, 4.6, 3.7), LENS, 1.0)
        p.setPen(QPen(WHITE, 1.2, *ROUND))
        p.drawLine(QPointF(lens_x - 2.6, -2.2), QPointF(lens_x - 0.8, -3.6))
    outlined(p, rounded(-1.6, -2.4, 3.2, 2.4, 1.0), GOGGLE_FRAME, 0.9)
    if glint:
        sparkle(p, 10.0, -7.5, 3.4, WHITE)
    p.restore()


def _tube(p: QPainter, x: float, top: float, bottom: float, level: float, color: QColor, foam: float,
          bubbles: int, moment: float) -> None:
    w = 6.4
    tube = QPainterPath(QPointF(x - w / 2, top))
    tube.lineTo(x - w / 2, bottom - w / 2)
    tube.arcTo(QRectF(x - w / 2, bottom - w, w, w), 180, 180)
    tube.lineTo(x + w / 2, top)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(faded(GLASS, 0.9))
    p.drawPath(tube)
    p.save()
    p.setClipPath(tube)
    surface = bottom - (bottom - top - 2.0) * clamp(level, 0.0, 1.0)
    p.fillRect(QRectF(x - w / 2, surface, w, bottom - surface + 1), color)
    p.fillRect(QRectF(x - w / 2, surface, w, 1.2), faded(WHITE, 0.6))
    p.setPen(QPen(faded(WHITE, 0.9), 0.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for k in range(bubbles):
        cycle = (moment * 2.2 + k / 3) % 1.0
        p.drawEllipse(QPointF(x - 1.0 + k * 1.0, bottom - 3.0 - cycle * (bottom - surface - 3.0)), 0.8, 0.8)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.3, *ROUND))
    p.drawPath(tube)
    stroke(p, x - w / 2 - 1.0, top, x + w / 2 + 1.0, top, INK, 1.4)
    if foam > 0:
        p.setPen(QPen(INK, 0.9))
        p.setBrush(color.lighter(130))
        for k in range(3):
            p.drawEllipse(QPointF(x - 2.0 + k * 2.0, top - 1.5 - foam * (1.5 + (k % 2) * 1.5)), 1.6 + foam, 1.6 + foam)


def _element_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = ELEMENT_CLOCK
    number, symbol = element_of_second(elapsed)
    frac = elapsed - math.floor(elapsed)
    d = (frac - 0.05) / 0.06
    flip = 1.0 if reduced else 1.0 - 0.7 * math.exp(-d * d)
    p.save()
    p.translate(cx, cy)
    p.scale(1.0, flip)
    tile = rounded(-8.5, -9.0, 17.0, 18.0, 2.6)
    cm._ink_shape(p, tile, WHITE, 1.5, 1.4)
    p.save()
    p.setClipPath(tile)
    p.fillRect(QRectF(-9.0, -9.5, 18.0, 4.6), TURQUOISE)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(INK, 1.5, *ROUND))
    p.drawPath(tile)
    digits = QPainterPath()
    digits.addText(0, 0, comic.baloo(800, 5), str(number))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(WHITE)
    p.drawPath(digits.translated(-6.6, -5.5))
    letters = QPainterPath()
    letters.addText(0, 0, comic.baloo(800, 10 if len(symbol) == 1 else 9), symbol)
    box = letters.boundingRect()
    p.setBrush(INK)
    p.drawPath(letters.translated(-box.center().x(), 3.2 - box.center().y()))
    p.restore()
    since = elapsed % 60
    if not reduced and elapsed >= 60 and since < 0.6:
        sparkle(p, cx + 9.0, cy - 9.0, 3.8 * math.sin(since / 0.6 * math.pi), WHITE)
    cm._clock_digits(p, cx - 11.5, cy + 0.4, elapsed)


def ball(p: QPainter, x: float, y: float, r: float, color: QColor) -> None:
    outlined(p, ellipse(x, y, r), color, 1.1)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(faded(WHITE, 0.7))
    p.drawEllipse(QPointF(x - r * 0.35, y - r * 0.35), r * 0.3, r * 0.22)


class Chemie(Fachgebiet):
    key = "chemie"
    SCENES = ("titration", "molekuel", "kristall")
    CLOCKS = ("element",)
    WORDS = (N_("bla"), N_("zisch!"), N_("bla"))
    WORD_FILLS = (QColor(comic.YELLOW_HOVER), MINT, MAGENTA_LIGHT)
    ZACK_WORD = N_("Gelöst!")
    SILENCE = (N_("Kein Signal"), N_("Keine Reaktion im Mikrofon."))
    CAPTIONS = {
        "titration": (N_("titriert …"), N_("Farbumschlag!"), 2.4),
        "molekuel": (N_("Bindung entsteht …"), N_("stabil!"), 2.3),
        "kristall": (N_("kristallisiert …"), N_("glasklar!"), 2.4),
    }
    LOOKS = {
        "titration": ((8, 6), "line", "o"),
        "molekuel": ((10, 8), "line", "smile"),
        "kristall": ((10, 8), "line", "o"),
    }

    def __init__(self) -> None:
        super().__init__()
        self._levels = list(IDLE_LEVELS)

    def on_press(self, t: float, f: Frame) -> None:
        super().on_press(t, f)
        self._levels = list(IDLE_LEVELS)

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        super().step(t, dt, f, tap, an)
        targets = list(IDLE_LEVELS)
        if self.mode == "rec":
            targets = [0.2, 0.2, 0.2]
            if not an.silent:
                bands = (an.band(150, 500), an.band(500, 1500), an.band(1500, 4000))
                targets = [clamp(0.22 + 0.78 * clamp(v * 1.5, 0.0, 1.0) * (0.45 + 0.55 * self._lv), 0.2, 1.0)
                           for v in bands]
        for i in range(3):
            tau = 0.06 if targets[i] > self._levels[i] else 0.25
            self._levels[i] += (targets[i] - self._levels[i]) * min(1.0, dt / tau)

    def accessory(self, p: QPainter, pose: Pose) -> None:
        angle, dy, glint = 0.0, 0.0, False
        if pose.kind == "talk":
            if not pose.reduced:
                angle = 2.5 * pose.level * math.sin(pose.t * 8.0)
                dy = -0.8 * pose.level * abs(math.sin(pose.t * 8.0))
        elif pose.kind == "shout":
            angle, dy = (0.0 if pose.reduced else 4.0 * math.sin(pose.t * 31.0)), 2.2
        elif pose.kind == "wink":
            glint = True
        elif pose.kind == "sad":
            angle, dy = 12.0, 1.6
        else:
            angle = 0.0 if pose.reduced else 1.5 * math.sin(pose.t * 1.6)
            if pose.kind == "look":
                angle += pose.look[0] * 0.2
        _goggles(p, GOGGLES_AT[0], GOGGLES_AT[1] + dy, angle, glint)

    def backdrop(self, p: QPainter, t: float, f: Frame, an) -> None:
        x0, y0 = RACK_AT.x(), RACK_AT.y()
        foam = 1.0 if self.mode == "rec" and an.clip else 0.0
        levels = STILL_LEVELS if f.reduced else self._levels
        for i, color in enumerate(TUBE_COLORS):
            bubbles = 0 if f.reduced else int(clamp(levels[i] - 0.45, 0.0, 1.0) * 6.0)
            _tube(p, x0 - 8.0 + i * 8.0, y0 - 18.0, y0 + 6.0, levels[i], color, foam, bubbles, t + i * 0.3)
        cm._ink_shape(p, rounded(x0 - 14.0, y0 - 1.0, 28.0, 4.0, 1.4), RACK_WOOD, 1.3, 1.1)
        stroke(p, x0 - 12.0, y0 + 3.0, x0 - 12.0, y0 + 9.0, INK, 1.6)
        stroke(p, x0 + 12.0, y0 + 3.0, x0 + 12.0, y0 + 9.0, INK, 1.6)

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _element_clock(p, elapsed, reduced)

    def scene_titration(self, p: QPainter, e: float, reduced: bool) -> None:
        cx = 121.0
        at = self.payoff("titration")
        outlined(p, rounded(cx - 2.2, 4.0, 4.4, 17.0, 1.2), faded(GLASS, 0.95), 1.2)
        p.fillRect(QRectF(cx - 1.2, 8.0, 2.4, 12.0), faded(MAGENTA_LIGHT, 0.9))
        outlined(p, rounded(cx - 4.5, 15.0, 9.0, 2.4, 1.0), STEEL, 1.0)
        stroke(p, cx, 21.0, cx, 24.5, INK, 1.4)
        flask = QPainterPath(QPointF(cx - 3.2, 27.0))
        flask.lineTo(cx - 3.2, 32.0)
        flask.lineTo(cx - 13.5, 47.0)
        flask.quadTo(QPointF(cx - 14.5, 50.0), QPointF(cx - 11.0, 50.0))
        flask.lineTo(cx + 11.0, 50.0)
        flask.quadTo(QPointF(cx + 14.5, 50.0), QPointF(cx + 13.5, 47.0))
        flask.lineTo(cx + 3.2, 32.0)
        flask.lineTo(cx + 3.2, 27.0)
        flask.closeSubpath()
        cm._ink_shape(p, flask, faded(GLASS, 0.95), 1.6, 1.4)
        turned = 1.0 if reduced else clamp((e - (at - 0.25)) / 0.35, 0.0, 1.0)
        r0, g0, b0 = CLEAR_LIQUID
        liquid = QColor(int(r0 + (MAGENTA.red() - r0) * turned), int(g0 + (MAGENTA.green() - g0) * turned),
                        int(b0 + (MAGENTA.blue() - b0) * turned))
        p.save()
        p.setClipPath(flask)
        p.fillRect(QRectF(cx - 15.0, 40.0, 30.0, 11.0), liquid)
        p.fillRect(QRectF(cx - 15.0, 40.0, 30.0, 1.2), faded(WHITE, 0.7))
        if not reduced and turned < 1.0:
            for j in range(2):
                age = (e / 0.32 + j * 0.5) % 1.0
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(faded(MAGENTA, 0.6 * (1.0 - age)))
                swirl = QPointF(cx + math.sin(age * 6 + j) * 4.0, 43.0 + age * 3.0)
                p.drawEllipse(swirl, 1.5 + age * 5.0, 1.0 + age * 2.0)
        p.restore()
        if not reduced and turned < 1.0:
            fall = (e % 0.32) / 0.32
            outlined(p, ellipse(cx, 25.5 + fall * 14.0, 1.1, 1.5), MAGENTA_LIGHT, 0.7)
        if turned >= 1.0:
            sparkle(p, cx + 12.0, 34.0, 3.4 * twinkle(e, reduced), WHITE)

    def scene_molekuel(self, p: QPainter, e: float, reduced: bool) -> None:
        cx, cy = 121.0, 31.0
        at = self.payoff("molekuel")
        docked = (1.0, 1.0) if reduced else (clamp((e - 0.4) / 0.6, 0.0, 1.0), clamp((e - 1.3) / 0.6, 0.0, 1.0))
        turn = 0.0 if reduced or e < at else (e - at) * 40.0
        atoms = []
        for i, (angle, k) in enumerate(((150.0, docked[0]), (30.0, docked[1]))):
            a = math.radians(angle + turn)
            ease = 1.0 - (1.0 - k) * (1.0 - k) * (1.0 - k)
            distance = 12.0 + (1.0 - ease) * 10.0
            drift = 0.0 if reduced else (1.0 - k) * math.sin(e * 9 + i * 2) * 2.0
            atoms.append((cx + math.cos(a) * distance + drift, cy + math.sin(a) * distance + 6.0 * (1.0 - k), k))
        for x, y, k in atoms:
            if k >= 1.0:
                p.setPen(QPen(INK, 3.4, *ROUND))
                p.drawLine(QPointF(cx, cy), QPointF(x, y))
                p.setPen(QPen(QColor("#F2F2F2"), 1.6, *ROUND))
                p.drawLine(QPointF(cx, cy), QPointF(x, y))
        ball(p, cx, cy, 6.6, OXYGEN)
        for x, y, k in atoms:
            ball(p, x, y, 4.4, WHITE)
            if not reduced and 0.95 < k < 1.0:
                sparkle(p, (x + cx) / 2, (y + cy) / 2, 3.0, YELLOW)
        if e >= at:
            sparkle(p, cx + 13.0, cy - 12.0, 3.2 * twinkle(e, reduced), WHITE)

    def scene_kristall(self, p: QPainter, e: float, reduced: bool) -> None:
        cx, cy = 121.0, 31.0
        at = self.payoff("kristall")
        k = clamp(e / (at - 0.2), 0.0, 1.0)
        grown = 1.0 if reduced else 1.0 - (1.0 - k) * (1.0 - k) * (1.0 - k)
        s = 0.35 + 0.65 * grown
        top = (cx, cy - 18.0 * s)
        bottom = (cx, cy + 18.0 * s)
        ring = [(cx + math.cos(math.radians(a)) * 12.0 * s, cy - 4.0 * s + math.sin(math.radians(a)) * 3.6 * s)
                for a in (180, 120, 60, 0)]
        faces = ((top, ring[0], ring[1], CRYSTAL[1]), (top, ring[1], ring[2], CRYSTAL[0]),
                 (top, ring[2], ring[3], CRYSTAL[3]), (bottom, ring[0], ring[1], CRYSTAL[2]),
                 (bottom, ring[1], ring[2], CRYSTAL[1]), (bottom, ring[2], ring[3], CRYSTAL[2]))
        shown = 6 if reduced else int(clamp(e / (at / 6.0), 1.0, 6.0))
        outline = polygon((top, ring[0], bottom, ring[3]))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK)
        p.drawPath(outline.translated(1.6, 1.6))
        for i, (a, b, c, color) in enumerate(faces):
            outlined(p, polygon((a, b, c)), color if i < shown else faded(GLASS, 0.6), 1.1)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(INK, 1.6, *ROUND))
        p.drawPath(outline)
        if e >= at:
            sweep = 1.0 if reduced else ((e - at) / 0.9) % 1.0
            p.save()
            p.setClipPath(outline)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(faded(WHITE, 0.75))
            x = cx - 14.0 + sweep * 28.0
            p.drawPath(polygon(((x - 2.0, cy - 20.0), (x + 2.0, cy - 20.0), (x - 4.0, cy + 20.0),
                                (x - 8.0, cy + 20.0))))
            p.restore()
            sparkle(p, cx + 10.0, cy - 14.0, 3.6 * twinkle(e, reduced), WHITE)
            sparkle(p, cx - 12.0, cy + 9.0, 2.4 * (1.0 if reduced else abs(math.cos(e * 4))), WHITE)

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        def draw(pp, x, y, size, moment, j):
            if j % 2 == 0:
                outlined(pp, ellipse(x, y, 4.0 * size), faded(WHITE, 0.95), 1.2)
            else:
                a = moment * 3 + j
                dx, dy = math.cos(a) * 3.6 * size, math.sin(a) * 3.6 * size
                stroke(pp, x - dx, y - dy, x + dx, y + dy, INK, 2.2)
                ball(pp, x - dx, y - dy, 2.6 * size, OXYGEN)
                ball(pp, x + dx, y + dy, 2.0 * size, WHITE)
        fly_out(p, t, f, k, draw, FLY_ROUTES)

    def error_decor(self, p: QPainter, left: float, top: float) -> None:
        x, y = left + 6.0, top + 2.0
        for k, (dx, dy, r) in enumerate(((0.0, 0.0, 5.0), (5.5, -2.0, 4.0), (-4.0, -2.5, 3.4), (2.0, -4.6, 3.0))):
            cm._puff(p, x + dx, y + dy, r, 1.0, SOOT if k % 2 == 0 else SOOT_LIGHT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK)
        for dx, dy in ((9.0, 2.0), (11.0, -1.0), (-6.0, 3.0)):
            p.drawEllipse(QPointF(x + dx, y + dy), 0.7, 0.7)
