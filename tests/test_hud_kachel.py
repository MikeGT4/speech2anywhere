# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math
import sys
from dataclasses import replace

import numpy as np
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPainter

from kira.ui import hud_preview
from kira.ui.hud import comic as cm, create_style, fachgebiet, katze, manga, saison
from kira.ui.hud.base import Frame

MASCOTS = ("halloween", "weihnachten", "katze", "medizin", "medikamente", "jura", "wirtschaft", "technik", "chemie", "it")
KINDS = ("talk", "shout", "think", "look", "wink", "sad")
INSET = 6.125
TOLERANCE = 0.5
PX = 8
ORIGIN = -24.0
SPAN = 124.0


class Ink:
    def __init__(self) -> None:
        self.img = QImage(round(SPAN * PX), round(SPAN * PX), QImage.Format.Format_ARGB32_Premultiplied)
        self.img.fill(Qt.GlobalColor.transparent)
        self.p = QPainter(self.img)
        self.p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.p.scale(PX, PX)
        self.p.translate(-ORIGIN, -ORIGIN)

    def add(self, draw) -> None:
        self.p.save()
        draw(self.p)
        self.p.restore()

    def mask(self) -> np.ndarray:
        if self.p.isActive():
            self.p.end()
        ptr = self.img.constBits()
        ptr.setsize(self.img.sizeInBytes())
        rows = np.frombuffer(ptr, np.uint8).reshape(self.img.height(), self.img.bytesPerLine() // 4, 4)
        return rows[:, :self.img.width(), 3] > 0

    def box(self) -> tuple[float, float, float, float]:
        alpha = self.mask()
        rows = np.flatnonzero(alpha.any(axis=1))
        cols = np.flatnonzero(alpha.any(axis=0))
        assert len(rows), "nichts gezeichnet"
        return (ORIGIN + cols[0] / PX, ORIGIN + rows[0] / PX, ORIGIN + (cols[-1] + 1) / PX,
                ORIGIN + (rows[-1] + 1) / PX)


def _poses() -> list[saison.Pose]:
    poses = [saison.Pose(kind, level, 0.0, (x, 12), "smile", True)
             for kind in KINDS for x in (-12, 0, 12) for level in (0.0, 1.0)]
    for i in range(480):
        t = i / 60
        poses += [saison.Pose("talk", level, t) for level in (0.0, 0.5, 1.0)]
        poses += [saison.Pose(kind, 1.0, t) for kind in ("shout", "think", "wink", "sad")]
        poses += [saison.Pose("look", 0.0, t, (x, 12), "smile") for x in (-12, 0, 12)]
    return poses


def _cats() -> list[katze.Cat]:
    cats = [katze.SAD, katze.HISS, katze.PUZZLED, katze.THINKING]
    for duration, move in katze.REC_MOTIONS.values():
        for i in range(int(duration * 60) + 1):
            for level in (0.0, 1.0):
                cats.append(move(katze.Cat(mouth="talk", level=level, twitch=level - 0.5, ear_l=-4 * level), i / 60))
    cats += [katze.bell_shake(katze.WINK, i / 60) for i in range(121)]
    for i in range(480):
        cats.append(replace(katze.PUZZLED, tilt=-14 + 3 * math.sin(i / 60 * 1.8)))
        cats += [move(katze.THINKING, i / 60) for move in katze.SCENE_MOTIONS.values()]
    return cats


def _margins(box, frame=cm.TILE) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    return y0 - frame.top(), frame.bottom() - y1, x0 - frame.left(), frame.right() - x1


def _assert_centred_with_inset(box) -> None:
    top, bottom, left, right = _margins(box)
    assert min(top, bottom, left, right) >= INSET - TOLERANCE, (top, bottom, left, right)
    assert min(top, bottom, left, right) <= INSET + TOLERANCE, (top, bottom, left, right)
    assert abs(top - bottom) <= TOLERANCE, (top, bottom)
    assert abs(left - right) <= TOLERANCE, (left, right)


def test_comic_bubble_sits_centred_in_the_tile(qapp, monkeypatch):
    monkeypatch.setattr(cm, "paint_tile", lambda p: None)
    ink = Ink()
    for k in range(9):
        ink.add(lambda p, k=k: cm._mascot(p, "talk", k / 8))
    for kind in ("wink", "think", "sad", "shout"):
        ink.add(lambda p, kind=kind: cm._mascot(p, kind))
    for i in range(16):
        look = cm._circling_look(i * 0.7 / 16, 0.7)
        ink.add(lambda p, look=look: cm._mascot_looking(p, look, "o"))
    assert cm.FIGURE_SCALE == 1.0
    _assert_centred_with_inset(ink.box())


@pytest.mark.parametrize("key", MASCOTS)
def test_mascot_and_accessory_sit_centred_in_the_tile_in_every_pose(qapp, key):
    style = create_style(key)
    style.paint_tile = lambda p, pose: None
    ink = Ink()
    for pose in _poses():
        ink.add(lambda p, pose=pose: style.figure(p, pose))
    if key == "katze":
        look = saison.Pose("look", 0.0, 0.0, katze.THINKING.look)
        for cat in _cats():
            ink.add(lambda p, cat=cat: style.figure(p, look, cat))
    _assert_centred_with_inset(ink.box())


@pytest.mark.parametrize("key", ["jura", "medikamente"])
def test_hourglass_stays_in_the_tile_and_clear_of_the_figure(qapp, key):
    style = create_style(key)
    style.paint_tile = lambda p, pose: None
    figure = Ink()
    for scene, (look, before, after) in style.LOOKS.items():
        for i in range(0, 720, 4):
            t = i / 60
            for reduced in (False, True):
                pose = style.pose("look", t, Frame(reduced=reduced), look=look,
                                  mouth=after if t >= style.payoff(scene) else before)
                figure.add(lambda p, pose=pose: style.figure(p, pose))
    glass = Ink()
    x, y, size = style.HOURGLASS
    for i in range(0, 217, 2):
        for reduced in (False, True):
            glass.add(lambda p, age=i / 120, reduced=reduced: fachgebiet.hourglass(p, x, y, age, reduced, size))
    tile = Ink()
    tile.add(lambda p: p.fillPath(fachgebiet.tile_path(), QColor(0, 0, 0)))
    swept, drawn, inside = glass.mask(), figure.mask(), tile.mask()
    assert swept.any() and drawn.any()
    assert not (swept & drawn).any()
    assert not (swept & ~inside).any()


def test_manga_thumbnail_shows_the_whole_fighter_centred(qapp, monkeypatch):
    ink = Ink()
    draw = manga._figure

    def capture(p, pose, level=0.0, t=0.0, dx=0.0, dy=0.0):
        ink.add(lambda q: draw(q, pose, level, t, dx, dy))
        draw(p, pose, level, t, dx, dy)

    monkeypatch.setattr(manga, "_figure", capture)
    hud_preview.load_fonts()
    driver = hud_preview._poster("manga")
    sink = QImage(40, 40, QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(sink)
    driver.paint(p, 0, 0)
    p.end()
    top, bottom, left, right = _margins(ink.box(), hud_preview.thumb_crop("manga"))
    assert min(top, bottom, left, right) > 0, (top, bottom, left, right)
    assert abs(top - bottom) <= TOLERANCE and abs(left - right) <= TOLERANCE, (top, bottom, left, right)


@pytest.mark.parametrize("key", ("comic",) + MASCOTS)
def test_tile_styles_keep_the_tile_as_thumbnail_crop(key):
    assert hud_preview.thumb_crop(key) == cm.TILE
