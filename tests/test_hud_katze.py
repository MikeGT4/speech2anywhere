# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math
import random
import re
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetricsF, QImage, QPainter

from kira import texte
from kira._resources import assets_dir
from kira.ui import _comic
from kira.ui.hud import comic as cm, create_style, katze, saison
from kira.ui.hud.base import H, W, Frame
from tests.test_hud_fachgebiete import ERROR_TEXT, FIELD_KINDS, NARROW_TEXT_W, TEXT_AIR, _changed, _field_run, _grown
from tests.test_hud_saison import EDGE_SIZES, _short_of_air
from tests.test_hud_styles import DT, Driver, _corner_ink, _count_color, _ink, _think_cycle

KEY = "katze"
SCENES = katze.Katze.SCENES
EARS = (2, 8, 66, 15)
TAIL = (58, 44, 12, 30)
CLOUD_BOX = (94, 3, 158, 56)
PROPS = [
    ("wolle", (100, 22, 24, 24), (0xE5, 0x48, 0x4D)),
    ("putzen", (106, 22, 26, 22), (0x5A, 0x3E, 0x2B)),
    ("gaehnen", (110, 20, 22, 22), (0xF2, 0xC2, 0x30)),
    ("schnurren", (100, 12, 38, 38), (0xF2, 0xC2, 0x30)),
    ("kopf_schief", (112, 14, 18, 32), (0xFF, 0xC4, 0x00)),
]


class Quiet(Driver):
    def render(self):
        return None


def _talking(seed: int, seconds: float, reduced: bool = False) -> tuple[Quiet, list[tuple[str, float]]]:
    d = Quiet(KEY, reduced=reduced)
    d.style._rng = random.Random(seed)
    d.press()
    started: list[tuple[str, float]] = []
    last = None
    for _ in range(int(round(seconds / DT))):
        d.run(DT)
        if d.style._motion is not None and d.style._motion is not last:
            started.append(d.style._motion)
        last = d.style._motion
    return d, started


def test_scene_and_clock_are_chosen_by_chance_per_dictation(qapp):
    d = Quiet(KEY)
    d.style._rng = random.Random(7)
    scenes, clocks = set(), set()
    for _ in range(40):
        d.press()
        scenes.add(d.style.scene)
        clocks.add(d.style.clock)
        d.style.abort(d.t)
        d.run(0.2, amp=0.0)
    assert scenes == set(SCENES)
    assert clocks == {"katzenuhr"}


def test_scene_changes_every_five_seconds_but_never_with_animations_off(qapp):
    d = Quiet(KEY)
    _think_cycle(d, 4.9, scene=SCENES[0])
    assert d.style.scene_at(d.t, d.f)[0] == SCENES[0]
    for nxt in SCENES[1:] + SCENES[:1]:
        d.run(5.0 if nxt != SCENES[1] else 0.2, amp=0.0)
        assert d.style.scene_at(d.t, d.f)[0] == nxt
    still = Quiet(KEY, reduced=True)
    _think_cycle(still, 16.0, scene=SCENES[2])
    assert still.style.scene_at(still.t, still.f)[0] == SCENES[2]


@pytest.mark.parametrize("scene", SCENES)
def test_scene_stays_when_polish_begins(qapp, scene):
    d = Quiet(KEY)
    _think_cycle(d, 0.8, scene=scene)
    d.f.polishing = True
    d.f.polish_t = d.t
    d.run(0.3, amp=0.0)
    assert d.style.scene_at(d.t, d.f)[0] == scene


@pytest.mark.parametrize("scene", SCENES)
@pytest.mark.parametrize("reduced", [False, True])
def test_long_wait_keeps_drawing_and_sweats(qapp, scene, reduced):
    d = Quiet(KEY, reduced=reduced)
    _think_cycle(d, 7.0, 7.0, scene)
    assert d.style.visible
    assert d.style.sweating(d.t)
    assert _ink(Driver.render(d)) > 2000


@pytest.mark.parametrize("scene", SCENES)
@pytest.mark.parametrize("polish", [0.0, 0.4])
@pytest.mark.parametrize("at", [1.0, 2.5, 4.4])
def test_thinking_moves_in_the_cloud_and_on_the_tile_unless_reduced(qapp, scene, polish, at):
    for reduced in (False, True):
        d = Quiet(KEY, reduced=reduced)
        _think_cycle(d, at, polish, scene)
        first = Driver.render(d)
        d.t += 0.2
        second = Driver.render(d)
        x, y, w, h = (round(v * d.f.px) for v in CLOUD_BOX)
        assert (first.copy(x, y, w, h) != second.copy(x, y, w, h)) is not reduced
        assert (first != second) is not reduced


@pytest.mark.parametrize("scene, box, rgb", PROPS)
def test_every_scene_shows_its_prop_in_the_cloud(qapp, scene, box, rgb):
    d = Quiet(KEY, reduced=True)
    _think_cycle(d, 0.8, scene=scene)
    assert _count_color(Driver.render(d), box, rgb, d.f.px, tol=16) > 10


@pytest.mark.parametrize("language", ["de", "en"])
def test_titles_and_captions_fit_the_cloud(qapp, language):
    texte.set_language(language)
    try:
        title = QFontMetricsF(_comic.baloo(800, 15))
        caption = QFontMetricsF(_comic.baloo(600, 11))
        room = cm.CLOUD.right() - 8 - katze.Katze.TITLE_X
        assert max(title.horizontalAdvance(texte.tr(word)) for word in ("Erkennen", "Politur")) <= room
        for before, after, _at in katze.Katze.CAPTIONS.values():
            assert caption.horizontalAdvance(texte.tr(before)) <= room, before
            assert caption.horizontalAdvance(texte.tr(after)) <= room, after
    finally:
        texte.set_language("de")


@pytest.mark.parametrize("reduced", [False, True])
@pytest.mark.parametrize("shift", [0.0, 59.8, 60.2, 125.4])
def test_clock_draws_in_the_corner_also_at_the_full_minute(qapp, reduced, shift):
    d = Quiet(KEY, reduced=reduced)
    d.press()
    d.style.t0 -= shift
    d.run(0.4)
    assert d.style.mode == "rec"
    assert _corner_ink(Driver.render(d), d.f.px) > 400


@pytest.mark.parametrize("language", ["de", "en"])
def test_done_word_fits_the_burst_uncut(qapp, language):
    texte.set_language(language)
    try:
        word = texte.tr(katze.Katze.ZACK_WORD)
        px = saison.zack_px(word)
        assert px >= 14
        assert QFontMetricsF(_comic.baloo(800, px)).horizontalAdvance(word) <= saison.ZACK_TEXT_W
    finally:
        texte.set_language("de")


def test_bla_first_then_spoken_fragments_in_the_cat_colors(qapp):
    d = Quiet(KEY)
    d.press()
    d.run(0.5)
    style = d.style
    assert style._words and {w.text for w in style._words} <= set(style.WORDS)
    assert all(w.fill.name() == saison.YELLOW.name() for w in style._words)
    style.feed_words(d.t, ["Unterlagen", "Freitag"])
    d.run(0.8)
    spoken = [w for w in style._words if w.text in ("Unterlagen", "Freitag")]
    assert {w.text for w in spoken} == {"Unterlagen", "Freitag"}
    assert {w.fill.name() for w in spoken} <= {c.name() for c in style.WORD_FILLS}


def test_long_fragments_shrink_to_fit_the_lane(qapp):
    d = Quiet(KEY)
    d.press()
    d.style.feed_words(d.t, ["Donaudampfschifffahrt"])
    d.run(0.5)
    word = next(w for w in d.style._words if w.text.startswith("Donau"))
    assert word.width <= cm.MAX_WORD_W + 0.5


def test_reduced_motion_keeps_the_dictation_still(qapp):
    d = Quiet(KEY, reduced=True)
    d.press()
    d.run(1.2)
    first = Driver.render(d)
    d.t += 0.2
    assert Driver.render(d) == first
    moving = Quiet(KEY)
    moving.press()
    moving.run(1.2)
    first = Driver.render(moving)
    moving.t += 0.2
    assert Driver.render(moving) != first


@pytest.mark.parametrize("box", [EARS, TAIL])
def test_ears_and_tail_stay_still_with_animations_off_while_the_voice_changes(qapp, box):
    d = Quiet(KEY, reduced=True)
    d.press()
    d.run(1.2, amp=0.2)
    x, y, w, h = (round(v * d.f.px) for v in box)
    first = Driver.render(d).copy(x, y, w, h)
    for amp in (0.9, 0.0, 0.6):
        d.run(0.4, amp=amp)
        assert Driver.render(d).copy(x, y, w, h) == first


def test_mouth_follows_the_voice(qapp):
    quiet = katze.Katze().cat(saison.Pose("talk", 0.1, 5.0))
    loud = katze.Katze().cat(saison.Pose("talk", 0.9, 5.0))
    assert quiet.mouth == loud.mouth == "talk"
    assert katze.face_key(loud)[5] > katze.face_key(quiet)[5]


def test_random_motions_play_while_speaking_and_all_of_them_come_up(qapp):
    seen = set()
    for seed in range(4):
        _d, started = _talking(seed, 30.0)
        seen |= {name for name, _t0 in started}
    assert seen == set(katze.REC_MOTIONS)


def test_paw_swipes_only_when_a_word_has_just_spawned(qapp):
    swipes = 0
    for seed in range(4):
        d = Quiet(KEY)
        d.style._rng = random.Random(seed)
        d.press()
        last = None
        for _ in range(int(round(30.0 / DT))):
            d.run(DT)
            motion = d.style._motion
            if motion is not None and motion is not last and motion[0] == "pfotenhieb":
                swipes += 1
                assert any(abs(w.born - motion[1]) < 1e-9 for w in d.style._words)
            last = motion
    assert swipes


def test_no_motions_and_no_swipes_with_animations_off(qapp):
    d, started = _talking(1, 20.0, reduced=True)
    assert started == []
    assert d.style._motion is None


def test_each_dictation_starts_without_a_motion(qapp):
    d, started = _talking(2, 12.0)
    assert started
    d.style._motion = ("schwanz", d.t)
    d.style._pending = "pfotenhieb"
    d.style.abort(d.t)
    d.run(0.3, amp=0.0)
    d.press()
    assert d.style._motion is None
    assert d.style._pending is None
    assert d.style._next_motion > d.t


def test_motions_only_move_while_they_last(qapp):
    style = katze.Katze()
    style._motion = ("schwanz", 10.0)
    swinging = style.cat(saison.Pose("talk", 0.5, 10.25))
    after = style.cat(saison.Pose("talk", 0.5, 12.5))
    assert abs(swinging.tail) > 20
    assert after.tail == 0.0


def test_faces_of_the_moods(qapp):
    style = katze.Katze()
    style.end_t = 20.0
    shout = style.cat(saison.Pose("shout", 1.0, 3.0))
    assert (shout.eye_l, shout.eye_r, shout.mouth) == ("squint", "squint", "hiss")
    assert shout.ear_l < -20 < 20 < shout.ear_r
    sad = style.cat(saison.Pose("sad", 0.0, 3.0))
    assert sad.mouth == "sad" and sad.ear_l < -15 < 15 < sad.ear_r
    wink = style.cat(saison.Pose("wink", 0.0, 20.5))
    assert (wink.eye_l, wink.eye_r, wink.mouth) == ("open", "shut", "laugh")
    assert abs(wink.bell) > 5
    assert style.cat(saison.Pose("wink", 0.0, 0.0, reduced=True)).bell == 0.0
    puzzled = style.cat(saison.Pose("think", 0.0, 3.0))
    assert puzzled.question and puzzled.tilt < -10
    still = style.cat(saison.Pose("think", 0.0, 0.0, reduced=True))
    assert still == katze.PUZZLED


def test_silence_tilts_the_head_and_shows_a_question_mark(qapp, monkeypatch):
    d = Quiet(KEY, reduced=True)
    d.press()
    d.run(1.6, amp=0.0)
    assert d.an.silent
    x, y, w, h = (round(v * d.f.px) for v in (50, 12, 14, 16))
    asking = Driver.render(d).copy(x, y, w, h)
    monkeypatch.setattr(katze, "PUZZLED", replace(katze.PUZZLED, question=False))
    assert Driver.render(d).copy(x, y, w, h) != asking
    monkeypatch.setattr(katze, "PUZZLED", replace(katze.PUZZLED, tilt=0.0))
    assert Driver.render(d).copy(x, y, w, h) != asking


@pytest.mark.parametrize("reduced", [False, True])
def test_every_frame_stays_in_the_window_and_the_decor_keeps_its_air(qapp, reduced):
    style = create_style(KEY)
    poses, decors, outside = _field_run(KEY, reduced)
    assert {pose.kind for pose in poses} == FIELD_KINDS
    assert decors
    assert not outside, outside[:6]
    tight = []
    for t, still, k in decors:
        frame = Frame(reduced=still)
        tight += [("decor", round(k, 3), miss) for miss in _short_of_air(lambda p: style.zack_decor(p, t, frame, k))]
    assert not tight, tight[:6]


def test_done_decor_keeps_its_air_at_full_swing(qapp):
    style = create_style(KEY)
    tight = []
    for still in (False, True):
        frame = Frame(reduced=still)
        for i in range(241):
            k, t = i / 240, 100.0 + i / 97
            tight += [(still, round(k, 3), miss)
                      for miss in _short_of_air(lambda p: style.zack_decor(p, t, frame, k), EDGE_SIZES)]
    assert not tight, tight[:6]


@pytest.mark.parametrize("language", ["de", "en"])
def test_error_text_in_four_lines_keeps_its_air_to_the_decor(qapp, monkeypatch, language):
    monkeypatch.setattr(cm, "HINT_TEXT_W", NARROW_TEXT_W)
    texte.set_language(language)
    try:
        message = texte.tr(ERROR_TEXT)
        first, _, second = message.partition("|")
        assert len(cm.error_lines(first, second)) == 4
        d = Driver(KEY, px=4.0)
        d.style.error(d.t, message, d.f)
        full = d.render()
        monkeypatch.setattr(d.style, "error_decor", lambda *_args: None)
        bare = d.render()
        monkeypatch.setattr(cm, "error_lines", lambda *_args: [])
        empty = d.render()
    finally:
        texte.set_language("de")
    decor, words = _changed(full, bare), _changed(bare, empty)
    assert decor.any() and words.any()
    clash = _grown(decor, math.ceil(TEXT_AIR * d.f.px)) & words
    assert not clash.any(), int(clash.sum())


def test_face_cache_stays_bounded_after_long_use(qapp):
    katze._FACES.clear()
    for seed in range(3):
        _talking(seed, 25.0)
    for scene in SCENES:
        d = Quiet(KEY)
        _think_cycle(d, 0.2, scene=scene)
        for _ in range(int(round(5.0 / DT))):
            d.run(DT, amp=0.0)
            Driver.render(d)
        d.style.done(d.t, d.f)
        d.run(0.6, amp=0.0)
        Driver.render(d)
    d, _started = _talking(5, 30.0)
    for _ in range(int(round(30.0 / DT))):
        d.run(DT)
        Driver.render(d)
    assert 0 < len(katze._FACES) <= katze.FACE_CACHE
    for i in range(katze.FACE_CACHE + 10):
        katze._face(("open", "open", 5, (0, 6), "talk", i, 0))
    assert len(katze._FACES) == katze.FACE_CACHE


def test_frame_time_stays_in_the_range_of_the_other_styles(qapp):
    px = 1.5
    img = QImage(round(W * px), round(H * px), QImage.Format.Format_ARGB32_Premultiplied)

    def cycle() -> list[float]:
        d = Quiet(KEY, px=px)
        d.style._rng = random.Random(11)
        times: list[float] = []

        def frames(seconds: float, amp: float) -> None:
            for _ in range(int(round(seconds / DT))):
                d.run(DT, amp=amp)
                if not d.style.visible:
                    continue
                img.fill(Qt.GlobalColor.transparent)
                p = QPainter(img)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.scale(px, px)
                start = time.perf_counter()
                d.style.paint(p, d.t, d.f, d.tap, d.an)
                times.append((time.perf_counter() - start) * 1000.0)
                p.end()

        d.press()
        d.style.feed_words(d.t, ["Unterlagen", "Freitag", "schicken"])
        frames(6.0, 0.5)
        d.style.release(d.t, d.f)
        frames(12.0, 0.0)
        d.style.done(d.t, d.f)
        frames(0.6, 0.0)
        return times

    cycle()
    assert statistics.median(cycle()) < 4.0


def test_cat_ships_its_own_sound_variants():
    folder = assets_dir() / "sounds" / KEY
    names = sorted(path.name for path in folder.glob("*.wav"))
    assert names == ["fehler-2.wav", "fehler-3.wav", "fehler.wav", "fertig-2.wav", "fertig-3.wav", "fertig-4.wav",
                     "fertig.wav", "start-2.wav", "start-3.wav", "start.wav", "stopp-2.wav", "stopp-3.wav", "stopp.wav"]


def test_host_passes_spoken_words_to_the_cat(qtbot, tmp_path):
    from kira.ui.hud_qt import PopupHUD
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"ui:\n  hud_style: {KEY}\n", encoding="utf-8")
    hud = PopupHUD(config_path=cfg, state_dir=tmp_path)
    qtbot.addWidget(hud)
    assert hud.style_key == KEY
    assert hud.wants_live_words
    hud.set_phase("rec")
    hud.push_words(["Hallo"])
    qtbot.waitUntil(lambda: "Hallo" in hud._style._queue, timeout=1000)
    hud.set_phase("idle")
    qtbot.waitUntil(lambda: not hud.isVisible(), timeout=2000)


def test_preview_feeds_fragments_to_the_cat(qapp):
    from kira.ui.hud_preview import RELEASE_S, PreviewDriver
    calls: list[list[str]] = []
    d = PreviewDriver(KEY)
    d.restart(0.0)
    d.style.feed_words = lambda t, words: calls.append(list(words))
    t = 0.0
    while t < RELEASE_S:
        t += DT
        d.advance(t)
    assert not d.failed
    assert calls


def test_cat_style_skips_path_booleans_and_powers():
    source = (Path(katze.__file__)).read_text(encoding="utf-8")
    assert not re.search(r"\.(united|intersected|subtracted|simplified|pointAtPercent|toReversed)\(", source)
    assert "**" not in source
    assert not re.search(r"\b(sum|hypot)\(", source)
