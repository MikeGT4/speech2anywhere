# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import functools
import math
from collections import OrderedDict
from dataclasses import dataclass, replace

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtSvg import QSvgRenderer

from kira.ui.hud import comic as cm
from kira.ui.hud.base import EASE_OUT, Frame, clamp, prog
from kira.ui.hud.fachgebiet import Fachgebiet, fly_out, heart, lettering, outlined
from kira.ui.hud.saison import LABEL, TILE, WHITE, YELLOW, Pose, ellipse, faded, polygon, sparkle, text
from kira.texte import N_, tr

LINE = "#111111"
FUR = "#F3E6D0"
MASK = "#5A3E2B"
MASK_LIGHT = "#7A5A42"
IRIS = "#3F86D8"
COLLAR = "#2F5FB3"
GOLD = "#F2C230"
NOSE = "#3A2A20"
TONGUE = "#E5484D"
YARN = "#E5484D"
YARN_DARK = "#9E2A2F"
BELL_SHINE = "#FFF2B0"

INK = QColor(LINE)
FUR_COLOR = QColor(FUR)
MASK_COLOR = QColor(MASK)
MASK_LIGHT_COLOR = QColor(MASK_LIGHT)
IRIS_COLOR = QColor(IRIS)
GOLD_COLOR = QColor(GOLD)
YARN_COLOR = QColor(YARN)
YARN_DARK_COLOR = QColor(YARN_DARK)
HEART_COLOR = QColor("#E5484D")
SKY_COLOR = QColor("#9CC8F2")

VIEW = QRectF(0.0, 0.0, 512.0, 512.0)
HEAD_PIVOT = (256.0, 300.0)
EAR_PIVOTS = ((160.0, 130.0), (352.0, 130.0))
TAIL_PIVOT = (452.0, 470.0)
BELL_PIVOT = (256.0, 418.0)
PART_CENTER = 256.0
FACE_CACHE = 192
OPEN_STEPS = 5
LEVEL_STEPS = 8
TWITCH_STEPS = 4
LEVELED_MOUTHS = ("talk", "yawn", "lick")
FIRST_MOTION_S = (0.8, 1.6)
MOTION_GAP_S = (1.0, 2.6)
SWIPE_WAIT_S = 1.2
SWIPE_S = 1.0
MEOW_S = 0.8
CLOCK_AT = (241.0, 14.0)
CLOCK_R = 8.5
PROP_X, PROP_Y = 121.0, 31.0

_FACES: OrderedDict[tuple, QSvgRenderer] = OrderedDict()


def _ear(x0: int, x1: int, tip: int) -> str:
    inner = tip + 10 if tip < 256 else tip - 10
    return (f'<path d="M {x0} 150 L {tip} 16 L {x1} 96 Z" fill="{MASK}" stroke="{LINE}" stroke-width="18" '
            'stroke-linejoin="round"/>'
            f'<path d="M {x0 + 28} 134 L {inner} 54 L {x1 - 30} 104 Z" fill="{MASK_LIGHT}"/>')


TAIL_PATH = "M 452 470 C 520 430 500 330 452 300"
PARTS = {
    "tile": '<rect x="0" y="0" width="512" height="512" rx="102" ry="102" fill="#FFC400"/>',
    "tail": (f'<path d="{TAIL_PATH}" fill="none" stroke="{LINE}" stroke-width="44" stroke-linecap="round"/>'
             f'<path d="{TAIL_PATH}" fill="none" stroke="{MASK}" stroke-width="26" stroke-linecap="round"/>'),
    "ear_l": _ear(96, 214, 120),
    "ear_r": _ear(298, 416, 392),
    "bell": ('<path d="M 230 428 Q 230 400 256 400 Q 282 400 282 428 L 288 446 L 224 446 Z" '
             f'fill="{GOLD}" stroke="{LINE}" stroke-width="9" stroke-linejoin="round"/>'
             f'<circle cx="256" cy="450" r="7" fill="{LINE}"/>'
             f'<path d="M 238 426 Q 256 418 274 426" fill="none" stroke="{BELL_SHINE}" stroke-width="5" '
             'stroke-linecap="round"/>'),
    "paw": (f'<g transform="translate(256 256)"><ellipse cx="0" cy="0" rx="44" ry="36" fill="{MASK}" '
            f'stroke="{LINE}" stroke-width="14"/><path d="M -18 -30 L -18 -14 M 0 -34 L 0 -16 M 18 -30 L 18 -14" '
            f'stroke="{LINE}" stroke-width="7" stroke-linecap="round"/></g>'),
    "yarn": (f'<g transform="translate(256 256)"><circle cx="0" cy="0" r="40" fill="{YARN}" stroke="{LINE}" '
             'stroke-width="10"/><path d="M -30 -10 Q 0 -40 30 -10 M -34 10 Q 0 -20 34 10 M -20 28 Q 0 0 20 28" '
             f'fill="none" stroke="{YARN_DARK}" stroke-width="6"/></g>'),
}
HEAD = f'<path d="{cm._BUBBLE}" fill="{FUR}"/>'
HEAD_LINE = f'<path d="{cm._BUBBLE}" fill="none" stroke="{LINE}" stroke-width="18" stroke-linejoin="round"/>'
NOSE_SVG = (f'<path d="M 240 232 L 276 232 L 258 254 Z" fill="{NOSE}" stroke="{LINE}" stroke-width="6" '
            'stroke-linejoin="round"/>')
CAT_MOUTH = (f'<path d="M 222 286 Q 240 306 258 286 Q 276 306 294 286" fill="none" stroke="{LINE}" '
             'stroke-width="12" stroke-linecap="round"/>')
COLLAR_SVG = (f'<path d="M 150 404 Q 256 446 362 404" stroke="{COLLAR}" stroke-width="26" fill="none" '
              'stroke-linecap="round"/>')


def _svg(body: str) -> QSvgRenderer:
    return QSvgRenderer(('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">' + body + '</svg>')
                        .encode("utf-8"))


@functools.lru_cache(maxsize=None)
def _part(name: str) -> QSvgRenderer:
    return _svg(PARTS[name])


@functools.lru_cache(maxsize=1)
def _bubble() -> QPainterPath:
    path = QPainterPath()
    werte = cm._BUBBLE.split()
    i = 0
    while i < len(werte):
        befehl = werte[i]
        if befehl == "M":
            path.moveTo(float(werte[i + 1]), float(werte[i + 2]))
            i += 3
        elif befehl == "C":
            z = [float(w) for w in werte[i + 1:i + 7]]
            path.cubicTo(z[0], z[1], z[2], z[3], z[4], z[5])
            i += 7
        elif befehl == "Z":
            path.closeSubpath()
            i += 1
        else:
            raise ValueError(befehl)
    return path


def _head(p: QPainter) -> None:
    _svg_head().render(p, VIEW)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setClipPath(_bubble(), Qt.ClipOperation.IntersectClip)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(faded(MASK_COLOR, 0.9))
    p.drawEllipse(QPointF(258, 292), 122, 96)
    p.setBrush(faded(MASK_LIGHT_COLOR, 0.5))
    p.drawEllipse(QPointF(258, 96), 70, 40)
    p.restore()
    _svg_head_line().render(p, VIEW)


@functools.lru_cache(maxsize=1)
def _svg_head() -> QSvgRenderer:
    return _svg(HEAD)


@functools.lru_cache(maxsize=1)
def _svg_head_line() -> QSvgRenderer:
    return _svg(HEAD_LINE)


def _eye(cx: int, state: str, look: tuple[int, int], opening: float) -> str:
    if state == "shut":
        return (f'<path d="M {cx - 34} 178 Q {cx} 204 {cx + 34} 178" fill="none" stroke="{LINE}" '
                'stroke-width="16" stroke-linecap="round"/>')
    if state == "squint":
        s = 1 if cx < 256 else -1
        return (f'<path d="M {cx - 30 * s} 150 L {cx + 26 * s} 176 L {cx - 30 * s} 202" fill="none" '
                f'stroke="{LINE}" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>')
    if opening < 0.18:
        return f'<path d="M {cx - 36} 176 L {cx + 36} 176" stroke="{LINE}" stroke-width="16" stroke-linecap="round"/>'
    ry = 46 * opening
    lx, ly = look
    y = 176 + ly * opening
    out = (f'<ellipse cx="{cx}" cy="176" rx="38" ry="{ry:.1f}" fill="#FFFFFF" stroke="{LINE}" stroke-width="14"/>'
           f'<ellipse cx="{cx + lx}" cy="{y:.1f}" rx="26" ry="{max(2.0, min(30.0, ry - 8)):.1f}" fill="{IRIS}"/>')
    pupil = min(22.0, ry - 14)
    if pupil > 2.0:
        out += (f'<ellipse cx="{cx + lx}" cy="{y:.1f}" rx="9" ry="{pupil:.1f}" fill="{LINE}"/>'
                f'<circle cx="{cx + lx - 9}" cy="{y - 12 * opening:.1f}" r="6" fill="#FFFFFF"/>')
    return out


def _mouth(kind: str, level: float) -> str:
    if kind == "talk":
        ry = 24 + 58 * level
        return (f'<ellipse cx="258" cy="{300 + ry * 0.25:.1f}" rx="{50 + 14 * level:.1f}" ry="{ry:.1f}" '
                f'fill="{LINE}"/><ellipse cx="258" cy="{300 + ry * 0.8:.1f}" rx="{28 + 6 * level:.1f}" '
                f'ry="{max(4.0, ry * 0.3):.1f}" fill="{TONGUE}"/>')
    if kind == "yawn":
        lift = 40 * level
        return (f'<ellipse cx="258" cy="320" rx="70" ry="{40 + 60 * level:.1f}" fill="{LINE}"/>'
                f'<path d="M 214 {300 + lift:.1f} L 226 {280 + lift:.1f} L 236 {300 + lift:.1f} Z '
                f'M 280 {300 + lift:.1f} L 290 {280 + lift:.1f} L 302 {300 + lift:.1f} Z" fill="#FFFFFF"/>'
                f'<ellipse cx="258" cy="{330 + 50 * level:.1f}" rx="38" ry="{14 + 18 * level:.1f}" fill="{TONGUE}"/>')
    if kind == "lick":
        return (CAT_MOUTH + f'<path d="M 244 296 Q 258 {330 + 14 * level:.1f} 272 296 Z" fill="{TONGUE}" '
                f'stroke="{LINE}" stroke-width="6"/>')
    if kind == "sad":
        return (f'<path d="M 206 334 C 230 300 286 300 310 334" fill="none" stroke="{LINE}" stroke-width="16" '
                'stroke-linecap="round"/>')
    if kind == "hiss":
        return (f'<ellipse cx="258" cy="316" rx="80" ry="88" fill="{LINE}"/>'
                f'<ellipse cx="258" cy="372" rx="42" ry="26" fill="{TONGUE}"/>')
    if kind == "laugh":
        return ('<path d="M 186 270 C 186 330 222 360 258 360 C 296 360 330 330 330 270 C 288 290 228 290 186 270 Z" '
                f'fill="{LINE}"/><path d="M 220 334 C 236 318 280 318 296 334 C 278 350 236 350 220 334 Z" '
                f'fill="{TONGUE}"/>')
    return CAT_MOUTH


def _whiskers(twitch: float) -> str:
    out = []
    for side in (-1, 1):
        cx = 256 + side * 86
        for dy, slant in ((0, -12), (22, 0), (44, 12)):
            end_y = 258 + dy + slant + twitch * (dy - 22) * 0.6
            d = f"M {cx} {258 + dy} L {cx + side * 124} {end_y:.1f}"
            out.append(f'<path d="{d}" stroke="{LINE}" stroke-width="12" stroke-linecap="round"/>'
                       f'<path d="{d}" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>')
    return "".join(out)


def _face_svg(key: tuple) -> str:
    eye_l, eye_r, opening, look, mouth, level, twitch = key
    k = opening / OPEN_STEPS
    return (_eye(200, eye_l, look, k) + _eye(312, eye_r, look, k) + NOSE_SVG
            + _mouth(mouth, level / LEVEL_STEPS) + _whiskers(twitch / TWITCH_STEPS) + COLLAR_SVG)


def _face(key: tuple) -> QSvgRenderer:
    renderer = _FACES.get(key)
    if renderer is None:
        renderer = _svg(_face_svg(key))
        _FACES[key] = renderer
        if len(_FACES) > FACE_CACHE:
            _FACES.popitem(last=False)
    else:
        _FACES.move_to_end(key)
    return renderer


@dataclass(frozen=True)
class Cat:
    ear_l: float = 0.0
    ear_r: float = 0.0
    tilt: float = 0.0
    lift: float = 0.0
    tail: float = 0.0
    eye_l: str = "open"
    eye_r: str = "open"
    opening: float = 1.0
    look: tuple[float, float] = (0.0, 6.0)
    mouth: str = "cat"
    level: float = 0.5
    twitch: float = 0.0
    bell: float = 0.0
    shine: bool = False
    paw: tuple[float, float, float, float] | None = None
    yarn: tuple[float, float, float] | None = None
    question: bool = False
    purr: float = -1.0


def face_key(cat: Cat) -> tuple:
    open_eyes = "open" in (cat.eye_l, cat.eye_r)
    opening = round(clamp(cat.opening, 0.0, 1.0) * OPEN_STEPS) if open_eyes else 0
    look = (2 * round(cat.look[0] / 2), 2 * round(cat.look[1] / 2)) if open_eyes else (0, 0)
    level = round(clamp(cat.level, 0.0, 1.0) * LEVEL_STEPS) if cat.mouth in LEVELED_MOUTHS else 0
    twitch = round(clamp(cat.twitch, -0.5, 0.5) * TWITCH_STEPS)
    return (cat.eye_l, cat.eye_r, opening, look, cat.mouth, level, twitch)


def bump(t: float, a: float, b: float) -> float:
    if t < a or t > b:
        return 0.0
    return math.sin(math.pi * (t - a) / (b - a))


def smooth(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def shut(cat: Cat) -> Cat:
    return replace(cat, eye_l="shut", eye_r="shut")


def ear_flick(cat: Cat, m: float) -> Cat:
    return replace(cat, ear_r=cat.ear_r + 18 * (bump(m, 0.2, 0.42) + bump(m, 0.62, 0.84)), look=(10, 4))


def blink(cat: Cat, m: float) -> Cat:
    return replace(cat, opening=1 - 0.95 * min(1.0, bump(m, 0.5, 1.7) * 1.4))


def tail_swing(cat: Cat, m: float) -> Cat:
    return replace(cat, tail=26 * math.sin(m * math.pi * 2), look=(8 * math.sin(m * 3), 6))


def bell_shake(cat: Cat, m: float) -> Cat:
    s = math.sin(m * 22) * bump(m, 0.1, 1.3)
    return replace(cat, tilt=cat.tilt + 6 * s, bell=28 * s, shine=abs(s) > 0.5)


def paw_swipe(cat: Cat, m: float) -> Cat:
    hit = bump(m, 0.25, 0.65)
    alpha = prog(m, 0.0, 0.12) * (1.0 - prog(m, SWIPE_S - 0.15, 0.15))
    return replace(cat, look=(14, -10), paw=(380 - 60 * hit, 400 - 230 * hit, -40 * hit, alpha))


def yarn_play(cat: Cat, e: float) -> Cat:
    x = 96 + 60 * math.sin(e * 2.6)
    poke = bump(e % 1.2, 0.5, 0.8)
    return replace(cat, look=((x - 256) / 12, 14), yarn=(x, 440.0, e * 240),
                   paw=(x + 70, 470 - 60 * poke, -10.0, 1.0))


def wash(cat: Cat, e: float) -> Cat:
    m = e % 2.8
    up = smooth(m / 0.4) - smooth((m - 2.0) / 0.3)
    cat = replace(cat, paw=(330 - 30 * up, 470 - 150 * up, -20 * up, 1.0))
    if 0.4 < m < 2.0:
        cat = shut(replace(cat, mouth="lick", level=0.5 + 0.5 * math.sin(m * 18)))
    return cat


def yawn(cat: Cat, e: float) -> Cat:
    s = bump(e % 3.0, 0.3, 2.1)
    if s > 0.05:
        cat = replace(cat, mouth="yawn", level=s)
    if s > 0.2:
        cat = shut(cat)
    return replace(cat, lift=-8 * s, ear_l=-10 * s, ear_r=10 * s)


def purr(cat: Cat, e: float) -> Cat:
    return shut(replace(cat, mouth="cat", lift=math.sin(e * 70) * 1.5, twitch=math.sin(e * 40) * 0.5, purr=e))


def head_tilt(cat: Cat, e: float) -> Cat:
    m = e % 2.5
    k = smooth(m / 0.5) - smooth((m - 1.5) / 0.4)
    return replace(cat, tilt=-14 * k, ear_l=-8 * k, look=(-8, -6), question=0.5 < m < 1.6)


REC_MOTIONS = {
    "ohrzucken": (1.6, ear_flick),
    "blinzeln": (2.2, blink),
    "schwanz": (2.0, tail_swing),
    "gloeckchen": (1.6, bell_shake),
    "pfotenhieb": (SWIPE_S, paw_swipe),
}
REC_ORDER = tuple(REC_MOTIONS)
SCENE_MOTIONS = {"wolle": yarn_play, "putzen": wash, "gaehnen": yawn, "schnurren": purr, "kopf_schief": head_tilt}
STILL_AT = {"wolle": 1.0, "putzen": 1.1, "gaehnen": 1.2, "schnurren": 1.0, "kopf_schief": 1.0}
THINKING = Cat(look=(-6, -16))
WINK = Cat(eye_r="shut", mouth="laugh")
SAD = Cat(mouth="sad", look=(0, 14), ear_l=-22, ear_r=22)
HISS = Cat(eye_l="squint", eye_r="squint", mouth="hiss", ear_l=-28, ear_r=28)
PUZZLED = Cat(tilt=-14, ear_l=-8, look=(-8, -6), question=True)


def _turn(p: QPainter, angle: float, pivot: tuple[float, float]) -> None:
    if angle:
        p.translate(pivot[0], pivot[1])
        p.rotate(angle)
        p.translate(-pivot[0], -pivot[1])


def _place(p: QPainter, renderer: QSvgRenderer, angle: float, pivot: tuple[float, float]) -> None:
    p.save()
    _turn(p, angle, pivot)
    renderer.render(p, VIEW)
    p.restore()


def _prop(p: QPainter, name: str, x: float, y: float, angle: float, alpha: float = 1.0) -> None:
    if alpha <= 0:
        return
    p.save()
    p.setOpacity(p.opacity() * alpha)
    p.translate(x, y)
    p.rotate(angle)
    p.translate(-PART_CENTER, -PART_CENTER)
    _part(name).render(p, VIEW)
    p.restore()


def _tile_space(p: QPainter) -> None:
    p.translate(TILE.x(), TILE.y())
    p.scale(TILE.width() / 512.0, TILE.height() / 512.0)


def draw_tile(p: QPainter) -> None:
    p.save()
    _tile_space(p)
    _part("tile").render(p, VIEW)
    p.restore()


def draw_cat(p: QPainter, cat: Cat) -> None:
    p.save()
    _tile_space(p)
    _place(p, _part("tail"), cat.tail, TAIL_PIVOT)
    p.save()
    p.translate(0.0, cat.lift)
    _turn(p, cat.tilt, HEAD_PIVOT)
    _place(p, _part("ear_l"), cat.ear_l, EAR_PIVOTS[0])
    _place(p, _part("ear_r"), cat.ear_r, EAR_PIVOTS[1])
    _head(p)
    _face(face_key(cat)).render(p, VIEW)
    _place(p, _part("bell"), cat.bell, BELL_PIVOT)
    p.restore()
    if cat.shine:
        p.setPen(QPen(INK, 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for x0, y0, x1, y1 in ((300, 470, 330, 490), (212, 470, 182, 490), (256, 488, 256, 508)):
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    if cat.yarn is not None:
        _prop(p, "yarn", *cat.yarn)
    if cat.paw is not None:
        _prop(p, "paw", *cat.paw)
    if cat.question:
        cm._sfx(p, 426.0, 100.0, "?", 64.0, 12.0, 12.0, 0.0, YELLOW)
    if cat.purr >= 0.3:
        for i in range(3):
            cm._sfx(p, 370.0 + i * 34, 106.0 - (cat.purr * 60 + i * 20) % 60, "r", 44.0, 0.0, 12.0, 0.0, YELLOW)
    p.restore()


def paw_print(p: QPainter, x: float, y: float, s: float, angle: float, fill: QColor = MASK_COLOR) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.scale(s, s)
    outlined(p, ellipse(0.0, 1.0, 2.4, 2.0), fill, 0.8)
    for tx, ty in ((-2.4, -1.6), (-0.85, -3.1), (0.85, -3.1), (2.4, -1.6)):
        outlined(p, ellipse(tx, ty, 0.95), fill, 0.7)
    p.restore()


def _cat_clock(p: QPainter, elapsed: float, reduced: bool) -> None:
    cx, cy = CLOCK_AT
    r = CLOCK_R
    for side in (-1, 1):
        ear = polygon(((cx + side * 8.2, cy - 2.6), (cx + side * 6.6, cy - 11.4), (cx + side * 1.6, cy - 7.6)))
        cm._ink_shape(p, ear, MASK_COLOR, 1.4, 1.2)
    cm._ink_shape(p, ellipse(cx, cy, r), FUR_COLOR, 1.6, 1.4)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(faded(MASK_COLOR, 0.85))
    p.drawEllipse(QPointF(cx, cy + 4.0), 4.8, 3.6)
    sway = 0.0 if reduced else math.sin(elapsed * math.pi)
    for side in (-1, 1):
        p.setPen(QPen(INK, 0.6))
        p.setBrush(WHITE)
        p.drawEllipse(QPointF(cx + side * 3.3, cy - 1.4), 2.4, 2.6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(IRIS_COLOR)
        p.drawEllipse(QPointF(cx + side * 3.3 + sway, cy - 1.2), 1.4, 1.8)
    p.setBrush(INK)
    p.drawPath(polygon(((cx - 1.3, cy + 2.2), (cx + 1.3, cy + 2.2), (cx, cy + 3.5))))
    since = elapsed % 60
    if not reduced and elapsed >= 60 and since < MEOW_S:
        k = since / MEOW_S
        p.save()
        p.setOpacity(p.opacity() * (1.0 - prog(k, 0.6, 0.4)))
        cm._sfx(p, cx - 28.0, cy + 13.0, tr("miau!"), 8 + 2 * EASE_OUT(min(1.0, k * 3)), -8, 2.2, 1.0)
        p.restore()
    cm._clock_digits(p, cx - r - 4.5, cy + 0.4, elapsed)


def _payoff_heart(p: QPainter, x: float, y: float, e: float, at: float, reduced: bool) -> None:
    if e < at:
        return
    pop = 1.0 if reduced else EASE_OUT(clamp((e - at) / 0.2, 0.0, 1.0))
    p.save()
    p.translate(x, y)
    p.scale(pop, pop)
    outlined(p, heart(0.0, 0.0, 4.4), HEART_COLOR, 1.2)
    p.restore()


class Katze(Fachgebiet):
    key = "katze"
    SCENES = ("wolle", "putzen", "gaehnen", "schnurren", "kopf_schief")
    CLOCKS = ("katzenuhr",)
    WORDS = (N_("bla"), N_("miau!"), N_("bla"))
    WORD_FILLS = (FUR_COLOR, SKY_COLOR, GOLD_COLOR)
    ZACK_WORD = N_("Miau!")
    SILENCE = (N_("Kein Signal"), N_("Mucksmäuschenstill im Mikrofon."))
    FIGURE_SCALE = 0.73
    FIGURE_SHIFT = (-1.871, 0.867)
    CAPTIONS = {
        "wolle": (N_("rollt Wolle …"), N_("Faden gefunden!"), 2.4),
        "putzen": (N_("Katzenwäsche …"), N_("blitzblank!"), 2.4),
        "gaehnen": (N_("gähnt …"), N_("hellwach!"), 2.4),
        "schnurren": (N_("schnurrt …"), N_("wie geschnurrt!"), 2.4),
        "kopf_schief": (N_("grübelt …"), N_("kapiert!"), 2.4),
    }

    def __init__(self) -> None:
        super().__init__()
        self._motion: tuple[str, float] | None = None
        self._pending: str | None = None
        self._next_motion = 0.0

    def on_press(self, t: float, f: Frame) -> None:
        super().on_press(t, f)
        self._motion = None
        self._pending = None
        self._next_motion = t + self._rng.uniform(*FIRST_MOTION_S)

    def step(self, t: float, dt: float, f: Frame, tap, an) -> None:
        spawned = self._count
        super().step(t, dt, f, tap, an)
        if self.mode != "rec" or f.reduced:
            return
        if self._motion is not None and t - self._motion[1] >= REC_MOTIONS[self._motion[0]][0]:
            self._motion = None
            self._next_motion = t + self._rng.uniform(*MOTION_GAP_S)
        if self._motion is not None or t < self._next_motion:
            return
        if self._pending is None:
            self._pending = self._rng.choice(REC_ORDER)
        if self._pending == "pfotenhieb" and self._count == spawned:
            if t - self._next_motion <= SWIPE_WAIT_S:
                return
            self._pending = self._rng.choice(REC_ORDER[:-1])
        self._motion = (self._pending, t)
        self._pending = None

    def cat(self, pose: Pose) -> Cat:
        if pose.kind == "talk":
            level = clamp(pose.level, 0.0, 1.0)
            cat = Cat(mouth="talk", level=level)
            if pose.reduced:
                return cat
            cat = replace(cat, twitch=level - 0.5, ear_l=-4 * level)
            if self._motion is not None:
                name, t0 = self._motion
                duration, move = REC_MOTIONS[name]
                if 0.0 <= pose.t - t0 < duration:
                    cat = move(cat, pose.t - t0)
            return cat
        if pose.kind == "wink":
            return WINK if pose.reduced else bell_shake(WINK, pose.t - self.end_t)
        if pose.kind == "sad":
            return SAD
        if pose.kind == "shout":
            return HISS
        if pose.kind == "think":
            return PUZZLED if pose.reduced else replace(PUZZLED, tilt=-14 + 3 * math.sin(pose.t * 1.8))
        if pose.kind == "look":
            return replace(THINKING, look=pose.look)
        return Cat()

    def paint_tile(self, p: QPainter, pose: Pose) -> None:
        draw_tile(p)

    def figure(self, p: QPainter, pose: Pose, cat: Cat | None = None) -> None:
        self.paint_tile(p, pose)
        p.save()
        cm.fit_figure(p, self.FIGURE_SCALE, self.FIGURE_SHIFT)
        draw_cat(p, self.cat(pose) if cat is None else cat)
        self.accessory(p, pose)
        p.restore()

    def paint_clock(self, p: QPainter, elapsed: float, reduced: bool) -> None:
        _cat_clock(p, elapsed, reduced)

    def paint_scene(self, p: QPainter, key: str, t: float, f: Frame, elapsed: float, title: str) -> None:
        at = self.payoff(key)
        e = at + 0.6 if f.reduced else elapsed
        self.figure(p, self.pose("look", t, f, look=THINKING.look),
                    SCENE_MOTIONS[key](THINKING, STILL_AT[key] if f.reduced else elapsed))
        self.cloud(p)
        p.save()
        getattr(self, "scene_" + key)(p, e, f.reduced)
        p.restore()
        text(p, self.TITLE_X, 31, title, 15)
        text(p, self.TITLE_X, 47, self.caption(key, e), 11, 600, LABEL)

    def scene_wolle(self, p: QPainter, e: float, reduced: bool) -> None:
        at = self.payoff("wolle")
        spin = 0.0 if reduced else e * 4.0
        run = 1.0 if reduced else clamp(e / at, 0.0, 1.0)
        cx, cy = PROP_X - 8.0, PROP_Y + 5.0
        thread = QPainterPath(QPointF(cx + 6.0, cy + 4.0))
        for i in range(1, 17):
            u = i / 16 * run
            thread.lineTo(cx + 6.0 + u * 26.0, cy + 4.0 - u * 9.0 + math.sin(u * 12.0 - spin) * 2.0)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(YARN_DARK_COLOR, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(thread)
        p.save()
        p.translate(cx, cy)
        p.rotate(math.degrees(spin))
        outlined(p, ellipse(0.0, 0.0, 8.0), YARN_COLOR, 1.3)
        p.setPen(QPen(YARN_DARK_COLOR, 0.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for dy, bend in ((-2.4, -6.0), (1.6, -4.0), (5.2, -2.0)):
            arc = QPainterPath(QPointF(-6.2, dy))
            arc.quadTo(QPointF(0.0, dy + bend), QPointF(6.2, dy))
            p.drawPath(arc)
        p.restore()
        _payoff_heart(p, PROP_X + 19.0, PROP_Y - 13.0, e, at, reduced)

    def scene_putzen(self, p: QPainter, e: float, reduced: bool) -> None:
        at = self.payoff("putzen")
        paw_print(p, PROP_X - 2.0, PROP_Y + 3.0, 2.2, -12.0)
        for j, (dx, dy, size) in enumerate(((-15.0, -12.0, 3.4), (12.0, -15.0, 2.8), (16.0, 8.0, 2.4),
                                            (-16.0, 11.0, 2.2))):
            k = 1.0 if reduced else abs(math.sin(e * 4.0 + j * 1.3))
            sparkle(p, PROP_X + dx, PROP_Y + dy, size * k, WHITE)
        _payoff_heart(p, PROP_X + 19.0, PROP_Y - 13.0, e, at, reduced)

    def scene_gaehnen(self, p: QPainter, e: float, reduced: bool) -> None:
        at = self.payoff("gaehnen")
        if e < at:
            for j in range(3):
                u = (e * 0.7 + j / 3) % 1.0
                p.save()
                p.setOpacity(p.opacity() * math.sin(u * math.pi))
                lettering(p, PROP_X - 12.0 + j * 9.0 + u * 5.0, PROP_Y + 14.0 - u * 24.0, "z", 9.0 + j * 2.5,
                          -10.0, SKY_COLOR, 1.8, 0.8)
                p.restore()
            return
        turn = 0.0 if reduced else (e - at) * 40.0
        p.save()
        p.translate(PROP_X, PROP_Y)
        p.rotate(turn)
        p.setPen(QPen(INK, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(8):
            a = math.pi * i / 4
            p.drawLine(QPointF(math.cos(a) * 10.5, math.sin(a) * 10.5), QPointF(math.cos(a) * 15.0, math.sin(a) * 15.0))
        p.restore()
        outlined(p, ellipse(PROP_X, PROP_Y, 8.0), GOLD_COLOR, 1.4)
        sparkle(p, PROP_X + 17.0, PROP_Y - 14.0, 2.8 if reduced else 2.8 * abs(math.sin(e * 4.0)), WHITE)

    def scene_schnurren(self, p: QPainter, e: float, reduced: bool) -> None:
        at = self.payoff("schnurren")
        for j in range(4):
            u = 0.2 + j * 0.2 if reduced else (e * 0.8 + j * 0.25) % 1.0
            p.save()
            p.setOpacity(p.opacity() * (1.0 if reduced else math.sin(u * math.pi)))
            lettering(p, PROP_X - 15.0 + u * 28.0, PROP_Y + 12.0 - u * 22.0 + math.sin(u * 9.0 + j) * 2.0, "r",
                      10.0 + (j % 2) * 2.0, 8.0, GOLD_COLOR, 1.8, 0.8)
            p.restore()
        _payoff_heart(p, PROP_X + 19.0, PROP_Y - 13.0, e, at, reduced)

    def scene_kopf_schief(self, p: QPainter, e: float, reduced: bool) -> None:
        at = self.payoff("kopf_schief")
        bob = 0.0 if reduced else math.sin(e * 3.2)
        if e < at:
            lettering(p, PROP_X, PROP_Y + bob * 2.0, "?", 26.0, 10.0 * bob, YELLOW, 2.2, 1.2)
            return
        lettering(p, PROP_X, PROP_Y, "!", 26.0, 0.0, YELLOW, 2.2, 1.2)
        sparkle(p, PROP_X + 12.0, PROP_Y - 12.0, 3.0 if reduced else 3.0 * abs(math.sin(e * 4.0)), WHITE)

    def zack_decor(self, p: QPainter, t: float, f: Frame, k: float) -> None:
        def draw(pp, x, y, size, moment, j):
            if j % 2 == 0:
                outlined(pp, heart(x, y, 3.0 * size), HEART_COLOR, 1.0)
            else:
                paw_print(pp, x, y, 0.8 * size, math.sin(moment * 5 + j) * 20)
        fly_out(p, t, f, k, draw)

    def error_decor(self, p: QPainter, left: float, top: float) -> None:
        paw_print(p, left + 3.0, top + 4.5, 1.0, -20.0)
