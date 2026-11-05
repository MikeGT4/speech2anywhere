# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import logging
import struct
import time
import pyperclip
import win32clipboard

log = logging.getLogger(__name__)

MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
SNAPSHOT_BUDGET_S = 0.25
OPEN_ATTEMPTS = 5
OPEN_RETRY_S = 0.02

_HANDLE_FORMATS = frozenset({2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E})
_HANDLE_RANGE = range(0x0200, 0x0400)
CF_DIB = 8
CF_DIBV5 = 17
_DROP_HEADER = struct.pack("<IiiII", 20, 0, 0, 0, 1)

Snapshot = list[tuple[int, object]]


def _open() -> bool:
    for _attempt in range(OPEN_ATTEMPTS):
        try:
            win32clipboard.OpenClipboard()
            return True
        except Exception:
            time.sleep(OPEN_RETRY_S)
    return False


def _size(data: object) -> int:
    if isinstance(data, str):
        return len(data) * 2
    if isinstance(data, tuple):
        return sum(len(name) * 2 + 2 for name in data)
    return len(data)  # type: ignore[arg-type]


def _drop_files(names: tuple) -> bytes:
    return _DROP_HEADER + ("\0".join(names) + "\0\0").encode("utf-16-le")


def snapshot() -> Snapshot | None:
    if not _open():
        log.warning("Zwischenablage gesperrt, es wird nur Text gesichert")
        return None
    entries: Snapshot = []
    total = 0
    deadline = time.monotonic() + SNAPSHOT_BUDGET_S
    try:
        offered = []
        fmt = win32clipboard.EnumClipboardFormats(0)
        while fmt:
            offered.append(fmt)
            fmt = win32clipboard.EnumClipboardFormats(fmt)
        derived = {CF_DIB} if CF_DIBV5 in offered else set()
        for fmt in offered:
            if fmt in _HANDLE_FORMATS or fmt in _HANDLE_RANGE or fmt in derived:
                continue
            try:
                data = win32clipboard.GetClipboardData(fmt)
            except Exception:
                data = None
            if isinstance(data, (str, bytes, tuple)):
                total += _size(data)
                if total > MAX_SNAPSHOT_BYTES or time.monotonic() > deadline:
                    log.info("Zwischenablage zu groß oder zu langsam, es wird nur Text gesichert")
                    return None
                entries.append((fmt, data))
        return entries
    except Exception:
        log.exception("Zwischenablage ließ sich nicht lesen, es wird nur Text gesichert")
        return None
    finally:
        win32clipboard.CloseClipboard()


def restore(entries: Snapshot) -> bool:
    if not _open():
        return False
    try:
        win32clipboard.EmptyClipboard()
        for fmt, data in entries:
            try:
                win32clipboard.SetClipboardData(fmt, _drop_files(data) if isinstance(data, tuple) else data)
            except Exception:
                log.warning("Zwischenablage: Format %d ließ sich nicht zurücklegen", fmt)
        return True
    except Exception:
        log.exception("Zwischenablage ließ sich nicht zurücklegen")
        return False
    finally:
        win32clipboard.CloseClipboard()


def sequence() -> int:
    return win32clipboard.GetClipboardSequenceNumber()


def save() -> Snapshot | str:
    entries = snapshot()
    return entries if entries is not None else pyperclip.paste()


def put_back(saved: Snapshot | str) -> None:
    if isinstance(saved, str):
        pyperclip.copy(saved)
    elif not restore(saved):
        raise OSError("Zwischenablage gesperrt")
