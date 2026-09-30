from __future__ import annotations
import sys
from unittest.mock import MagicMock

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)


@pytest.fixture
def tray():
    from kira.ui.tray_win import KiraTray
    return KiraTray(on_quit=lambda: None)


def test_settings_dlg_reference_starts_none(tray):
    assert tray._settings_dlg is None


def test_open_when_already_open_raises_existing(tray):
    existing = MagicMock()
    tray._settings_dlg = existing
    tray._show_settings_dialog()
    existing.raise_.assert_called_once()
    existing.activateWindow.assert_called_once()
    assert tray._settings_dlg is existing


def test_second_click_during_open_does_not_stack(tray, monkeypatch):
    created = []

    class _FakeDialog:
        def __init__(self):
            created.append(self)
            self.raised = 0
            self.activated = 0
            self.shown = 0

        def show(self):
            self.shown += 1

        def raise_(self):
            self.raised += 1

        def activateWindow(self):
            self.activated += 1

    setattr(
        _FakeDialog, "exec",
        lambda self: tray._show_settings_dialog(),
    )
    monkeypatch.setattr(
        "kira.ui.settings_dialog.SettingsDialog", _FakeDialog,
    )

    tray._show_settings_dialog()

    assert len(created) == 1, "nur ein Dialog darf erzeugt worden sein"
    assert created[0].shown == 0, "kein show() vor dem Event-Loop"
    assert created[0].raised == 1, "nur der Guard-Pfad holt nach vorn"
    assert created[0].activated == 1
    assert tray._settings_dlg is None, "Referenz nach Schliessen zurueckgesetzt"
