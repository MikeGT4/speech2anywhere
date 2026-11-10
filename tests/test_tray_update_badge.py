# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys
import time

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from PIL import ImageChops
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import QWidgetAction

from kira import texte
from kira.app import State
from kira.ui import tray_win, update_badge
from kira.ui.tray_win import ICON_SIZE, KiraTray, _build_icon, _load_or_generate_icon

WORKING = (State.IDLE, State.RECORDING, State.TRANSCRIBING, State.STYLING, State.INJECTING)
CORNER = round(ICON_SIZE * (1 - update_badge.CORNER_SHARE))
CENTRE = round(ICON_SIZE - ICON_SIZE * update_badge.CORNER_SHARE / 2)
TOOLTIP = "Speech2Anywhere: Update auf v0.6.3 bereit"


class FakeIcon:
    def __init__(self):
        self.shown = []
        self.title = "Speech2Anywhere"
        self.menu = None

    @property
    def icon(self):
        return self.shown[-1] if self.shown else None

    @icon.setter
    def icon(self, image):
        self.shown.append(image)


@pytest.fixture
def english():
    texte.set_language("en")
    yield
    texte.set_language("de")


@pytest.fixture
def tray_with_icon():
    tray = KiraTray(on_quit=lambda: None)
    fake = FakeIcon()
    tray._icon = fake
    return tray, fake


@pytest.fixture
def started_tray(monkeypatch):
    monkeypatch.setattr(tray_win._KiraPystrayIcon, "run", lambda self: None)
    tray = KiraTray(on_quit=lambda: None)
    yield tray
    icon = tray._icon
    if icon is not None:
        icon._unregister_class(icon._atom)


def _near(pixel, colour, tolerance=30):
    return pixel[3] > 250 and all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], colour[:3]))


def _near_colour(colour, hex_rgb, tolerance=20):
    want = QColor(hex_rgb)
    return all(
        abs(a - b) <= tolerance
        for a, b in ((colour.red(), want.red()), (colour.green(), want.green()), (colour.blue(), want.blue()))
    )


@pytest.mark.parametrize("state", WORKING)
def test_badge_sits_in_the_bottom_right_corner_in_every_working_state(state):
    plain = _load_or_generate_icon(state)
    badged = _load_or_generate_icon(state, True)
    assert badged is not plain
    left, top, right, bottom = ImageChops.difference(plain, badged).getbbox(alpha_only=False)
    assert left >= CORNER - 3 and top >= CORNER - 3
    assert right >= ICON_SIZE - 2 and bottom >= ICON_SIZE - 2
    assert _near(badged.getpixel((CENTRE, CENTRE)), update_badge.WHITE, 12)
    assert _near(badged.getpixel((CENTRE + 6, CENTRE + 4)), update_badge.GREEN)
    assert not _near(plain.getpixel((CENTRE + 6, CENTRE + 4)), update_badge.GREEN)


def test_error_dot_has_priority_over_the_badge():
    plain = _load_or_generate_icon(State.ERROR)
    assert _load_or_generate_icon(State.ERROR, True).tobytes() == plain.tobytes()
    assert _build_icon(State.ERROR, True).tobytes() == _build_icon(State.ERROR).tobytes()
    assert _near(plain.getpixel((ICON_SIZE - ICON_SIZE // 10,) * 2), (255, 80, 0), 40)


def test_icons_are_memoized_per_state_and_update_flag():
    plain = _load_or_generate_icon(State.IDLE)
    badged = _load_or_generate_icon(State.IDLE, True)
    assert plain is not badged
    assert _load_or_generate_icon(State.IDLE) is plain
    assert _load_or_generate_icon(State.IDLE, True) is badged


def test_tooltip_names_the_version_and_returns_to_the_plain_title(tray_with_icon):
    tray, fake = tray_with_icon
    tray.set_update_available("0.6.3")
    assert fake.title == TOOLTIP
    assert fake.icon is _load_or_generate_icon(State.IDLE, True)
    tray.set_update_available(None)
    assert fake.title == "Speech2Anywhere"
    assert fake.icon is _load_or_generate_icon(State.IDLE)


def test_tooltip_follows_the_language(tray_with_icon, english):
    tray, fake = tray_with_icon
    tray.set_update_available("0.6.3")
    assert fake.title == "Speech2Anywhere: Update to v0.6.3 ready"


def test_unchanged_version_pushes_nothing_new(tray_with_icon):
    tray, fake = tray_with_icon
    tray.set_update_available("0.6.3")
    pushed = len(fake.shown)
    tray.set_update_available("0.6.3")
    assert len(fake.shown) == pushed


def test_update_state_keeps_the_badge(tray_with_icon):
    tray, fake = tray_with_icon
    tray.set_update_available("0.6.3")
    for state in (State.TRANSCRIBING, State.STYLING, State.INJECTING, State.IDLE):
        tray.update_state(state)
        assert fake.icon is _load_or_generate_icon(state, True)
    tray.update_state(State.ERROR)
    assert fake.icon.tobytes() == _load_or_generate_icon(State.ERROR).tobytes()
    tray.update_state(State.IDLE)
    assert fake.icon is _load_or_generate_icon(State.IDLE, True)


def test_update_arriving_during_an_error_keeps_the_error_dot(tray_with_icon):
    tray, fake = tray_with_icon
    tray.update_state(State.ERROR)
    tray.set_update_available("0.6.3")
    assert fake.icon.tobytes() == _load_or_generate_icon(State.ERROR).tobytes()
    assert fake.title == TOOLTIP


def test_recording_with_update_alternates_the_two_badged_frames(monkeypatch, tray_with_icon):
    monkeypatch.setattr(tray_win, "PLAPPER_INTERVAL_S", 0.01)
    tray, fake = tray_with_icon
    tray._update_available = "0.6.3"
    tray.update_state(State.RECORDING)
    time.sleep(0.15)
    tray.update_state(State.IDLE)
    idle = _load_or_generate_icon(State.IDLE, True)
    recording = _load_or_generate_icon(State.RECORDING, True)
    assert fake.shown[0] is recording
    assert {id(image) for image in fake.shown} == {id(idle), id(recording)}
    assert fake.shown[-1] is idle


def test_update_arriving_during_recording_switches_the_frames(monkeypatch, tray_with_icon):
    monkeypatch.setattr(tray_win, "PLAPPER_INTERVAL_S", 0.01)
    tray, fake = tray_with_icon
    tray.update_state(State.RECORDING)
    time.sleep(0.05)
    tray.set_update_available("0.6.3")
    time.sleep(0.1)
    tray.update_state(State.IDLE)
    badged = {id(_load_or_generate_icon(State.IDLE, True)), id(_load_or_generate_icon(State.RECORDING, True))}
    first = next(i for i, image in enumerate(fake.shown) if id(image) in badged)
    assert first > 0
    assert all(id(image) in badged for image in fake.shown[first:])
    assert fake.shown[-1] is _load_or_generate_icon(State.IDLE, True)


@pytest.mark.parametrize("version, tooltip, badged", [
    ("0.6.3", TOOLTIP, True),
    (None, "Speech2Anywhere", False),
])
def test_icon_created_after_the_version_is_known_starts_with_the_right_picture(started_tray, version, tooltip, badged):
    started_tray.set_update_available(version)
    started_tray.run()
    assert started_tray._icon.title == tooltip
    assert started_tray._icon.icon is _load_or_generate_icon(State.IDLE, badged)


def test_menu_icon_kind_separates_the_install_entry_from_the_search_entry(english):
    assert tray_win._menu_icon_kind("Install update to v0.6.3…") == "update"
    assert tray_win._menu_icon_kind("Check for updates…") == "retry"
    texte.set_language("de")
    assert tray_win._menu_icon_kind("Update auf v0.6.3 installieren…") == "update"
    assert tray_win._menu_icon_kind("Updates suchen…") == "retry"


def test_native_menu_lists_the_install_entry_right_under_the_status(tray_with_icon):
    tray, _fake = tray_with_icon
    tray.set_update_available("0.6.3")
    items = tray._build_menu().items
    assert [str(item.text) for item in items[:4]] == [
        "Speech2Anywhere", "Bereit", "- - - -", "Update auf v0.6.3 installieren…",
    ]


def test_comic_menu_puts_the_install_entry_first_and_only_it_wears_the_badge(qtbot):
    from kira.ui import _comic as comic
    tray = KiraTray(on_quit=lambda: None)
    tray.set_update_available("0.6.3")
    menu = tray._comic_menu()
    qtbot.addWidget(menu)
    actions = menu.actions()
    assert isinstance(actions[0], QWidgetAction) and isinstance(actions[1], QWidgetAction)
    assert actions[2].isSeparator()
    assert actions[3].text() == "Update auf v0.6.3 installieren…"
    badge = comic.menu_icon("update").pixmap(QSize(28, 28), QIcon.Mode.Normal).toImage()
    assert actions[3].icon().pixmap(QSize(28, 28), QIcon.Mode.Normal).toImage() == badge
    for action in actions[4:]:
        if action.isSeparator() or isinstance(action, QWidgetAction):
            continue
        assert action.icon().pixmap(QSize(28, 28), QIcon.Mode.Normal).toImage() != badge, action.text()


def test_comic_menu_without_update_has_no_install_entry(qtbot):
    tray = KiraTray(on_quit=lambda: None)
    menu = tray._comic_menu()
    qtbot.addWidget(menu)
    assert not any("installieren" in action.text() for action in menu.actions())


@pytest.mark.parametrize("mode", [QIcon.Mode.Normal, QIcon.Mode.Active])
def test_update_symbol_is_the_green_badge_in_both_hover_states(qtbot, mode):
    from kira.ui import _comic as comic
    image = comic.menu_icon("update").pixmap(QSize(28, 28), mode).toImage()
    width = image.width()
    assert image.pixelColor(0, 0).alpha() == 0
    assert _near_colour(image.pixelColor(width // 2, width // 2), "#FFFFFF")
    assert _near_colour(image.pixelColor(round(width * 0.695), round(width * 0.539)), "#2FA84F")
