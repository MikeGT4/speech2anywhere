# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import re
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)

from PyQt6.QtGui import QPainter, QPainterPath

from kira import texte
from kira.config import HUD_STYLES
from kira.ui.hud import base as hud_base
from tests.test_hud_styles import Driver

LATIN = re.compile(r"[A-Za-zÄÖÜäöüß]")
NOISE = "0123456789#%&*+=<>/"
SAME_IN_BOTH = frozenset({
    "RING!", "DING!", "KIAI!", "HA!", "hm", "ho!", "TRIG", "XY", "LOCK", "3 ms/div", "5 kHz", "−∞ dBFS",
})
ENGLISH_BY_DESIGN = frozenset({"klassisch"})
ERROR_TEXT = "Mikrofon nicht gefunden.|Gerät prüfen, dann erneut drücken."


class Sparse(Driver):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self._frames = 0

    def render(self):
        self._frames += 1
        if self._frames % 5 == 0:
            return super().render()
        return None


def _scenes(key: str) -> tuple:
    style = Driver(key).style
    module = sys.modules[type(style).__module__]
    return getattr(style, "SCENES", None) or getattr(module, "SCENES", None) or (None,)


def _play(key: str) -> None:
    for scene in _scenes(key):
        d = Sparse(key)
        d.press()
        if scene is not None:
            d.style.scene = scene
        d.run(1.3)
        d.style.release(d.t, d.f)
        d.run(0.5)
        d.f.polishing = True
        d.run(4.6)
        d.style.done(d.t, d.f)
        d.run(0.6)
    d = Sparse(key)
    d.press()
    d.run(3.5, amp=0.0)
    d.style.abort(d.t)
    d = Sparse(key)
    d.press()
    d.run(1.5, amp=3.0)
    d.style.release(d.t, d.f)
    d.style.error(d.t, texte.tr(ERROR_TEXT), d.f)
    d.run(0.8)
    d = Sparse(key)
    d.press()
    d.style.release(d.t, d.f)
    d.style.error(d.t, "", d.f)
    d.run(0.8)


def _drawn(key: str, language: str, monkeypatch) -> set[str]:
    seen: set[str] = set()
    draw, add = QPainter.drawText, QPainterPath.addText

    def record_draw(self, *args):
        seen.update(arg for arg in args if isinstance(arg, str))
        return draw(self, *args)

    def record_add(self, *args):
        seen.update(arg for arg in args if isinstance(arg, str))
        return add(self, *args)

    with monkeypatch.context() as patch:
        patch.setattr(QPainter, "drawText", record_draw)
        patch.setattr(QPainterPath, "addText", record_add)
        patch.setattr(hud_base, "GLYPHS", NOISE)
        module = sys.modules[type(Driver(key).style).__module__]
        if hasattr(module, "GLYPHS"):
            patch.setattr(module, "GLYPHS", NOISE)
        texte.set_language(language)
        try:
            _play(key)
        finally:
            texte.set_language("de")
    return {text for text in seen if len(LATIN.findall(text)) >= 2}


@pytest.mark.parametrize("key", [k for k in HUD_STYLES if k not in ENGLISH_BY_DESIGN])
def test_indicator_draws_no_german_text_in_english(qapp, monkeypatch, key):
    german = _drawn(key, "de", monkeypatch)
    english = _drawn(key, "en", monkeypatch)
    assert german, key
    assert sorted((german & english) - SAME_IN_BOTH) == []


def test_time_and_level_use_a_point_in_english():
    texte.set_language("en")
    try:
        assert hud_base.fmt_time(61.2) == "01:01.2"
        assert hud_base.fmt_db(-6.25).endswith(".2 dBFS") or hud_base.fmt_db(-6.25).endswith(".3 dBFS")
        assert hud_base.fmt_db(0.0) == "0.0 dBFS"
    finally:
        texte.set_language("de")
    assert hud_base.fmt_time(61.2) == "01:01,2"
    assert hud_base.fmt_db(0.0) == "0,0 dBFS"


def test_character_count_knows_one_from_many():
    from kira.ui.hud.klartext import character_count
    assert character_count(1) == "1 ZEICHEN"
    assert character_count(27) == "27 ZEICHEN"
    texte.set_language("en")
    try:
        assert character_count(1) == "1 CHARACTER"
        assert character_count(0) == "0 CHARACTERS"
        assert character_count(27) == "27 CHARACTERS"
    finally:
        texte.set_language("de")
