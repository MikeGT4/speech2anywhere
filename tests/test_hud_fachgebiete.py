# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)

from PyQt6.QtGui import QFontMetricsF, QImage, QPainter

from kira import texte
from kira.ui import _comic
from kira.ui.hud import chemie, comic as cm, create_style, fachgebiet, jura, medikamente, saison, wirtschaft
from kira.ui.hud.base import H, W, Frame
from tests.test_hud_saison import EDGE_SIZES, SWING_SIZES, _framed, _short_of_air
from tests.test_hud_styles import DT, Driver, _corner_ink, _count_color, _ink, _think_cycle

FIELDS = ("medizin", "medikamente", "jura", "wirtschaft", "technik", "chemie", "it")
REFINED = ("medikamente", "jura")
SCENES = [(key, scene) for key in FIELDS for scene in create_style(key).SCENES]
FIELD_KINDS = {"talk", "shout", "think", "look", "wink", "sad"}
ERROR_TEXT = "Mikrofon nicht gefunden.|Gerät prüfen, dann erneut drücken."
STILL_REGIONS = {
    "medizin": (10, 2, 50, 20),
    "medikamente": (26, 4, 18, 32),
    "jura": (12, 18, 46, 32),
    "wirtschaft": (26, 59, 20, 17),
    "technik": (10, 2, 50, 20),
    "chemie": (10, 6, 50, 16),
    "it": (14, 10, 42, 10),
}
PROPS = [
    ("medizin", "rezept", (101, 10, 40, 7), (0xDC, 0xEB, 0xF5)),
    ("medizin", "roentgen", (104, 14, 34, 27), (0x14, 0x20, 0x2B)),
    ("medizin", "abhoeren", (104, 22, 26, 24), (0xE5, 0x39, 0x4A)),
    ("medikamente", "dosieren", (108, 34, 26, 4), (0xC9, 0xA2, 0x4E)),
    ("medikamente", "etikett", (111, 25, 20, 19), (0xF3, 0xEB, 0xDD)),
    ("medikamente", "mischen", (106, 16, 30, 38), (0x5A, 0x6A, 0x72)),
    ("jura", "akte", (108, 16, 26, 26), (0x2B, 0x24, 0x20)),
    ("jura", "gesetz", (119, 20, 8, 32), (0xC9, 0xA2, 0x4E)),
    ("jura", "kalender", (110, 26, 22, 18), (0x2B, 0x24, 0x20)),
    ("wirtschaft", "kurs", (100, 10, 46, 40), (0x2E, 0x9E, 0x5B)),
    ("wirtschaft", "kasse", (103, 20, 36, 22), (0x3B, 0x46, 0x51)),
    ("wirtschaft", "rechner", (106, 27, 30, 20), (0xE9, 0xEC, 0xEF)),
    ("technik", "rakete", (108, 36, 34, 16), (0xE6, 0xE6, 0xE6)),
    ("technik", "bauplan", (100, 10, 42, 38), (0x1F, 0x5F, 0xAF)),
    ("technik", "gluehbirne", (112, 36, 18, 12), (0xED, 0xED, 0xED)),
    ("chemie", "titration", (108, 40, 26, 10), (0xE8, 0x45, 0x7A)),
    ("chemie", "molekuel", (113, 23, 16, 16), (0xE5, 0x48, 0x4D)),
    ("chemie", "kristall", (108, 12, 26, 38), (0xBD, 0xE7, 0xFF)),
    ("it", "build", (100, 10, 42, 36), (0x1F, 0x26, 0x33)),
    ("it", "bug", (100, 10, 42, 36), (0x1F, 0x26, 0x33)),
    ("it", "merge", (100, 18, 44, 8), (0x4F, 0xC1, 0xFF)),
]


@pytest.mark.parametrize("key", FIELDS)
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
    assert scenes == set(d.style.SCENES)
    assert clocks == set(d.style.CLOCKS)


@pytest.mark.parametrize("key", FIELDS)
def test_scene_changes_every_five_seconds_but_never_with_animations_off(qapp, key):
    first, second, third = create_style(key).SCENES
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


@pytest.mark.parametrize("key, scene, box, rgb", PROPS)
def test_every_scene_shows_its_props(qapp, key, scene, box, rgb):
    d = Driver(key, reduced=True)
    _think_cycle(d, 0.8, scene=scene)
    assert _count_color(d.render(), box, rgb, d.f.px, tol=16) > 10


@pytest.mark.parametrize("key", FIELDS)
@pytest.mark.parametrize("reduced", [False, True])
@pytest.mark.parametrize("shift", [0.0, 59.8, 60.2, 125.4])
def test_clock_draws_in_the_corner_also_at_the_full_minute(qapp, key, reduced, shift):
    d = Driver(key, reduced=reduced)
    d.press()
    d.style.t0 -= shift
    d.run(0.4)
    assert d.style.mode == "rec"
    assert _corner_ink(d.render(), d.f.px) > 400


@pytest.mark.parametrize("key", FIELDS)
@pytest.mark.parametrize("language", ["de", "en"])
def test_done_word_fits_the_burst_uncut(qapp, key, language):
    texte.set_language(language)
    try:
        word = texte.tr(create_style(key).ZACK_WORD)
        px = saison.zack_px(word)
        assert px >= 14
        assert QFontMetricsF(_comic.baloo(800, px)).horizontalAdvance(word) <= saison.ZACK_TEXT_W
    finally:
        texte.set_language("de")


@pytest.mark.parametrize("key", FIELDS)
def test_bla_first_then_spoken_fragments_in_the_field_colors(qapp, key):
    d = Driver(key)
    d.press()
    d.run(0.5)
    style = d.style
    assert style._words and {w.text for w in style._words} <= set(style.WORDS)
    assert all(w.fill.name() == saison.YELLOW.name() for w in style._words)
    style.feed_words(d.t, ["Anamnese", "Bilanz"])
    d.run(0.8)
    spoken = [w for w in style._words if w.text in ("Anamnese", "Bilanz")]
    assert {w.text for w in spoken} == {"Anamnese", "Bilanz"}
    assert {w.fill.name() for w in spoken} <= {c.name() for c in style.WORD_FILLS}


@pytest.mark.parametrize("key", FIELDS)
def test_long_fragments_shrink_to_fit_the_lane(qapp, key):
    d = Driver(key)
    d.press()
    d.style.feed_words(d.t, ["Donaudampfschifffahrt"])
    d.run(0.5)
    word = next(w for w in d.style._words if w.text.startswith("Donau"))
    assert word.width <= cm.MAX_WORD_W + 0.5


@pytest.mark.parametrize("key", FIELDS)
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


@pytest.mark.parametrize("key", FIELDS)
def test_accessory_stays_still_with_animations_off_while_the_voice_changes(qapp, key):
    d = Driver(key, reduced=True)
    d.press()
    d.run(1.2)
    x, y, w, h = (round(v * d.f.px) for v in STILL_REGIONS[key])
    first = d.render().copy(x, y, w, h)
    d.run(0.4, amp=0.9)
    assert d.render().copy(x, y, w, h) == first


def _field_run(key: str, reduced: bool) -> tuple[set, set, list]:
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
    for scene in d.style.SCENES:
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
    d.style.error(d.t, ERROR_TEXT, d.f)
    d.run(5.5, amp=0.0)
    return poses, decors, outside


@pytest.mark.parametrize("key", FIELDS)
@pytest.mark.parametrize("reduced", [False, True])
def test_every_frame_stays_in_the_window_and_accessory_and_decor_keep_their_air(qapp, key, reduced):
    style = create_style(key)
    poses, decors, outside = _field_run(key, reduced)
    assert {pose.kind for pose in poses} == FIELD_KINDS
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


@pytest.mark.parametrize("key", FIELDS)
def test_accessory_keeps_its_air_at_full_swing(qapp, key):
    style = create_style(key)
    poses = [saison.Pose(kind, 1.0, 0.0, (x, 12), "smile", True)
             for kind in FIELD_KINDS for x in (-12, 12)]
    for i in range(1512):
        t = i / 120
        poses += [saison.Pose(kind, 1.0, t) for kind in ("talk", "shout", "think")]
        poses += [saison.Pose("look", 0.0, t, (x, 12), "smile") for x in (-12, 12)]
    tight = []
    for pose in poses:
        tight += [(pose.kind, pose.reduced, round(pose.t, 3), miss)
                  for miss in _short_of_air(lambda p: style.accessory(p, pose), SWING_SIZES)]
    assert not tight, tight[:6]


@pytest.mark.parametrize("key", FIELDS)
def test_done_decor_keeps_its_air_at_full_swing(qapp, key):
    style = create_style(key)
    tight = []
    for still in (False, True):
        frame = Frame(reduced=still)
        for i in range(241):
            k, t = i / 240, 100.0 + i / 97
            tight += [(still, round(k, 3), miss)
                      for miss in _short_of_air(lambda p: style.zack_decor(p, t, frame, k), EDGE_SIZES)]
    assert not tight, tight[:6]


@pytest.mark.parametrize("key", FIELDS)
def test_host_passes_spoken_words_to_field_styles(qtbot, tmp_path, key):
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


@pytest.mark.parametrize("key", FIELDS)
def test_preview_feeds_fragments_to_field_styles(qapp, key):
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


def test_heartbeat_line_keeps_beating_without_signal(qapp):
    d = Driver("medizin")
    d.press()
    d.run(2.0, amp=0.0)
    assert d.an.silent
    window = [d.t - k / 60 for k in range(180)]
    assert max(d.style.ecg_at(moment) for moment in window) > 0.3


def test_heartbeat_line_beats_higher_while_speaking(qapp):
    quiet, loud = Driver("medizin"), Driver("medizin")
    quiet.press()
    quiet.run(3.0, amp=0.0)
    loud.press()
    loud.run(3.0, amp=0.9)
    assert max(amp for _s, _p, amp in loud.style._beats) > max(amp for _s, _p, amp in quiet.style._beats) + 0.2


def test_meter_needle_rests_without_signal_and_pins_in_the_red_when_too_close(qapp):
    d = Driver("technik")
    d.press()
    d.run(1.5, amp=0.0)
    assert d.style._needle < 0.05
    d.run(0.4, amp=3.0)
    assert d.an.clip
    assert d.style._needle > 0.9


def test_coin_stack_grows_with_spoken_words_up_to_its_height(qapp):
    d = Driver("wirtschaft")
    d.press()
    d.run(0.2)
    first = len(d.style._drops)
    d.run(4.0)
    assert first < len(d.style._drops) <= wirtschaft.STACK_MAX


def test_test_tubes_rise_with_the_voice_and_rest_without_signal(qapp):
    d = Driver("chemie")
    d.press()
    d.run(1.5)
    speaking = list(d.style._levels)
    d.run(1.5, amp=0.0)
    assert max(speaking) > max(d.style._levels) + 0.1


@pytest.mark.parametrize("seconds, number, symbol", [(0.4, 1, "H"), (1.2, 1, "H"), (2.5, 2, "He"), (8.3, 8, "O"),
                                                     (118.9, 118, "Og"), (119.2, 1, "H")])
def test_element_tile_names_the_element_of_the_second(seconds, number, symbol):
    assert chemie.element_of_second(seconds) == (number, symbol)


def test_wifi_bars_follow_the_voice(qapp):
    d = Driver("it")
    d.press()
    d.run(1.5, amp=0.0)
    assert d.an.silent
    silent = d.render()
    d.run(1.2, amp=0.9)
    loud = d.render()
    assert _count_color(loud, (66, 54, 36, 20), (0x4F, 0xC1, 0xFF), d.f.px) > _count_color(
        silent, (66, 54, 36, 20), (0x4F, 0xC1, 0xFF), d.f.px)


def _accessory_ink(style, pose: saison.Pose, box: tuple[float, float, float, float], px: float = 2.0) -> int:
    img = QImage(round(W * px), round(H * px), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(px, px)
    style.accessory(p, pose)
    p.end()
    x, y, w, h = (round(v * px) for v in box)
    return _ink(img.copy(x, y, w, h))


def test_scale_beam_tilts_with_the_voice_and_rests_level_when_done():
    assert jura.beam_tilt(saison.Pose("talk", 0.0, 0.6)) == 0.0
    assert abs(jura.beam_tilt(saison.Pose("talk", 1.0, 0.6))) > 8.0
    assert jura.beam_tilt(saison.Pose("talk", 1.0, 0.6, reduced=True)) == 0.0
    assert jura.beam_tilt(saison.Pose("wink", 0.0, 0.6)) == 0.0
    assert jura.beam_tilt(saison.Pose("sad", 0.0, 0.6)) > 10.0


def test_drops_fall_faster_the_louder_the_voice():
    def drops(level: float) -> int:
        falls = [medikamente.dropper(saison.Pose("talk", level, k / 100))[1] for k in range(201)]
        return sum(1 for a, b in zip(falls, falls[1:]) if b < a)
    assert drops(0.9) >= drops(0.1) + 2
    assert medikamente.dropper(saison.Pose("talk", 0.9, 0.4, reduced=True)) == (0.0, -1.0)


def test_dropper_hangs_over_the_bottle_and_the_cap_closes_it_on_error(qapp):
    style = create_style("medikamente")
    bulb, cap = (29, 4, 12, 12), (28, 30, 14, 8)
    assert _accessory_ink(style, saison.Pose("talk", 0.6, 0.4), bulb) > 50
    assert _accessory_ink(style, saison.Pose("sad", 0.0, 0.4), bulb) == 0
    assert _accessory_ink(style, saison.Pose("sad", 0.0, 0.4), cap) > 50


@pytest.mark.parametrize("key", REFINED)
def test_refined_styles_wait_with_an_hourglass_instead_of_sweat(qapp, monkeypatch, key):
    sweat, glass = [], []
    monkeypatch.setattr(cm, "_sweat", lambda *args: sweat.append(args))
    monkeypatch.setattr(fachgebiet, "hourglass", lambda *args: glass.append(args))
    d = Driver(key)
    _think_cycle(d, 7.0)
    d.render()
    assert d.style.sweating(d.t)
    assert glass and not sweat


def test_field_styles_skip_path_booleans_and_powers():
    root = Path(fachgebiet.__file__).parent
    for name in ("fachgebiet.py", "medizin.py", "medikamente.py", "jura.py", "wirtschaft.py", "technik.py", "chemie.py",
                 "it.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert not re.search(r"\.(united|intersected|subtracted|simplified|pointAtPercent|toReversed)\(", source), name
        assert "**" not in source, name
        assert not re.search(r"\b(sum|hypot)\(", source), name
