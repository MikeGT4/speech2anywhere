from __future__ import annotations
import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from kira.app import State
from kira.ui import tray_win
from kira.ui.tray_win import (
    ICON_SIZE,
    _build_icon,
    _load_or_generate_icon,
)


@pytest.fixture(autouse=True)
def _reset_caches():
    tray_win._LOGO_CACHE = None
    tray_win._LOGO_CACHE_FAILED = False
    tray_win._ICON_CACHE.clear()
    yield
    tray_win._LOGO_CACHE = None
    tray_win._LOGO_CACHE_FAILED = False
    tray_win._ICON_CACHE.clear()


def _bottom_right_dot_pixel(img):
    offset = ICON_SIZE // 10
    return img.getpixel((ICON_SIZE - offset, ICON_SIZE - offset))


def _center_pixel(img):
    return img.getpixel((ICON_SIZE // 2, ICON_SIZE // 2))


def test_idle_icon_has_yellow_background_no_overlay():
    img = _load_or_generate_icon(State.IDLE)
    assert img.size == (ICON_SIZE, ICON_SIZE)
    r, g, b, a = _bottom_right_dot_pixel(img)
    assert a == 255, "BG must be opaque inside the rounded square"
    assert r > 200 and g > 150 and b < 80, (
        f"expected yellow-ish BG, got RGBA=({r},{g},{b},{a})"
    )


def _tile_pixel(img):
    return img.getpixel((3, ICON_SIZE // 2))


MOUTH_TOP = (ICON_SIZE // 2, 31)


def test_recording_icon_opens_the_mouth():
    idle = _load_or_generate_icon(State.IDLE)
    img = _load_or_generate_icon(State.RECORDING)
    assert _tile_pixel(img) == _tile_pixel(idle)
    assert min(idle.getpixel(MOUTH_TOP)[:3]) > 180, "über dem lachenden Mund ist die Blase weiß"
    assert max(img.getpixel(MOUTH_TOP)[:3]) < 90, "der offene Mund reicht höher"
    assert _bottom_right_dot_pixel(img) == _bottom_right_dot_pixel(idle), "kein Punkt mehr"


def test_recording_alternates_two_frames_until_the_state_changes(monkeypatch):
    import time

    monkeypatch.setattr(tray_win, "PLAPPER_INTERVAL_S", 0.01)
    shown = []

    class FakeIcon:
        menu = None

        @property
        def icon(self):
            return shown[-1] if shown else None

        @icon.setter
        def icon(self, image):
            shown.append(image)

    tray = tray_win.KiraTray(on_quit=lambda: None)
    tray._icon = FakeIcon()
    tray.update_state(State.RECORDING)
    time.sleep(0.15)
    tray.update_state(State.IDLE)
    idle = _load_or_generate_icon(State.IDLE)
    recording = _load_or_generate_icon(State.RECORDING)
    assert shown[0] is recording
    assert {id(image) for image in shown} == {id(idle), id(recording)}
    assert len(shown) >= 4, "mehrere Wechsel während der Aufnahme"
    count = len(shown)
    time.sleep(0.05)
    assert len(shown) == count, "nach dem Zustandswechsel steht das Bild"
    assert shown[-1] is idle


def test_error_icon_has_orange_overlay_dot():
    img = _load_or_generate_icon(State.ERROR)
    r, g, b, _ = _bottom_right_dot_pixel(img)
    assert r > 200 and 40 < g < 120 and b < 50, (
        f"expected red-orange overlay dot, got RGB=({r},{g},{b})"
    )


def test_pipeline_states_have_no_overlay():
    idle = _load_or_generate_icon(State.IDLE)
    for s in (State.TRANSCRIBING, State.STYLING, State.INJECTING):
        img = _load_or_generate_icon(s)
        assert _bottom_right_dot_pixel(img) == _bottom_right_dot_pixel(idle)
        assert _center_pixel(img) == _center_pixel(idle)


def test_load_or_generate_icon_is_memoized_per_state():
    first = _load_or_generate_icon(State.IDLE)
    second = _load_or_generate_icon(State.IDLE)
    assert first is second
    other = _load_or_generate_icon(State.RECORDING)
    assert other is not first


def test_logo_is_loaded_only_once_across_states(monkeypatch):
    open_calls = []
    real_open = tray_win.Image.open

    def _counting_open(*args, **kwargs):
        open_calls.append(args[0] if args else None)
        return real_open(*args, **kwargs)

    monkeypatch.setattr("kira.ui.tray_win.Image.open", _counting_open)
    _load_or_generate_icon(State.IDLE)
    _load_or_generate_icon(State.RECORDING)
    _load_or_generate_icon(State.ERROR)
    _load_or_generate_icon(State.STYLING)
    assert len(open_calls) <= 1, (
        f"Expected logo loaded at most once, got {len(open_calls)} Image.open calls"
    )


def test_build_icon_bypasses_cache():
    a = _build_icon(State.IDLE)
    b = _build_icon(State.IDLE)
    assert a is not b
    assert _center_pixel(a) == _center_pixel(b)


def test_tray_icon_loads_each_image_only_once(monkeypatch):
    from kira.ui import tray_win
    loads = []
    original = tray_win._PystrayWin32Icon._assert_icon_handle

    def counting(self):
        loads.append(self.icon)
        original(self)

    monkeypatch.setattr(tray_win._PystrayWin32Icon, "_assert_icon_handle", counting)
    idle = tray_win._load_or_generate_icon(tray_win.State.IDLE)
    talking = tray_win._load_or_generate_icon(tray_win.State.RECORDING)
    icon = tray_win._KiraPystrayIcon("probe", icon=idle)
    handles = []
    for image in (idle, talking, idle, talking, idle):
        icon._icon = image
        icon._release_icon()
        icon._assert_icon_handle()
        handles.append(icon._icon_handle)
    assert len(loads) == 2
    assert handles[0] == handles[2] == handles[4]
    assert handles[1] == handles[3]
    assert handles[0] != handles[1]
