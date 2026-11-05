from __future__ import annotations
import ctypes
import logging
import threading
import time
from ctypes import wintypes
from typing import Callable
import pyperclip
import keyboard
from kira import clipboard_win

log = logging.getLogger(__name__)

_LONG_TEXT_THRESHOLD = 80
_PER_CHAR_PASTE_MS = 2
_PASTE_OVERHEAD_MS = 100

REMOTE_DESKTOP_CLIENTS = frozenset({"mstsc.exe", "msrdc.exe"})
REMOTE_RESTORE_MS = 3000
TYPE_DELAY_S = 0.003

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_TAB = 0x09
_SPECIAL_KEYS = {"\n": VK_RETURN, "\t": VK_TAB}


class _KeybdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput), ("ki", _KeybdInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


def _key_events(text: str) -> list[tuple[int, int, int]]:
    events: list[tuple[int, int, int]] = []
    for char in text.replace("\r\n", "\n").replace("\r", "\n"):
        vk = _SPECIAL_KEYS.get(char)
        if vk is not None:
            events += [(vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP)]
            continue
        data = char.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            events += [(0, unit, KEYEVENTF_UNICODE), (0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return events


def _send_inputs(events: list[tuple[int, int, int]]) -> None:
    batch = (_Input * len(events))()
    for slot, (vk, scan, flags) in zip(batch, events):
        slot.type = INPUT_KEYBOARD
        slot.u.ki = _KeybdInput(vk, scan, flags, 0, 0)
    sent = ctypes.windll.user32.SendInput(len(events), batch, ctypes.sizeof(_Input))
    if sent != len(events):
        log.warning("SendInput nahm %d von %d Tastenereignissen an", sent, len(events))


def _foreground_exe() -> str | None:
    from kira.context_win import active_exe
    return active_exe()


def _clipboard_sequence() -> int | None:
    try:
        return clipboard_win.sequence()
    except Exception:
        return None


class Injector:
    def __init__(
        self,
        restore_after_ms: int = 500,
        strategy: str = "clipboard",
        foreground: Callable[[], str | None] | None = None,
    ) -> None:
        self._restore_after_ms = restore_after_ms
        self._strategy = strategy
        self._foreground = foreground or _foreground_exe
        self._lock = threading.Lock()
        self._restore_gen = 0
        self._pending_original: clipboard_win.Snapshot | str | None = None

    def _effective_restore_ms(self, text_len: int) -> int:
        if text_len <= _LONG_TEXT_THRESHOLD:
            return self._restore_after_ms
        return max(
            self._restore_after_ms,
            _PASTE_OVERHEAD_MS + text_len * _PER_CHAR_PASTE_MS,
        )

    def _remote_desktop_in_front(self) -> bool:
        try:
            return (self._foreground() or "") in REMOTE_DESKTOP_CLIENTS
        except Exception:
            log.exception("Vordergrundprogramm nicht lesbar, Einfügen über die Zwischenablage")
            return False

    def inject(self, text: str) -> None:
        if not text:
            return
        remote = self._remote_desktop_in_front()
        if self._strategy == "keystrokes" or (self._strategy == "auto" and remote):
            self._type(text, remote)
            return
        self._paste(text, remote)

    def _type(self, text: str, remote: bool) -> None:
        log.info("Typing %d chars as keystrokes (remote desktop=%s)", len(text), remote)
        events = _key_events(text)
        try:
            for i in range(0, len(events), 2):
                _send_inputs(events[i:i + 2])
                time.sleep(TYPE_DELAY_S)
        except Exception:
            log.exception("Tippen per SendInput fehlgeschlagen")

    def _paste(self, text: str, remote: bool) -> None:
        delay_ms = self._effective_restore_ms(len(text))
        if remote:
            delay_ms = max(delay_ms, REMOTE_RESTORE_MS)
        log.info(
            "Injecting %d chars (restore in %d ms): %r",
            len(text), delay_ms, text[:80],
        )
        with self._lock:
            self._restore_gen += 1
            gen = self._restore_gen
            if self._pending_original is None:
                try:
                    self._pending_original = clipboard_win.save()
                except Exception:
                    self._pending_original = ""
                    log.warning("pyperclip.paste failed, restore will be empty")
        try:
            pyperclip.copy(text)
        except Exception:
            log.exception("pyperclip.copy failed")
            return
        own = _clipboard_sequence()
        time.sleep(0.02)
        try:
            keyboard.send("ctrl+v")
        except Exception:
            log.exception("keyboard.send(ctrl+v) failed")

        def restore():
            with self._lock:
                if gen != self._restore_gen:
                    return
                saved = self._pending_original
                self._pending_original = None
            if own is not None and _clipboard_sequence() != own:
                log.info("Zwischenablage inzwischen neu belegt, der neue Inhalt bleibt")
                return
            try:
                clipboard_win.put_back(saved if saved is not None else "")
            except Exception:
                log.warning("failed to restore clipboard")

        threading.Timer(delay_ms / 1000.0, restore).start()
