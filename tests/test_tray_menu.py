# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys
from types import SimpleNamespace

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from PyQt6.QtWidgets import QWidgetAction


class FakeLearning:
    def pending_count(self):
        return 3


def _entries(menu):
    return [a.text() for a in menu.actions() if not a.isSeparator() and not isinstance(a, QWidgetAction)]


def test_right_click_asks_for_the_comic_menu():
    from pystray._util import win32
    from kira.ui.tray_win import _KiraPystrayIcon
    calls = []
    fake = SimpleNamespace(on_context_menu=lambda: calls.append("menü") or True, _hwnd=0)
    _KiraPystrayIcon._on_notify(fake, 0, win32.WM_RBUTTONUP)
    assert calls == ["menü"]


def test_comic_menu_follows_the_approved_draft(qtbot):
    from kira.ui.tray_win import KiraTray
    tray = KiraTray(on_quit=lambda: None, learning=FakeLearning())
    tray._update_available = "0.5.0"
    menu = tray._comic_menu()
    qtbot.addWidget(menu)
    assert isinstance(menu.actions()[0], QWidgetAction), "oben der Kopf mit Logo und Wortmarke"
    status = menu.actions()[1]
    assert isinstance(status, QWidgetAction), "darunter die Statuskarte"
    assert status.defaultWidget()._text == "Bereit"
    assert status.defaultWidget()._mascot is not None
    assert not status.isEnabled()
    assert _entries(menu) == [
        "Update auf v0.5.0 installieren…", "Einstellungen…", "Gelernte Wörter (3 neu)…",
        "Anleitung…", "Protokoll öffnen…", "Updates suchen…", "Über Speech2Anywhere", "Beenden",
    ]
    for action in menu.actions():
        if not action.isSeparator() and not isinstance(action, QWidgetAction):
            assert not action.icon().isNull(), f"Symbol fehlt: {action.text()}"


def test_comic_menu_shows_other_states_without_the_face(qtbot):
    from kira.ui.tray_win import KiraTray
    from kira.app import State
    tray = KiraTray(on_quit=lambda: None)
    tray.update_state(State.RECORDING)
    menu = tray._comic_menu()
    qtbot.addWidget(menu)
    card = menu.actions()[1].defaultWidget()
    assert card._text == "Aufnahme läuft…"
    assert card._mascot is None


def test_menu_icons_are_round_and_28_px(qtbot):
    import kira.ui._comic as comic
    from PyQt6.QtWidgets import QStyle
    menu = comic.ComicMenu()
    qtbot.addWidget(menu)
    assert menu.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize) == 28
    for kind in ("gear", "clock", "wand", "book", "document", "file", "info", "power", "retry"):
        pix = comic.menu_icon(kind).pixmap(28, 28)
        assert not pix.isNull() and pix.width() >= 28


def _near(color, hex_rgb, tolerance=10):
    from PyQt6.QtGui import QColor
    want = QColor(hex_rgb)
    return all(abs(a - b) <= tolerance for a, b in ((color.red(), want.red()), (color.green(), want.green()),
                                                    (color.blue(), want.blue())))


def test_menu_icon_disc_turns_cream_when_hovered(qtbot):
    import kira.ui._comic as comic
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QIcon
    for kind in ("gear", "clock", "wand", "book", "document", "file", "info", "power", "retry"):
        icon = comic.menu_icon(kind)
        normal = icon.pixmap(QSize(28, 28), QIcon.Mode.Normal).toImage()
        hovered = icon.pixmap(QSize(28, 28), QIcon.Mode.Active).toImage()
        x, y = round(normal.width() * 3.6 / 24), normal.height() // 2
        assert _near(normal.pixelColor(x, y), comic.YELLOW), kind
        assert _near(hovered.pixelColor(x, y), comic.CREAM), kind


def test_hovered_last_entry_shows_a_cream_disc_and_stays_inside_the_frame(qtbot):
    import kira.ui._comic as comic
    from kira.ui.tray_win import KiraTray
    tray = KiraTray(on_quit=lambda: None, learning=FakeLearning())
    menu = tray._comic_menu()
    qtbot.addWidget(menu)
    menu.ensurePolished()
    menu.resize(menu.sizeHint())
    quit_action = next(a for a in menu.actions() if a.text() == "Beenden")
    calm = menu.grab().toImage()
    menu.setActiveAction(quit_action)
    hot = menu.grab().toImage()
    scale = hot.width() / menu.width()
    rect = menu.actionGeometry(quit_action)
    frame = comic.ComicMenu.SHADOW + 3
    assert rect.bottom() <= menu.height() - frame, (rect, menu.height())
    assert rect.right() - 8 <= menu.width() - frame, (rect, menu.width())
    cy = round(rect.center().y() * scale)
    pill = round((rect.right() - 30) * scale)
    assert _near(hot.pixelColor(pill, cy), comic.YELLOW), "Pille beim Hover"
    assert _near(calm.pixelColor(pill, cy), comic.CREAM, 6), "ohne Hover keine Pille"
    xs = range(round((rect.left() + 12) * scale), round((rect.left() + 70) * scale))
    disc = next((x for x in xs if _near(hot.pixelColor(x, cy), comic.CREAM, 6)), None)
    assert disc is not None, "kein heller Symbolkreis beim Hover"
    assert _near(calm.pixelColor(disc, cy), comic.YELLOW), "ohne Hover ist der Kreis gelb"


def test_comic_menu_entry_runs_the_tray_action(qtbot, monkeypatch):
    from kira.ui.tray_win import KiraTray
    opened = []
    monkeypatch.setattr(KiraTray, "_open_settings", lambda self, icon, item: opened.append(icon))
    tray = KiraTray(on_quit=lambda: None)
    tray._icon = "icon"
    menu = tray._comic_menu()
    qtbot.addWidget(menu)
    next(a for a in menu.actions() if a.text() == "Einstellungen…").trigger()
    assert opened == ["icon"]


class InstantMarshal:
    def run_on_main_thread(self, fn):
        fn()


class BlockedMarshal:
    def __init__(self):
        self.waiting = []

    def run_on_main_thread(self, fn):
        self.waiting.append(fn)


def test_context_menu_needs_a_responsive_qt_thread(monkeypatch):
    import time
    from kira.ui.tray_win import KiraTray
    shown = []
    monkeypatch.setattr(KiraTray, "_show_context_menu", lambda self: shown.append(True))
    assert KiraTray(on_quit=lambda: None, qt_marshal=InstantMarshal())._request_context_menu() is True
    assert shown == [True]
    blocked = BlockedMarshal()
    started = time.monotonic()
    assert KiraTray(on_quit=lambda: None, qt_marshal=blocked)._request_context_menu() is False
    assert time.monotonic() - started < 1.0
    for fn in blocked.waiting:
        fn()
    assert shown == [True]
    assert KiraTray(on_quit=lambda: None)._request_context_menu() is False


def test_right_click_falls_back_to_the_native_menu_when_qt_is_busy(monkeypatch):
    from pystray._util import win32
    from kira.ui import tray_win
    native = []
    monkeypatch.setattr(tray_win._PystrayWin32Icon, "_on_notify", lambda self, wparam, lparam: native.append(lparam))
    icon = tray_win._KiraPystrayIcon("probe", icon=tray_win._load_or_generate_icon(tray_win.State.IDLE))
    icon.on_context_menu = lambda: False
    icon._on_notify(0, win32.WM_RBUTTONUP)
    assert native == [win32.WM_RBUTTONUP]
