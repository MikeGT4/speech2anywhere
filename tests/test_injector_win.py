from __future__ import annotations
import sys
import threading
import time
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)


@pytest.fixture(autouse=True)
def _no_remote_desktop_in_front(monkeypatch):
    from kira import injector_win
    monkeypatch.setattr(injector_win, "_foreground_exe", lambda: None)


@pytest.fixture(autouse=True)
def _no_timer_outlives_its_test(monkeypatch):
    from kira import injector_win
    started = []
    plain_timer = threading.Timer

    class Tracked(plain_timer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            started.append(self)

    monkeypatch.setattr(injector_win.threading, "Timer", Tracked)
    yield
    for timer in started:
        timer.cancel()
        timer.join(timeout=2)


@pytest.fixture(autouse=True)
def _text_only_clipboard(monkeypatch):
    from kira import injector_win
    monkeypatch.setattr(injector_win.clipboard_win, "snapshot", lambda: None)
    monkeypatch.setattr(injector_win.clipboard_win, "sequence", lambda: 1)


def test_inject_empty_is_noop(monkeypatch):
    from kira import injector_win

    copy_calls = {"n": 0}
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: "saved")
    monkeypatch.setattr(
        injector_win.pyperclip, "copy",
        lambda t: copy_calls.update(n=copy_calls["n"] + 1),
    )
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    injector_win.Injector().inject("")
    assert copy_calls["n"] == 0


def test_inject_sends_ctrl_v(monkeypatch):
    from kira import injector_win

    sent = {"val": None}
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: "saved")
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: None)
    monkeypatch.setattr(
        injector_win.keyboard, "send",
        lambda k: sent.update(val=k),
    )

    injector_win.Injector().inject("hello")
    assert sent["val"] == "ctrl+v"


def test_inject_sets_clipboard_to_text(monkeypatch):
    from kira import injector_win

    copies = []
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: "saved")
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: copies.append(t))
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    injector_win.Injector().inject("hello world")
    assert copies[0] == "hello world"


def test_inject_restores_clipboard_after_delay(monkeypatch):
    from kira import injector_win

    copies = []
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: "ORIGINAL")
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: copies.append(t))
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    inj = injector_win.Injector(restore_after_ms=10)
    inj.inject("NEW")
    time.sleep(0.05)
    assert copies[0] == "NEW"
    assert copies[-1] == "ORIGINAL"


def test_inject_survives_paste_exception(monkeypatch):
    from kira import injector_win

    def raising_paste():
        raise RuntimeError("clipboard locked")

    copies = []
    monkeypatch.setattr(injector_win.pyperclip, "paste", raising_paste)
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: copies.append(t))
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    inj = injector_win.Injector(restore_after_ms=10)
    inj.inject("NEW")
    time.sleep(0.05)
    assert copies[0] == "NEW"


def test_short_text_uses_base_restore_delay():
    from kira import injector_win

    inj = injector_win.Injector(restore_after_ms=500)
    assert inj._effective_restore_ms(0) == 500
    assert inj._effective_restore_ms(1) == 500
    assert inj._effective_restore_ms(80) == 500


def test_long_text_extends_restore_delay():
    from kira import injector_win

    inj = injector_win.Injector(restore_after_ms=500)
    assert inj._effective_restore_ms(463) == 1026
    assert inj._effective_restore_ms(200) == 500
    assert inj._effective_restore_ms(250) == 600


def test_long_text_respects_higher_base():
    from kira import injector_win

    inj = injector_win.Injector(restore_after_ms=2000)
    assert inj._effective_restore_ms(80) == 2000
    assert inj._effective_restore_ms(500) == 2000
    assert inj._effective_restore_ms(2000) == 4100


def test_default_restore_after_ms_is_500():
    from kira import injector_win

    inj = injector_win.Injector()
    assert inj._restore_after_ms == 500


def test_stale_restore_timer_does_not_clobber_newer_injection(monkeypatch):
    from kira import injector_win

    time.sleep(0.6)

    clipboard = {"val": "ORIGINAL"}
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: clipboard["val"])
    monkeypatch.setattr(
        injector_win.pyperclip, "copy", lambda t: clipboard.update(val=t),
    )
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    inj = injector_win.Injector(restore_after_ms=150)
    inj.inject("text1")
    time.sleep(0.02)
    inj.inject("text2")

    time.sleep(0.5)

    assert clipboard["val"] == "ORIGINAL"


def test_single_injection_restore_unaffected_by_generation_guard(monkeypatch):
    from kira import injector_win

    clipboard = {"val": "ORIGINAL-A"}
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: clipboard["val"])
    monkeypatch.setattr(
        injector_win.pyperclip, "copy", lambda t: clipboard.update(val=t),
    )
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    inj = injector_win.Injector(restore_after_ms=80)
    inj.inject("text1")
    time.sleep(0.4)
    assert clipboard["val"] == "ORIGINAL-A"

    clipboard["val"] = "ORIGINAL-B"
    inj.inject("text2")
    time.sleep(0.4)
    assert clipboard["val"] == "ORIGINAL-B"


def _quiet_clipboard(monkeypatch, injector_win):
    copies, keys = [], []
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: "saved")
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: copies.append(t))
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: keys.append(k))
    typed = []
    monkeypatch.setattr(injector_win, "_send_inputs", lambda events: typed.extend(events))
    monkeypatch.setattr(injector_win.time, "sleep", lambda s: None)
    return copies, keys, typed


@pytest.mark.parametrize("exe", ["mstsc.exe", "msrdc.exe"])
def test_remote_desktop_window_gets_typed_text_and_clipboard_stays(monkeypatch, exe):
    from kira import injector_win

    copies, keys, typed = _quiet_clipboard(monkeypatch, injector_win)
    injector_win.Injector(strategy="auto", foreground=lambda: exe).inject("Grüße")
    assert copies == [] and keys == []
    assert typed == injector_win._key_events("Grüße")


def test_key_events_type_unicode_units_and_press_enter_and_tab():
    from kira import injector_win

    events = injector_win._key_events("Ä\n\t😀")
    unicode = injector_win.KEYEVENTF_UNICODE
    up = injector_win.KEYEVENTF_KEYUP
    assert events == [
        (0, 0xC4, unicode), (0, 0xC4, unicode | up),
        (injector_win.VK_RETURN, 0, 0), (injector_win.VK_RETURN, 0, up),
        (injector_win.VK_TAB, 0, 0), (injector_win.VK_TAB, 0, up),
        (0, 0xD83D, unicode), (0, 0xD83D, unicode | up),
        (0, 0xDE00, unicode), (0, 0xDE00, unicode | up),
    ]


def test_carriage_returns_do_not_double_the_enter():
    from kira import injector_win

    assert injector_win._key_events("a\r\nb") == injector_win._key_events("a\nb")


def test_keystroke_strategy_types_in_every_window(monkeypatch):
    from kira import injector_win

    copies, keys, typed = _quiet_clipboard(monkeypatch, injector_win)
    injector_win.Injector(strategy="keystrokes", foreground=lambda: "notepad.exe").inject("hallo")
    assert copies == [] and keys == []
    assert typed == injector_win._key_events("hallo")


def test_ordinary_window_keeps_pasting(monkeypatch):
    from kira import injector_win

    copies, keys, typed = _quiet_clipboard(monkeypatch, injector_win)
    injector_win.Injector(strategy="auto", foreground=lambda: "notepad.exe").inject("hallo")
    assert keys == ["ctrl+v"] and copies[0] == "hallo"
    assert typed == []


def test_default_pastes_in_remote_desktop_and_waits_longer_before_restoring(monkeypatch):
    from kira import injector_win

    copies, keys, typed = _quiet_clipboard(monkeypatch, injector_win)
    delays = []

    class _Timer:
        def __init__(self, seconds, fn):
            delays.append(seconds)

        def start(self):
            pass

    monkeypatch.setattr(injector_win.threading, "Timer", _Timer)
    injector_win.Injector(foreground=lambda: "mstsc.exe").inject("hallo")
    assert keys == ["ctrl+v"] and typed == []
    assert delays == [injector_win.REMOTE_RESTORE_MS / 1000.0]
    assert injector_win.REMOTE_RESTORE_MS >= 3000


def test_unknown_foreground_falls_back_to_pasting(monkeypatch):
    from kira import injector_win

    copies, keys, typed = _quiet_clipboard(monkeypatch, injector_win)
    injector_win.Injector(strategy="auto", foreground=lambda: None).inject("hallo")
    assert keys == ["ctrl+v"] and typed == []


def test_inject_puts_the_full_snapshot_back_after_the_delay(monkeypatch):
    from kira import injector_win

    snap = [(8, b"DIB")]
    restored = []
    monkeypatch.setattr(injector_win.clipboard_win, "snapshot", lambda: snap)
    monkeypatch.setattr(
        injector_win.clipboard_win, "restore", lambda entries: restored.append(entries) or True,
    )
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: None)
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    injector_win.Injector(restore_after_ms=10).inject("NEW")
    time.sleep(0.05)
    assert restored == [snap]


def test_inject_keeps_what_the_user_copied_in_the_meantime(monkeypatch):
    from kira import injector_win

    numbers = iter([5, 6])
    copies = []
    monkeypatch.setattr(injector_win.clipboard_win, "sequence", lambda: next(numbers))
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: "ORIGINAL")
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: copies.append(t))
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    injector_win.Injector(restore_after_ms=10).inject("NEW")
    time.sleep(0.05)
    assert copies == ["NEW"]


def test_inject_still_restores_when_the_clipboard_counter_is_unavailable(monkeypatch):
    from kira import injector_win

    def broken():
        raise OSError("no counter")

    copies = []
    monkeypatch.setattr(injector_win.clipboard_win, "sequence", broken)
    monkeypatch.setattr(injector_win.pyperclip, "paste", lambda: "ORIGINAL")
    monkeypatch.setattr(injector_win.pyperclip, "copy", lambda t: copies.append(t))
    monkeypatch.setattr(injector_win.keyboard, "send", lambda k: None)

    injector_win.Injector(restore_after_ms=10).inject("NEW")
    time.sleep(0.05)
    assert copies == ["NEW", "ORIGINAL"]
