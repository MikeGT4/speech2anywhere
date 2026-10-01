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
    assert _entries(menu) == [
        "●  Bereit", "Update auf v0.5.0 installieren…", "Einstellungen…", "Gelernte Wörter (3 neu)…",
        "Anleitung…", "Protokoll öffnen…", "Updates suchen…", "Über Speech2Anywhere", "Beenden",
    ]
    status = next(a for a in menu.actions() if a.text() == "●  Bereit")
    assert not status.isEnabled()


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
