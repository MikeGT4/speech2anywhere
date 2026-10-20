from __future__ import annotations
import sys
from unittest.mock import MagicMock, patch

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)


@pytest.fixture
def tray():
    from kira.ui.tray_win import KiraTray
    quit_calls = []
    t = KiraTray(on_quit=lambda: quit_calls.append(1))
    t._quit_calls = quit_calls
    return t


def test_check_for_updates_marshals_to_qt(tray):
    tray._marshal_to_qt = MagicMock()
    tray._check_for_updates(None, None)
    tray._marshal_to_qt.assert_called_once()
    label = tray._marshal_to_qt.call_args.args[1]
    assert "update" in label.lower()


def test_run_update_flow_marshalled_calls_underlying_runner():
    from kira.ui.tray_win import KiraTray

    quit_marker = MagicMock()
    with patch("kira.ui._update_runner.run_update_flow") as mock_run:
        KiraTray._run_update_flow_marshalled(quit_marker)
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["parent"] is None
    assert kwargs["on_quit_request"] is quit_marker


def test_check_for_updates_passes_quit_callback_through(tray):
    captured = {}

    def fake_marshal(func, _label):
        captured["called"] = True
        with patch("kira.ui._update_runner.run_update_flow") as mock_run:
            func()
            captured["kwargs"] = mock_run.call_args.kwargs

    tray._marshal_to_qt = fake_marshal
    tray._check_for_updates(None, None)
    assert captured.get("called") is True
    assert captured["kwargs"]["on_quit_request"] is tray._on_quit
    assert captured["kwargs"]["parent"] is None


def test_menu_includes_check_for_updates_item(tray):
    menu = tray._build_menu()
    labels = [getattr(item, "text", None) for item in menu.items]
    assert "Updates suchen…" in labels


def _make_fake_messagebox(answer):
    class _FakeMessageBox:
        class StandardButton:
            Yes = 1
            No = 2

        class Icon:
            Question = 4

        def __init__(self, _parent):
            pass

        def setWindowTitle(self, _t): pass
        def setIcon(self, _i): pass
        def setText(self, _t): pass
        def setInformativeText(self, _t): pass
        def setStandardButtons(self, _b): pass
        def setDefaultButton(self, _b): pass

    setattr(_FakeMessageBox, "exec", lambda self: answer)
    return _FakeMessageBox


def _patch_qt(monkeypatch, answer):
    import PyQt6.QtWidgets as qtw
    import kira.ui._dialog_style as dlg_style
    fake = _make_fake_messagebox(answer)
    monkeypatch.setattr(qtw, "QMessageBox", fake)
    monkeypatch.setattr(dlg_style, "apply_light_theme", lambda _d: None)
    return fake


def test_prompt_start_update_yes_triggers_update_flow(tray, monkeypatch):
    _patch_qt(monkeypatch, 1)

    declined_calls = []
    with patch("kira.ui._update_runner.run_update_flow") as mock_run:
        tray.prompt_start_update("0.4.0", on_declined=declined_calls.append)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["on_quit_request"] is tray._on_quit
    assert mock_run.call_args.kwargs["parent"] is None
    assert declined_calls == []


def test_prompt_start_update_no_calls_on_declined(tray, monkeypatch):
    _patch_qt(monkeypatch, 2)

    declined_calls = []
    with patch("kira.ui._update_runner.run_update_flow") as mock_run:
        tray.prompt_start_update("0.4.0", on_declined=declined_calls.append)

    mock_run.assert_not_called()
    assert declined_calls == ["0.4.0"]


def test_prompt_start_update_no_without_callback_is_safe(tray, monkeypatch):
    _patch_qt(monkeypatch, 2)
    with patch("kira.ui._update_runner.run_update_flow"):
        tray.prompt_start_update("0.4.0")


def test_prompt_start_update_skips_while_an_update_runs(tray, monkeypatch):
    import kira.ui._update_runner as runner
    monkeypatch.setattr(runner, "_flow_active", True)
    _patch_qt(monkeypatch, 2)
    declined_calls = []
    with patch("kira.ui._update_runner.run_update_flow") as mock_run:
        tray.prompt_start_update("0.4.2", on_declined=declined_calls.append)
    mock_run.assert_not_called()
    assert declined_calls == []


def test_update_menu_entry_appears_when_version_is_known(tray):
    labels = [str(item.text) for item in tray._build_menu().items]
    assert not any("installieren" in label for label in labels)
    tray.set_update_available("0.4.2")
    labels = [str(item.text) for item in tray._build_menu().items]
    assert "Update auf v0.4.2 installieren…" in labels
    assert labels.index("Update auf v0.4.2 installieren…") < labels.index("Einstellungen…")


def test_update_menu_entry_disappears_when_cleared(tray):
    tray.set_update_available("0.4.2")
    tray.set_update_available(None)
    labels = [str(item.text) for item in tray._build_menu().items]
    assert not any("installieren" in label for label in labels)


def test_update_menu_entry_runs_the_update_flow(tray):
    tray.set_update_available("0.4.2")
    entry = next(i for i in tray._build_menu().items if "installieren" in str(i.text))
    tray._marshal_to_qt = MagicMock()
    entry(None)
    tray._marshal_to_qt.assert_called_once()


def test_notify_update_names_the_version(tray):
    tray.notify = MagicMock()
    tray.notify_update("0.4.2")
    title, message = tray.notify.call_args.args
    assert "Update" in title
    assert "v0.4.2" in message and "installieren" in message


def _advice(kind="ollama"):
    from kira.ollama_advice import Advice
    if kind == "ollama":
        return Advice("ollama", "0.35.0", "0.40.5")
    return Advice("model", "aa" * 32, "bb" * 32, model="gemma4:26b-a4b-it-qat")


def test_ollama_advice_adds_a_menu_entry_after_the_update(tray):
    labels = [str(item.text) for item in tray._build_menu().items]
    assert "Ollama-Empfehlung ansehen…" not in labels
    tray.set_update_available("0.5.5")
    tray.set_ollama_advice([_advice()])
    labels = [str(item.text) for item in tray._build_menu().items]
    assert labels.index("Update auf v0.5.5 installieren…") < labels.index("Ollama-Empfehlung ansehen…")
    assert labels.index("Ollama-Empfehlung ansehen…") < labels.index("Einstellungen…")
    tray.set_ollama_advice([])
    assert "Ollama-Empfehlung ansehen…" not in [str(item.text) for item in tray._build_menu().items]


def test_ollama_advice_notification_names_both_versions(tray):
    tray.notify = MagicMock()
    tray.notify_ollama_advice(_advice())
    title, message = tray.notify.call_args.args
    assert "Ollama" in title
    assert "0.40.5" in message and "0.35.0" in message
    tray.notify_ollama_advice(_advice("model"))
    assert "gemma4:26b-a4b-it-qat" in tray.notify.call_args.args[1]


def test_ollama_advice_entry_opens_the_dialog_and_decline_clears_it(tray, monkeypatch):
    import kira._update_marker as marker
    import kira.ui.ollama_advice_dialog as dialog_mod

    marked = []
    monkeypatch.setattr(marker, "mark_advice_declined", marked.append)
    opened = {}

    class _Dialog:
        def __init__(self, advice, on_declined, app_version, on_handled):
            opened["advice"] = advice
            opened["version"] = app_version
            opened["handled"] = on_handled
            self._on_declined = on_declined

        def exec(self):
            self._on_declined(opened["advice"][0].key)

    monkeypatch.setattr(dialog_mod, "OllamaAdviceDialog", _Dialog)
    tray.set_ollama_advice([_advice()])
    tray._marshal_to_qt = lambda func, label: func()
    entry = next(i for i in tray._build_menu().items if "Ollama-Empfehlung" in str(i.text))
    entry(None)
    assert opened["advice"] == [_advice()]
    assert marked == ["ollama||0.40.5"]
    assert tray._ollama_advice == []


def test_started_ollama_update_only_clears_the_menu_for_this_session(tray, monkeypatch):
    import kira._update_marker as marker
    import kira.ui.ollama_advice_dialog as dialog_mod

    marked = []
    monkeypatch.setattr(marker, "mark_advice_declined", marked.append)

    class _Dialog:
        def __init__(self, advice, on_declined, app_version, on_handled):
            self._advice, self._handled = advice, on_handled

        def exec(self):
            self._handled(self._advice[0].key)

    monkeypatch.setattr(dialog_mod, "OllamaAdviceDialog", _Dialog)
    tray.set_ollama_advice([_advice()])
    tray._show_ollama_advice()
    assert tray._ollama_advice == []
    assert marked == []
