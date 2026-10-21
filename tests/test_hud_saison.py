# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetricsF, QImage, QPainter

from kira.ui import _comic
from kira.ui.hud import comic as cm
from kira.ui.hud import create_style, halloween, saison, weihnachten
from kira.ui.hud.base import Frame, H, W
from tests.test_hud_styles import DT, Driver, _corner_ink, _count_color, _ink, _think_cycle

SEASONS = ("halloween", "weihnachten")
CLASSES = {"halloween": halloween.Halloween, "weihnachten": weihnachten.Weihnachten}
SCENES = [(key, scene) for key in SEASONS for scene in CLASSES[key].SCENES]
STATES = ["talk", "think", "done", "error", "silent", "clip"]
ORANGE = (0xFF, 0x8A, 0x1F)
YELLOW = (0xFF, 0xC4, 0x00)
WHITE = (0xFF, 0xFF, 0xFF)
WINTER = (0x15, 0x29, 0x4B)
FIR = (0x2E, 0x7D, 0x4F)
MOON = (0xFF, 0xF1, 0xB8)
JACK_BOX = (68, 57, 10, 16)
EDGE_SIZES = (0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
SWING_SIZES = (0.75, 4.0)
EDGE_UNITS = 2.75
SEASON_KINDS = {"talk", "shout", "think", "look", "wink", "sad"}


def _reach(key: str, kind: str, reduced: bool = False) -> Driver:
    d = Driver(key, reduced=reduced)
    if kind == "talk":
        d.press()
        d.run(1.5)
    elif kind == "think":
        _think_cycle(d, 1.0, scene=CLASSES[key].SCENES[0])
    elif kind == "done":
        _think_cycle(d, 0.5, scene=CLASSES[key].SCENES[0])
        d.style.done(d.t, d.f)
        d.run(0.15, amp=0.0)
    elif kind == "error":
        d.style.error(d.t, "Mikrofon nicht gefunden.|Gerät prüfen, dann erneut drücken.", d.f)
        d.run(0.3, amp=0.0)
    elif kind == "silent":
        d.press()
        d.run(0.9, amp=0.0)
    else:
        d.press()
        d.run(0.4, amp=3.0)
    return d


def _glow_strip(d: Driver) -> int:
    img = QImage(round(W * d.f.px), round(H * d.f.px), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(d.f.px, d.f.px)
    d.style.backdrop(p, d.t, d.f, d.an)
    p.end()
    x, y, w, h = (round(v * d.f.px) for v in (93, 46, 6, 8))
    return _ink(img.copy(x, y, w, h))


@pytest.mark.parametrize("key", SEASONS)
def test_scene_and_clock_are_chosen_by_chance_per_dictation(qapp, key):
    d = Driver(key)
    d.style._rng = random.Random(7)
    scenes, clocks = set(), set()
    for _ in range(24):
        d.press()
        scenes.add(d.style.scene)
        clocks.add(d.style.clock)
        d.style.abort(d.t)
        d.run(0.2, amp=0.0)
    assert scenes == set(CLASSES[key].SCENES)
    assert clocks == set(CLASSES[key].CLOCKS)


@pytest.mark.parametrize("key", SEASONS)
def test_scene_changes_every_five_seconds_but_never_with_animations_off(qapp, key):
    first, second, third = CLASSES[key].SCENES
    d = Driver(key)
    _think_cycle(d, 4.9, scene=first)
    assert d.style.scene_at(d.t, d.f)[0] == first
    d.run(0.2, amp=0.0)
    assert d.style.scene_at(d.t, d.f)[0] == second
    d.run(5.0, amp=0.0)
    assert d.style.scene_at(d.t, d.f)[0] == third
    still = Driver(key, reduced=True)
    _think_cycle(still, 11.0, scene=second)
    assert still.style.scene_at(still.t, still.f)[0] == second


@pytest.mark.parametrize("key, scene", SCENES)
def test_scene_stays_when_polish_begins(qapp, key, scene):
    d = Driver(key)
    _think_cycle(d, 0.8, scene=scene)
    d.f.polishing = True
    d.f.polish_t = d.t
    d.run(0.3, amp=0.0)
    assert d.style.scene_at(d.t, d.f)[0] == scene


@pytest.mark.parametrize("key, scene", SCENES)
@pytest.mark.parametrize("reduced", [False, True])
def test_long_wait_keeps_drawing_and_sweats(qapp, key, scene, reduced):
    d = Driver(key, reduced=reduced)
    _think_cycle(d, 7.0, 7.0, scene)
    assert d.style.visible
    assert d.style.sweating(d.t)
    assert _ink(d.render()) > 2000


@pytest.mark.parametrize("key, scene", SCENES)
@pytest.mark.parametrize("polish", [0.0, 0.4])
def test_thinking_moves_unless_reduced(qapp, key, scene, polish):
    for reduced in (False, True):
        d = Driver(key, reduced=reduced)
        _think_cycle(d, 1.0, polish, scene)
        first = d.render()
        d.t += 0.2
        second = d.render()
        x, y, w, h = (round(v * d.f.px) for v in (94, 3, 158, 56))
        assert (first.copy(x, y, w, h) != second.copy(x, y, w, h)) is not reduced


@pytest.mark.parametrize("key, scene, box, rgb", [
    ("halloween", "kessel", (100, 10, 44, 44), (0x2B, 0x2B, 0x31)),
    ("halloween", "besen", (100, 20, 150, 40), (0xF2, 0xC1, 0x4E)),
    ("halloween", "kuerbis", (100, 10, 44, 44), ORANGE),
    ("weihnachten", "schlitten", (94, 3, 158, 56), (0xC9, 0x25, 0x2C)),
    ("weihnachten", "schwibbogen", (100, 20, 44, 30), (0xFF, 0xF6, 0xE0)),
    ("weihnachten", "plaetzchen", (106, 30, 32, 16), (0xE3, 0xA8, 0x57)),
])
def test_every_scene_shows_its_props(qapp, key, scene, box, rgb):
    d = Driver(key, reduced=True)
    _think_cycle(d, 0.8, scene=scene)
    assert _count_color(d.render(), box, rgb, d.f.px, tol=16) > 10


@pytest.mark.parametrize("key", SEASONS)
@pytest.mark.parametrize("reduced", [False, True])
@pytest.mark.parametrize("shift", [0.0, 59.8, 60.2, 125.4])
def test_clock_draws_in_the_corner_also_at_the_full_minute(qapp, key, reduced, shift):
    d = Driver(key, reduced=reduced)
    d.press()
    d.style.t0 -= shift
    d.run(0.4)
    assert d.style.mode == "rec"
    img = d.render()
    if key == "halloween":
        assert _corner_ink(img, d.f.px) > 400
    else:
        assert _count_color(img, (226, 6, 32, 22), FIR, d.f.px) > 20


def test_moon_waxes_over_the_minute(qapp):
    counts = []
    for shift in (0.0, 45.0):
        d = Driver("halloween")
        d.press()
        d.style.t0 -= shift
        d.run(0.4)
        counts.append(_count_color(d.render(), (235, 5, 18, 18), MOON, d.f.px))
    assert counts[1] > counts[0] + 50


def test_advent_wreath_lights_one_more_candle_every_quarter_minute():
    lit = weihnachten.wreath_lit
    assert [lit(s, False) for s in (0.4, 14.9, 15.2, 30.1, 45.0, 59.5)] == [1, 1, 2, 3, 4, 4]
    assert lit(60.3, False) == 4
    assert lit(61.0, False) == 1
    assert lit(60.3, True) == 1


@pytest.mark.parametrize("kind", STATES)
def test_pumpkin_stands_behind_the_mascot_and_the_tile_stays_yellow(qapp, kind):
    d = _reach("halloween", kind)
    img = d.render()
    assert _count_color(img, JACK_BOX, ORANGE, d.f.px) > 60
    assert _count_color(img, (3.5, 24, 5, 30), YELLOW, d.f.px) > 300
    assert _count_color(img, (4, 24, 50, 44), ORANGE, d.f.px) == 0


def test_pumpkin_dims_without_signal_and_goes_dark_on_error(qapp):
    style = create_style("halloween")
    an = SimpleNamespace(silent=False, clip=False)
    style.mode = "rec"
    assert style.jack_light(an) == 1.0
    an.silent = True
    assert style.jack_light(an) == halloween.JACK_DIM
    style.mode = "error"
    assert style.jack_light(an) == 0.0
    assert _glow_strip(_reach("halloween", "talk")) > 0
    assert _glow_strip(_reach("halloween", "error")) == 0


def test_snow_falls_and_stands_still_with_animations_off():
    now, later = weihnachten.snowflakes(100.0, False), weihnachten.snowflakes(100.3, False)
    assert len(now) == weihnachten.FLAKE_COUNT
    assert all(a[1] != b[1] for a, b in zip(now, later))
    assert all(-2.0 <= y < weihnachten.SNOW_FALL_H - 2.0 for _x, y, _r, _c in now)
    assert weihnachten.snowflakes(100.0, True) == weihnachten.snowflakes(500.0, True)


@pytest.mark.parametrize("kind", STATES)
def test_winter_night_stage_shows_in_every_state(qapp, kind):
    d = _reach("weihnachten", kind)
    assert _count_color(d.render(), (72, 3, 12, 4), WINTER, d.f.px) > 60


def test_thought_cloud_and_hint_bubble_wear_snow(qapp):
    think = _reach("weihnachten", "think")
    assert _count_color(think.render(), (110, 6, 120, 6), WHITE, think.f.px) > 400
    silent = _reach("weihnachten", "silent")
    assert _count_color(silent.render(), (100, 5, 140, 6), WHITE, silent.f.px) > 400


@pytest.mark.parametrize("key, word", [("halloween", "Hokuspokus!"), ("weihnachten", "Bescherung!")])
def test_done_word_fits_the_burst_uncut(qapp, key, word):
    assert create_style(key).ZACK_WORD == word
    px = saison.zack_px(word)
    assert px >= 14
    assert QFontMetricsF(_comic.baloo(800, px)).horizontalAdvance(word) <= saison.ZACK_TEXT_W


@pytest.mark.parametrize("key", SEASONS)
def test_seasonal_bla_first_then_spoken_fragments_in_warm_colors(qapp, key):
    d = Driver(key)
    d.press()
    d.run(0.5)
    style = d.style
    assert style._words and {w.text for w in style._words} <= set(style.WORDS)
    assert all(w.fill.name() == saison.YELLOW.name() for w in style._words)
    style.feed_words(d.t, ["Politur", "morgen"])
    d.run(0.8)
    spoken = [w for w in style._words if w.text in ("Politur", "morgen")]
    assert {w.text for w in spoken} == {"Politur", "morgen"}
    assert {w.fill.name() for w in spoken} <= {c.name() for c in style.WORD_FILLS}


@pytest.mark.parametrize("key", SEASONS)
def test_long_fragments_shrink_to_fit_the_lane(qapp, key):
    d = Driver(key)
    d.press()
    d.style.feed_words(d.t, ["Donaudampfschifffahrt"])
    d.run(0.5)
    word = next(w for w in d.style._words if w.text.startswith("Donau"))
    assert word.width <= cm.MAX_WORD_W + 0.5


@pytest.mark.parametrize("key", SEASONS)
def test_reduced_motion_keeps_the_dictation_still(qapp, key):
    d = Driver(key, reduced=True)
    d.press()
    d.run(1.2)
    first = d.render()
    d.t += 0.2
    assert d.render() == first
    moving = Driver(key)
    moving.press()
    moving.run(1.2)
    first = moving.render()
    moving.t += 0.2
    assert moving.render() != first


@pytest.mark.parametrize("key", SEASONS)
def test_hat_stays_still_with_animations_off_while_the_voice_changes(qapp, key):
    d = Driver(key, reduced=True)
    d.press()
    d.run(1.2)
    x, y, w, h = (round(v * d.f.px) for v in (12, 0, 48, 21))
    first = d.render().copy(x, y, w, h)
    d.run(0.4, amp=0.9)
    assert d.render().copy(x, y, w, h) == first


def _alpha(img: QImage) -> np.ndarray:
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width(), 3]


def _air(draw, size: float) -> tuple[int, int, int, int] | None:
    img = QImage(round(W * size), round(H * size), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(size, size)
    draw(p)
    p.end()
    alpha = _alpha(img)
    rows = np.flatnonzero(alpha.any(axis=1))
    cols = np.flatnonzero(alpha.any(axis=0))
    if not len(rows):
        return None
    return (int(cols[0]), int(rows[0]), img.width() - 1 - int(cols[-1]), img.height() - 1 - int(rows[-1]))


def _short_of_air(draw, sizes: tuple[float, ...] = EDGE_SIZES) -> list:
    out = []
    for size in sizes:
        air = _air(draw, size)
        if air is not None and min(air) < math.floor(EDGE_UNITS * size):
            out.append((size, air))
    return out


def _framed(d: Driver, margin: int = 16) -> tuple[QImage, int]:
    w, h = round(W * d.f.px), round(H * d.f.px)
    img = QImage(w + 2 * margin, h + 2 * margin, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.translate(margin, margin)
    p.scale(d.f.px, d.f.px)
    p.setOpacity(d.style.fade_alpha(d.t))
    d.style.paint(p, d.t, d.f, d.tap, d.an)
    p.end()
    alpha = _alpha(img).copy()
    alpha[margin:margin + h, margin:margin + w] = 0
    return img, int(np.count_nonzero(alpha))


def _season_run(key: str, reduced: bool) -> tuple[set, set, list]:
    d = Driver(key, reduced=reduced)
    poses: set[saison.Pose] = set()
    decors: set[tuple[float, bool, float]] = set()
    outside: list[tuple[str, float]] = []
    draw, decor = d.style.accessory, d.style.zack_decor

    def record_pose(p, pose):
        poses.add(pose)
        draw(p, pose)

    def record_decor(p, t, f, k):
        decors.add((t, f.reduced, k))
        decor(p, t, f, k)

    def render() -> QImage:
        img, count = _framed(d)
        if count:
            outside.append((d.style.mode, round(d.t, 3)))
        return img

    d.style.accessory = record_pose
    d.style.zack_decor = record_decor
    d.render = render
    d.press()
    d.run(1.5)
    d.run(2.0, amp=0.95)
    d.run(1.0, amp=3.0)
    d.run(1.2, amp=0.0)
    d.style.abort(d.t)
    d.run(0.3, amp=0.0)
    for scene in CLASSES[key].SCENES:
        d.press()
        d.style.scene = scene
        d.run(0.6)
        d.style.release(d.t, d.f)
        d.run(7.6, amp=0.0)
        d.f.polishing = True
        d.f.polish_t = d.t
        d.run(0.4, amp=0.0)
        d.f.polishing = False
        d.style.done(d.t, d.f)
        d.run(0.8, amp=0.0)
    d.press()
    d.style.t0 -= 59.0
    d.run(2.5)
    d.style.abort(d.t)
    d.run(0.3, amp=0.0)
    d.style.error(d.t, "Mikrofon nicht gefunden.|Gerät prüfen, dann erneut drücken.", d.f)
    d.run(5.5, amp=0.0)
    return poses, decors, outside


@pytest.mark.parametrize("key", SEASONS)
@pytest.mark.parametrize("reduced", [False, True])
def test_every_frame_stays_in_the_window_and_hat_and_decor_keep_their_air(qapp, key, reduced):
    style = create_style(key)
    poses, decors, outside = _season_run(key, reduced)
    assert {pose.kind for pose in poses} == SEASON_KINDS
    assert decors
    assert not outside, outside[:6]
    tight = []
    for pose in poses:
        tight += [(pose.kind, round(pose.t, 3), miss)
                  for miss in _short_of_air(lambda p: style.accessory(p, pose), SWING_SIZES)]
    for t, still, k in decors:
        frame = Frame(reduced=still)
        tight += [("decor", round(k, 3), miss) for miss in _short_of_air(lambda p: style.zack_decor(p, t, frame, k))]
    assert not tight, tight[:6]


@pytest.mark.parametrize("key", SEASONS)
def test_hat_keeps_its_air_at_full_swing(qapp, key):
    style = create_style(key)
    poses = [saison.Pose(kind, 1.0, 0.0, (x, 12), "smile", True)
             for kind in SEASON_KINDS for x in (-12, 12)]
    for i in range(1512):
        t = i / 120
        poses += [saison.Pose(kind, 1.0, t) for kind in ("talk", "shout", "think")]
        poses += [saison.Pose("look", 0.0, t, (x, 12), "smile") for x in (-12, 12)]
    tight = []
    for pose in poses:
        tight += [(pose.kind, pose.reduced, round(pose.t, 3), miss)
                  for miss in _short_of_air(lambda p: style.accessory(p, pose), SWING_SIZES)]
    assert not tight, tight[:6]


@pytest.mark.parametrize("key", SEASONS)
def test_done_decor_keeps_its_air_at_full_swing(qapp, key):
    style = create_style(key)
    tight = []
    for still in (False, True):
        frame = Frame(reduced=still)
        for i in range(241):
            k, t = i / 240, 100.0 + i / 97
            tight += [(still, round(k, 3), miss)
                      for miss in _short_of_air(lambda p: style.zack_decor(p, t, frame, k), SWING_SIZES)]
    assert not tight, tight[:6]


@pytest.mark.parametrize("key", SEASONS)
def test_host_passes_spoken_words_to_seasonal_styles(qtbot, tmp_path, key):
    from kira.ui.hud_qt import PopupHUD
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"ui:\n  hud_style: {key}\n", encoding="utf-8")
    hud = PopupHUD(config_path=cfg, state_dir=tmp_path)
    qtbot.addWidget(hud)
    assert hud.style_key == key
    assert hud.wants_live_words
    hud.set_phase("rec")
    hud.push_words(["Hallo"])
    qtbot.waitUntil(lambda: "Hallo" in hud._style._queue, timeout=1000)
    hud.set_phase("idle")
    qtbot.waitUntil(lambda: not hud.isVisible(), timeout=2000)


@pytest.mark.parametrize("key", SEASONS)
def test_preview_feeds_fragments_to_seasonal_styles(qapp, key):
    from kira.ui.hud_preview import RELEASE_S, PreviewDriver
    calls: list[list[str]] = []
    d = PreviewDriver(key)
    d.restart(0.0)
    d.style.feed_words = lambda t, words: calls.append(list(words))
    t = 0.0
    while t < RELEASE_S:
        t += DT
        d.advance(t)
    assert not d.failed
    assert calls


def test_seasonal_styles_skip_path_booleans_and_powers():
    root = Path(saison.__file__).parent
    for name in ("saison.py", "halloween.py", "weihnachten.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert not re.search(r"\.(united|intersected|subtracted|simplified|pointAtPercent|toReversed)\(", source), name
        assert "**" not in source, name
        assert not re.search(r"\b(sum|hypot)\(", source), name
