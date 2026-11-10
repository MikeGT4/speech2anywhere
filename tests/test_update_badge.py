# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

import pytest
from PIL import ImageChops, ImageStat

from kira.ui import update_badge


def _figure_box(layer):
    return layer.getchannel("A").point(lambda value: 255 if value > 127 else 0).getbbox()


def _pixels(layer):
    data = layer.tobytes()
    return list(zip(data[0::4], data[1::4], data[2::4], data[3::4]))


def _count_near(layer, colour, tolerance=24):
    return sum(
        1
        for r, g, b, a in _pixels(layer)
        if a > 250 and all(abs(x - y) <= tolerance for x, y in zip((r, g, b), colour[:3]))
    )


def test_star_has_nine_tips_and_nine_valleys():
    points = update_badge._star(100, 100, 50)
    assert len(points) == 18
    assert points[0] == pytest.approx((100, 50))
    assert all(math.dist(p, (100, 100)) == pytest.approx(50) for p in points[0::2])
    assert all(math.dist(p, (100, 100)) == pytest.approx(35) for p in points[1::2])


@pytest.mark.parametrize("size", [16, 32, 64, 128])
def test_corner_badge_fills_the_bottom_right_corner(size):
    layer = update_badge.corner(size)
    assert layer.size == (size, size)
    assert layer.mode == "RGBA"
    left, top, right, bottom = _figure_box(layer)
    assert left >= size * 0.42 and top >= size * 0.42
    assert right >= size - 2 and bottom >= size - 2
    assert right - left <= size * 0.58


def test_corner_badge_draws_ink_green_and_white():
    layer = update_badge.corner(64)
    assert _count_near(layer, update_badge.INK) > 80
    assert _count_near(layer, update_badge.GREEN) > 150
    assert _count_near(layer, update_badge.WHITE, 12) > 30


@pytest.mark.parametrize("size", [84, 168])
def test_solo_badge_fills_the_box_like_the_round_symbols(size):
    left, top, right, bottom = _figure_box(update_badge.solo(size))
    assert size * 0.88 <= right - left <= size * 0.97
    assert size * 0.88 <= bottom - top <= size * 0.97
    assert abs(left + right - size) <= size * 0.06
    assert abs(top + bottom - size) <= size * 0.06


def test_solo_badge_is_the_same_figure_as_the_corner_badge():
    def figure(layer):
        return layer.crop(_figure_box(layer)).resize((96, 96))

    corner = figure(update_badge.corner(512))
    solo = figure(update_badge.solo(512))
    assert max(ImageStat.Stat(ImageChops.difference(corner, solo)).mean) < 3
