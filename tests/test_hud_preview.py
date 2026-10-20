# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import sys

import numpy as np
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter

from kira.config import HUD_STYLES
from kira.ui import hud_preview
from kira.ui.hud.base import H, W
from kira.ui.hud_preview import (
    DONE_S,
    LOOP_S,
    POLISH_S,
    POLISHED_TEXT,
    RAW_TEXT,
    RELEASE_S,
    HudPreview,
    PreviewDriver,
    spoken_words,
)

DT = 1 / 60


def _run(driver: PreviewDriver, until: float, start: float = 0.0, probe=None) -> None:
    t = start
    while t < until - 1e-9:
        t += DT
        driver.advance(t)
        if probe is not None:
            probe(t, driver)


def _ink(driver: PreviewDriver) -> int:
    img = QImage(round(W * driver.scale), round(H * driver.scale), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    driver.paint(p, 0, 0)
    p.end()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)
    return int((arr[..., 3] > 0).sum())


@pytest.mark.parametrize("key", HUD_STYLES)
def test_every_style_plays_the_loop_and_starts_over(qapp, key):
    d = PreviewDriver(key)
    d.restart(0.0)
    modes: list[str] = []
    inked: dict[str, int] = {}

    def probe(t, drv):
        mode = drv.style.mode
        if not modes or modes[-1] != mode:
            modes.append(mode)
        if mode in ("rec", "proc") and mode not in inked and t > 1.0 and (mode == "rec" or t > RELEASE_S + 0.5):
            inked[mode] = _ink(drv)

    _run(d, LOOP_S + 1.0, probe=probe)
    assert not d.failed
    assert modes[0] == "rec"
    assert "proc" in modes
    assert modes[-1] == "rec"
    assert modes.count("rec") == 2
    assert inked["rec"] > 2000
    assert inked["proc"] > 2000


def test_loop_follows_the_real_phases(qapp):
    d = PreviewDriver("klartext")
    d.restart(0.0)
    seen = {}

    def probe(t, drv):
        for at in (1.0, RELEASE_S + 0.5, POLISH_S + 0.5, DONE_S + 0.05):
            if at not in seen and t >= at:
                f = drv.frame
                seen[at] = (drv.style.mode, f.polishing, f.raw_text, f.polished_text)

    _run(d, DONE_S + 0.2, probe=probe)
    assert seen[1.0] == ("rec", False, "", "")
    assert seen[RELEASE_S + 0.5] == ("proc", False, "", "")
    assert seen[POLISH_S + 0.5] == ("proc", True, RAW_TEXT, "")
    assert seen[DONE_S + 0.05] == ("done", True, RAW_TEXT, POLISHED_TEXT)


def test_voice_never_reads_as_silence_or_clipping(qapp):
    d = PreviewDriver("phosphor")
    d.restart(0.0)
    flags = set()

    def probe(t, drv):
        if drv.style.mode == "rec" and t > 0.2:
            flags.add(("silent", drv.an.silent))
            flags.add(("clip", drv.an.clip))

    _run(d, RELEASE_S - 0.05, probe=probe)
    assert ("silent", True) not in flags
    assert ("clip", True) not in flags
    assert d.an.level > 0.3


def test_word_fragments_reach_only_styles_with_words_and_skip_repeats(qapp):
    calls: list[list[str]] = []
    d = PreviewDriver("comic")
    d.restart(0.0)
    d.style.feed_words = lambda t, words: calls.append(list(words))
    _run(d, RELEASE_S)
    flat = [w for words in calls for w in words]
    assert flat[:2] == spoken_words(0.7)
    assert all(a != b for a, b in zip(flat, flat[1:]))
    assert "Unterlag…" in flat


def test_word_switch_off_keeps_the_default_blabla(qapp):
    calls: list[list[str]] = []
    d = PreviewDriver("comic", live_words=False)
    d.restart(0.0)
    d.style.feed_words = lambda t, words: calls.append(list(words))
    _run(d, RELEASE_S)
    assert calls == []


def test_style_switch_builds_a_fresh_instance(qapp):
    d = PreviewDriver("comic")
    d.restart(0.0)
    _run(d, 2.0)
    old = d.style
    d.set_style("manga", 2.0)
    _run(d, 2.5, start=2.0)
    assert d.style is not old
    assert d.style.key == "manga"
    assert d.style.mode == "rec"
    assert d.loop_t < 1.0


def test_a_failing_style_switches_the_preview_off_without_raising(qapp, monkeypatch):
    d = PreviewDriver("comic")
    d.restart(0.0)

    def broken(*_args):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(d.style, "paint", broken)
    _run(d, 1.0)
    assert _ink(d) == 0
    assert d.failed
    d.set_style("manga", 1.0)
    assert not d.failed


def test_timer_runs_only_while_the_preview_is_visible(qtbot):
    w = HudPreview("comic")
    qtbot.addWidget(w)
    assert not w.running
    w.show()
    qtbot.waitExposed(w)
    assert w.running
    w.hide()
    assert not w.running


def test_reduced_motion_from_windows_reaches_the_styles(qtbot, monkeypatch):
    monkeypatch.setattr(hud_preview, "animations_off", lambda: True)
    w = HudPreview("comic")
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    w._timer.stop()
    d = w.driver
    d.restart(0.0)
    _run(d, 0.5)
    assert d.frame.reduced


def test_preview_keeps_the_hud_scale_but_never_grows_past_the_tile(qtbot):
    small = HudPreview("comic", scale=1.0)
    large = HudPreview("comic", scale=2.5)
    qtbot.addWidget(small)
    qtbot.addWidget(large)
    assert small.driver.scale == 1.0
    assert large.driver.scale == 1.5
    assert small.height() == large.height()


def test_a_style_that_cannot_be_built_leaves_the_preview_empty(qapp, monkeypatch):
    def broken(key):
        raise ImportError("kaputt")

    d = PreviewDriver("comic")
    monkeypatch.setattr(hud_preview, "create_style", broken)
    d.set_style("manga", 0.0)
    assert d.failed and d.key == "manga"
    _run(d, 1.0)
    assert _ink(d) == 0
    fresh = PreviewDriver("phosphor")
    assert fresh.failed and fresh.style is None
    _run(fresh, 0.5)
