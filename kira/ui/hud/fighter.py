# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from kira.ui.hud.base import EASE_IN_OUT, EASE_OUT, clamp

INK = QColor("#111111")
SKIN = QColor("#FFFFFF")
GI = QColor("#FFC400")
PANTS = QColor("#3A3A3A")
BAND = QColor("#FFC400")
TONGUE = QColor("#E5484D")
VIEW = 512.0
_ROUND = (Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


@dataclass(frozen=True)
class Pose:
    head: tuple[float, float, float]
    torso: tuple[float, float, float, float]
    arm_b: tuple[float, float, float, float, float, float]
    arm_f: tuple[float, float, float, float, float, float]
    leg_b: tuple[float, float, float, float, float, float]
    leg_f: tuple[float, float, float, float, float, float]
    foot_b: float = 0.0
    foot_f: float = 0.0
    hand_b: float = 0.0
    hand_f: float = 0.0
    lift: float = 0.0
    face: str = "focus"
    open_b: bool = False
    open_f: bool = False
    arms_front: bool = False
    speed: tuple = ()
    stars: bool = False

    def blend(self, other: "Pose", u: float) -> "Pose":
        u = clamp(u, 0.0, 1.0)

        def mix(a, b):
            if isinstance(a, tuple):
                return tuple(mix(x, y) for x, y in zip(a, b))
            return a + (b - a) * u

        far = other if u >= 0.5 else self
        return Pose(mix(self.head, other.head), mix(self.torso, other.torso), mix(self.arm_b, other.arm_b),
                    mix(self.arm_f, other.arm_f), mix(self.leg_b, other.leg_b), mix(self.leg_f, other.leg_f),
                    mix(self.foot_b, other.foot_b), mix(self.foot_f, other.foot_f), mix(self.hand_b, other.hand_b),
                    mix(self.hand_f, other.hand_f), mix(self.lift, other.lift), far.face, far.open_b, far.open_f,
                    far.arms_front, far.speed, far.stars)


STANCE = Pose((256, 150, 0), (256, 240, 352, 0), (222, 262, 186, 318, 232, 336), (292, 262, 348, 292, 372, 246),
              (236, 350, 206, 412, 192, 470), (276, 350, 318, 406, 342, 470))
STANCE_B = Pose((256, 154, 1), (256, 244, 352, 0), (222, 266, 182, 320, 234, 340), (292, 266, 350, 296, 376, 252),
                (236, 350, 204, 414, 192, 470), (276, 350, 316, 408, 342, 470))
WINDUP_PUNCH = Pose((248, 150, -3), (250, 240, 352, -5), (222, 262, 176, 300, 194, 332), (292, 262, 288, 302, 302, 320),
                    (236, 350, 206, 412, 192, 470), (276, 350, 318, 406, 342, 470))
PUNCH = Pose((272, 152, 6), (262, 240, 352, 10), (222, 262, 172, 304, 190, 338), (292, 262, 378, 258, 466, 252),
             (236, 350, 188, 418, 148, 472), (276, 350, 320, 402, 352, 470), foot_b=20,
             speed=((372, 214, 430, 210), (368, 292, 426, 296)))
CHAMBER = Pose((246, 150, -4), (250, 240, 352, -6), (222, 262, 166, 230, 140, 190), (292, 262, 330, 300, 352, 342),
               (236, 350, 226, 414, 216, 476), (276, 350, 300, 300, 332, 330), foot_f=-40)
KICK = Pose((240, 150, -6), (250, 240, 352, -8), (222, 262, 166, 220, 132, 168), (292, 262, 330, 300, 352, 342),
            (236, 350, 226, 414, 216, 476), (276, 346, 362, 322, 458, 300), foot_f=-10,
            speed=((352, 262, 410, 250), (360, 350, 420, 346)))
RAISE = Pose((250, 150, -2), (254, 240, 352, -3), (222, 262, 178, 310, 206, 346), (292, 262, 330, 200, 372, 150),
             (236, 350, 206, 412, 192, 470), (276, 350, 318, 406, 342, 470), hand_f=-60, open_f=True)
CHOP = Pose((266, 150, 4), (260, 240, 352, 8), (222, 262, 178, 310, 206, 346), (292, 262, 356, 214, 420, 298),
            (236, 350, 206, 412, 192, 470), (276, 350, 318, 406, 342, 470), hand_f=60, open_f=True,
            speed=((388, 188, 402, 234), (448, 196, 448, 246)))
MEDITATE = Pose((256, 182, 0), (256, 270, 384, 0), (222, 292, 196, 350, 206, 406), (292, 292, 318, 350, 306, 406),
                (240, 392, 170, 428, 280, 452), (272, 392, 342, 428, 232, 452), foot_b=15, foot_f=-15,
                face="calm", open_b=True, open_f=True)
MEDITATE_B = Pose((256, 177, 0), (256, 265, 384, 0), (222, 287, 194, 348, 206, 406), (292, 287, 320, 348, 306, 406),
                  (240, 392, 170, 428, 280, 452), (272, 392, 342, 428, 232, 452), foot_b=15, foot_f=-15,
                  face="calm", open_b=True, open_f=True)
CROUCH = Pose((256, 172, -4), (256, 262, 352, -2), (222, 284, 180, 330, 216, 356), (292, 284, 330, 330, 350, 300),
              (236, 350, 196, 404, 196, 470), (276, 350, 322, 404, 330, 470))
VICTORY = Pose((256, 140, -8), (256, 230, 342, -4), (222, 252, 180, 300, 216, 330), (292, 252, 304, 180, 312, 104),
               (236, 340, 206, 390, 240, 424), (276, 340, 312, 392, 282, 428), foot_b=30, foot_f=-30, lift=-40,
               face="laugh")
STUMBLE = Pose((236, 160, -8), (240, 250, 360, -10), (206, 272, 150, 300, 120, 340), (272, 272, 320, 300, 350, 330),
               (230, 358, 210, 420, 200, 470), (262, 360, 330, 420, 380, 460), foot_f=20, face="dizzy",
               open_b=True, open_f=True)
KO = Pose((214, 206, -12), (230, 290, 400, -16), (200, 310, 150, 370, 120, 440), (262, 310, 296, 370, 300, 440),
          (230, 400, 320, 420, 400, 440), (250, 404, 340, 430, 420, 452), foot_b=70, foot_f=70, hand_b=20,
          hand_f=10, face="dizzy", open_b=True, open_f=True, stars=True)
BLOCK = Pose((246, 150, -4), (250, 240, 352, -6), (222, 262, 300, 232, 336, 176), (292, 262, 228, 236, 188, 172),
             (236, 350, 200, 414, 176, 472), (276, 350, 314, 410, 330, 472), foot_b=10, face="squeeze",
             arms_front=True)
LISTEN = Pose((256, 150, 8), (256, 240, 352, 0), (222, 262, 198, 330, 206, 392), (292, 262, 336, 212, 322, 152),
              (240, 350, 232, 412, 226, 472), (272, 350, 284, 412, 292, 472), hand_f=-20, open_f=True, face="wary")

KEYFRAMES = {"stance": STANCE, "punch": PUNCH, "kick": KICK, "chop": CHOP, "meditate": MEDITATE,
             "victory": VICTORY, "ko": KO, "block": BLOCK, "listen": LISTEN}
POSES = tuple(KEYFRAMES)
STRIKES = ("punch", "kick", "chop")
_HOLD = None
CLIPS = {
    "punch": ((0.08, WINDUP_PUNCH, EASE_OUT), (0.08, PUNCH, EASE_OUT), (0.12, _HOLD, None), (0.14, STANCE, EASE_IN_OUT)),
    "kick": ((0.10, CHAMBER, EASE_OUT), (0.08, KICK, EASE_OUT), (0.12, _HOLD, None), (0.16, STANCE, EASE_IN_OUT)),
    "chop": ((0.10, RAISE, EASE_OUT), (0.08, CHOP, EASE_OUT), (0.12, _HOLD, None), (0.14, STANCE, EASE_IN_OUT)),
    "victory": ((0.10, CROUCH, EASE_IN_OUT), (0.18, VICTORY, EASE_OUT)),
    "ko": ((0.15, STUMBLE, EASE_OUT), (0.22, KO, EASE_IN_OUT)),
    "block": ((0.12, BLOCK, EASE_OUT),),
    "listen": ((0.25, LISTEN, EASE_IN_OUT),),
}
IDLE_PERIOD = {"stance": 1.1, "meditate": 2.8}


def duration(clip: str) -> float:
    return sum(seg[0] for seg in CLIPS[clip])


def clip_pose(clip: str, age: float, start: Pose = STANCE) -> Pose:
    current = start
    for seconds, target, ease in CLIPS[clip]:
        if target is None:
            if age < seconds:
                return current
            age -= seconds
            continue
        if age < seconds:
            return current.blend(target, ease(age / seconds))
        age -= seconds
        current = target
    return current


def idle(kind: str, t: float) -> Pose:
    period = IDLE_PERIOD[kind]
    u = 0.5 - 0.5 * math.cos(2 * math.pi * (t % period) / period)
    if kind == "meditate":
        return MEDITATE.blend(MEDITATE_B, u)
    return STANCE.blend(STANCE_B, u)


def strike_point(clip: str) -> tuple[float, float]:
    peak = KEYFRAMES.get(clip, STANCE)
    if clip == "kick":
        return peak.leg_f[4], peak.leg_f[5]
    return peak.arm_f[4], peak.arm_f[5]


def _pen(color: QColor, width: float) -> QPen:
    return QPen(color, width, *_ROUND)


def _limb(p: QPainter, pts, color: QColor, width: float = 36.0) -> None:
    path = QPainterPath(QPointF(pts[0], pts[1]))
    path.lineTo(pts[2], pts[3])
    path.lineTo(pts[4], pts[5])
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(INK, width + 12))
    p.drawPath(path)
    p.setPen(_pen(color, width))
    p.drawPath(path)


def _fist(p: QPainter, x: float, y: float) -> None:
    p.setPen(_pen(INK, 10))
    p.setBrush(SKIN)
    p.drawEllipse(QPointF(x, y), 23, 23)


def _hand(p: QPainter, x: float, y: float, angle: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(_pen(INK, 10))
    p.setBrush(SKIN)
    p.drawEllipse(QPointF(0, 0), 31, 17)
    p.restore()


def _foot(p: QPainter, x: float, y: float, angle: float) -> None:
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawEllipse(QPointF(0, 0), 31, 15)
    p.restore()


def _end(p: QPainter, pts, angle: float, open_hand: bool) -> None:
    if open_hand:
        _hand(p, pts[4], pts[5], angle)
    else:
        _fist(p, pts[4], pts[5])


def _torso(p: QPainter, cx: float, top: float, bottom: float, lean: float) -> None:
    p.save()
    p.translate(cx, bottom)
    p.rotate(lean)
    p.translate(-cx, -bottom)
    p.setPen(_pen(INK, 12))
    p.setBrush(GI)
    p.drawRoundedRect(QRectF(cx - 60, top, 120, bottom - top), 34, 34)
    collar = QPainterPath(QPointF(cx - 34, top + 8))
    collar.lineTo(cx, top + 54)
    collar.lineTo(cx + 34, top + 8)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(INK, 9))
    p.drawPath(collar)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawRoundedRect(QRectF(cx - 66, bottom - 54, 132, 26), 6, 6)
    p.drawRoundedRect(QRectF(cx + 14, bottom - 60, 26, 38), 6, 6)
    p.setPen(_pen(INK, 12))
    p.drawLine(QPointF(cx + 20, bottom - 24), QPointF(cx + 10, bottom + 22))
    p.drawLine(QPointF(cx + 36, bottom - 24), QPointF(cx + 44, bottom + 20))
    p.restore()


def _eye(p: QPainter, cx: float, cy: float, look_x: float, look_y: float) -> None:
    p.setPen(_pen(INK, 8))
    p.setBrush(SKIN)
    p.drawEllipse(QPointF(cx, cy), 20, 26)
    lash = QPainterPath(QPointF(cx - 22, cy - 14))
    lash.cubicTo(QPointF(cx - 12, cy - 34), QPointF(cx + 12, cy - 34), QPointF(cx + 24, cy - 12))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(INK, 13))
    p.drawPath(lash)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawEllipse(QPointF(cx + look_x, cy + look_y + 3), 11, 15)
    p.setBrush(SKIN)
    p.drawEllipse(QPointF(cx + look_x - 4, cy + look_y - 4), 5, 5)


def _closed(p: QPainter, cx: float, cy: float) -> None:
    arc = QPainterPath(QPointF(cx - 22, cy + 4))
    arc.cubicTo(QPointF(cx - 10, cy - 18), QPointF(cx + 10, cy - 18), QPointF(cx + 22, cy + 4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(INK, 11))
    p.drawPath(arc)


def _squeezed(p: QPainter, cx: float, cy: float, sign: int) -> None:
    path = QPainterPath(QPointF(cx - sign * 16, cy - 16))
    path.lineTo(cx + sign * 14, cy)
    path.lineTo(cx - sign * 16, cy + 16)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(INK, 12))
    p.drawPath(path)


def _cross(p: QPainter, cx: float, cy: float) -> None:
    p.setPen(_pen(INK, 11))
    p.drawLine(QPointF(cx - 16, cy - 16), QPointF(cx + 16, cy + 16))
    p.drawLine(QPointF(cx + 16, cy - 16), QPointF(cx - 16, cy + 16))


def _brows(p: QPainter, cx: float, cy: float, kind: str) -> None:
    y = cy - 40
    if kind == "angry":
        left, right = ((cx - 54, y - 8), (cx - 14, y + 8)), ((cx + 14, y + 8), (cx + 54, y - 8))
    elif kind == "worried":
        left, right = ((cx - 54, y + 4), (cx - 14, y - 6)), ((cx + 14, y - 6), (cx + 54, y + 4))
    elif kind == "raised":
        left, right = ((cx - 54, y + 2), (cx - 14, y - 2)), ((cx + 12, y - 14), (cx + 54, y - 18))
    else:
        left, right = ((cx - 54, y - 2), (cx - 14, y + 4)), ((cx + 14, y + 4), (cx + 54, y - 2))
    p.setPen(_pen(INK, 11))
    for (x0, y0), (x1, y1) in (left, right):
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


def _mouth(p: QPainter, cx: float, cy: float, kind: str, level: float) -> None:
    my = cy + 50
    p.setPen(Qt.PenStyle.NoPen)
    if kind == "open":
        rx, ry = 7 + 13 * level, 3 + 17 * level
        p.setBrush(INK)
        p.drawEllipse(QPointF(cx + 4, my + ry * 0.3), rx, ry)
        if level > 0.4:
            p.setBrush(TONGUE)
            p.drawEllipse(QPointF(cx + 4, my + ry * 0.75), rx * 0.55, max(3.0, ry * 0.3))
        return
    if kind == "laugh":
        grin = QPainterPath(QPointF(cx - 26, my - 6))
        grin.cubicTo(QPointF(cx - 20, my + 30), QPointF(cx + 28, my + 30), QPointF(cx + 34, my - 6))
        grin.closeSubpath()
        p.setBrush(INK)
        p.drawPath(grin)
        teeth = QPainterPath(QPointF(cx - 18, my))
        teeth.cubicTo(QPointF(cx, my + 6), QPointF(cx + 14, my + 6), QPointF(cx + 26, my))
        teeth.lineTo(cx + 22, my + 8)
        teeth.lineTo(cx - 14, my + 8)
        teeth.closeSubpath()
        p.setBrush(SKIN)
        p.drawPath(teeth)
        return
    if kind == "jagged":
        points = []
        for i in range(16):
            a = math.pi * i / 8
            k = 1.0 if i % 2 == 0 else 0.7
            points.append(QPointF(cx + 4 + math.cos(a) * 30 * k, my + 6 + math.sin(a) * 20 * k))
        p.setBrush(INK)
        p.drawPolygon(QPolygonF(points))
        return
    if kind == "o":
        p.setBrush(INK)
        p.drawEllipse(QPointF(cx + 4, my + 4), 9, 11)
        return
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(INK, 9))
    if kind == "wave":
        wave = QPainterPath(QPointF(cx - 20, my + 4))
        wave.cubicTo(QPointF(cx - 10, my - 6), QPointF(cx, my + 14), QPointF(cx + 10, my + 4))
        wave.cubicTo(QPointF(cx + 16, my - 2), QPointF(cx + 22, my + 8), QPointF(cx + 28, my + 2))
        p.drawPath(wave)
        return
    line = QPainterPath(QPointF(cx - 12, my + 4))
    line.cubicTo(QPointF(cx, my + 12), QPointF(cx + 12, my + 12), QPointF(cx + 24, my + 2))
    p.drawPath(line)


def _face(p: QPainter, cx: float, cy: float, kind: str, level: float) -> None:
    ex, ey = 34, 2
    if kind in ("shout", "squeeze"):
        _brows(p, cx, cy, "angry")
        _squeezed(p, cx - ex, cy + ey, -1)
        _squeezed(p, cx + ex, cy + ey, 1)
    elif kind in ("calm", "laugh"):
        _brows(p, cx, cy, "flat")
        _closed(p, cx - ex, cy + ey)
        _closed(p, cx + ex, cy + ey)
    elif kind == "dizzy":
        _brows(p, cx, cy, "worried")
        _cross(p, cx - ex, cy + ey)
        _cross(p, cx + ex, cy + ey)
    elif kind == "wary":
        _brows(p, cx, cy, "raised")
        _eye(p, cx - ex, cy + ey, 6, 0)
        _eye(p, cx + ex, cy + ey, 6, 0)
    else:
        _brows(p, cx, cy, "focus")
        _eye(p, cx - ex, cy + ey, 5, 0)
        _eye(p, cx + ex, cy + ey, 5, 0)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(INK, 7))
    p.drawLine(QPointF(cx + 6, cy + 24), QPointF(cx + 12, cy + 34))
    mouths = {"shout": ("jagged", 1.0), "squeeze": ("line", 0.0), "calm": ("line", 0.0), "laugh": ("laugh", 1.0),
              "dizzy": ("wave", 0.0), "wary": ("o", 0.0)}
    mouth, fixed = mouths.get(kind, ("open", level))
    _mouth(p, cx, cy, mouth, fixed)


def _head(p: QPainter, cx: float, cy: float, tilt: float, kind: str, level: float) -> None:
    p.save()
    p.translate(cx, cy)
    p.rotate(tilt)
    p.translate(-cx, -cy)
    hair = [(cx - 94, cy - 20), (cx - 112, cy - 84), (cx - 62, cy - 70), (cx - 50, cy - 142), (cx - 10, cy - 92),
            (cx + 12, cy - 152), (cx + 46, cy - 94), (cx + 94, cy - 124), (cx + 84, cy - 58), (cx + 102, cy - 22),
            (cx + 60, cy - 60), (cx, cy - 76), (cx - 60, cy - 60)]
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in hair]))
    p.setPen(_pen(INK, 8))
    p.setBrush(BAND)
    p.drawPolygon(QPolygonF([QPointF(cx - 96, cy - 50), QPointF(cx - 156, cy - 74), QPointF(cx - 142, cy - 34)]))
    p.drawPolygon(QPolygonF([QPointF(cx - 96, cy - 38), QPointF(cx - 150, cy - 4), QPointF(cx - 130, cy - 26)]))
    p.setPen(_pen(INK, 12))
    p.setBrush(SKIN)
    p.drawEllipse(QPointF(cx, cy), 92, 92)
    p.setPen(_pen(INK, 9))
    p.setBrush(BAND)
    p.drawRoundedRect(QRectF(cx - 98, cy - 66, 196, 30), 7, 7)
    _face(p, cx, cy, kind, level)
    p.restore()


def _speed(p: QPainter, segments) -> None:
    p.setPen(_pen(INK, 9))
    for x0, y0, x1, y1 in segments:
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


def _stars(p: QPainter, cx: float, cy: float, angle: float) -> None:
    p.setPen(_pen(INK, 6))
    p.setBrush(GI)
    for i in range(3):
        a = math.radians(angle + i * 120)
        sx, sy = cx + math.cos(a) * 96, cy - 72 + math.sin(a) * 34
        points = []
        for k in range(8):
            b = math.pi * k / 4 - math.pi / 2
            rr = 16 if k % 2 == 0 else 7
            points.append(QPointF(sx + math.cos(b) * rr, sy + math.sin(b) * rr))
        p.drawPolygon(QPolygonF(points))


def draw(p: QPainter, rect: QRectF, pose: Pose, level: float = 0.0, t: float = 0.0) -> None:
    p.save()
    p.translate(rect.x(), rect.y())
    p.scale(rect.width() / VIEW, rect.height() / VIEW)
    p.setPen(Qt.PenStyle.NoPen)
    shade = QColor(INK)
    shade.setAlphaF(0.16)
    p.setBrush(shade)
    p.drawEllipse(QPointF(256, 478), 118 + pose.lift * 0.4, 13 + pose.lift * 0.05)
    p.translate(0, pose.lift)
    cx, top, bottom, lean = pose.torso
    _limb(p, pose.leg_b, PANTS)
    _foot(p, pose.leg_b[4], pose.leg_b[5], pose.foot_b)
    if not pose.arms_front:
        _limb(p, pose.arm_b, GI)
        _end(p, pose.arm_b, pose.hand_b, pose.open_b)
    _torso(p, cx, top, bottom, lean)
    _limb(p, pose.leg_f, PANTS)
    _foot(p, pose.leg_f[4], pose.leg_f[5], pose.foot_f)
    if pose.speed:
        _speed(p, pose.speed)
    if not pose.arms_front:
        _limb(p, pose.arm_f, GI)
        _end(p, pose.arm_f, pose.hand_f, pose.open_f)
    hx, hy, tilt = pose.head
    _head(p, hx, hy, tilt, pose.face, level)
    if pose.arms_front:
        _limb(p, pose.arm_b, GI)
        _end(p, pose.arm_b, pose.hand_b, pose.open_b)
        _limb(p, pose.arm_f, GI)
        _end(p, pose.arm_f, pose.hand_f, pose.open_f)
    if pose.stars:
        _stars(p, hx, hy, t * 150.0)
    p.restore()


def wobble(pose: Pose, t: float, degrees: float, hz: float) -> Pose:
    hx, hy, tilt = pose.head
    return replace(pose, head=(hx, hy, tilt + degrees * math.sin(2 * math.pi * hz * t)))
