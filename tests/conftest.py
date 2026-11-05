# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys
import pytest


@pytest.fixture(autouse=True)
def _no_real_clipboard_or_keys(monkeypatch):
    if sys.platform != "win32":
        yield
        return
    import ctypes
    import keyboard
    import pyperclip
    import win32clipboard
    touched: list[str] = []

    def refuse(name: str):
        def refused(*_args, **_kwargs):
            touched.append(name)
            raise AssertionError(f"Test greift auf {name} des echten Systems zu")
        return refused

    monkeypatch.setattr(keyboard, "send", refuse("keyboard.send"))
    monkeypatch.setattr(pyperclip, "copy", refuse("pyperclip.copy"))
    monkeypatch.setattr(pyperclip, "paste", refuse("pyperclip.paste"))
    monkeypatch.setattr(win32clipboard, "OpenClipboard", refuse("win32clipboard.OpenClipboard"))
    monkeypatch.setattr(ctypes.windll.user32, "MessageBoxW", refuse("MessageBoxW"))
    monkeypatch.setattr(ctypes.windll.user32, "SendInput", refuse("SendInput"))
    yield
    assert touched == [], f"Test griff auf das echte System zu: {touched}"
