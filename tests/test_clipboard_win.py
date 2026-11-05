# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import struct
import sys
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

CF_BITMAP = 2
CF_DIB = 8
CF_UNICODETEXT = 13
CF_HDROP = 15
HTML_FORMAT = 49161


class FakeClipboard:
    def __init__(self, formats=None, locked=0, unreadable=()):
        self.formats = dict(formats or {})
        self.locked = locked
        self.unreadable = set(unreadable)
        self.opens = 0
        self.closes = 0
        self.calls = []
        self.number = 7

    def OpenClipboard(self, *args):
        self.opens += 1
        if self.locked:
            self.locked -= 1
            raise OSError("locked")

    def CloseClipboard(self):
        self.closes += 1

    def EnumClipboardFormats(self, previous=0):
        keys = list(self.formats)
        if previous == 0:
            return keys[0] if keys else 0
        index = keys.index(previous) + 1
        return keys[index] if index < len(keys) else 0

    def GetClipboardData(self, fmt):
        if fmt in self.unreadable:
            raise OSError("unreadable")
        return self.formats[fmt]

    def EmptyClipboard(self):
        self.calls.append(("empty",))
        self.formats = {}

    def SetClipboardData(self, fmt, data):
        self.calls.append(("set", fmt, data))
        self.formats[fmt] = data

    def GetClipboardSequenceNumber(self):
        return self.number


@pytest.fixture
def install(monkeypatch):
    from kira import clipboard_win

    monkeypatch.setattr(clipboard_win.time, "sleep", lambda _s: None)

    def _install(**kwargs):
        fake = FakeClipboard(**kwargs)
        monkeypatch.setattr(clipboard_win, "win32clipboard", fake)
        return fake

    return _install


def test_snapshot_keeps_text_html_and_image_data(install):
    from kira import clipboard_win

    install(formats={CF_UNICODETEXT: "Hallo", HTML_FORMAT: b"<b>Hallo</b>", CF_DIB: b"DIB"})

    assert clipboard_win.snapshot() == [
        (CF_UNICODETEXT, "Hallo"), (HTML_FORMAT, b"<b>Hallo</b>"), (CF_DIB, b"DIB"),
    ]


def test_snapshot_leaves_out_graphics_handles(install):
    from kira import clipboard_win

    install(formats={CF_BITMAP: 4711, CF_DIB: b"DIB"})

    assert clipboard_win.snapshot() == [(CF_DIB, b"DIB")]


def test_snapshot_keeps_file_list_as_names(install):
    from kira import clipboard_win

    install(formats={CF_HDROP: ("C:\\a.txt", "C:\\b.txt")})

    assert clipboard_win.snapshot() == [(CF_HDROP, ("C:\\a.txt", "C:\\b.txt"))]


def test_snapshot_of_empty_clipboard_is_an_empty_list(install):
    from kira import clipboard_win

    install()

    assert clipboard_win.snapshot() == []


def test_snapshot_leaves_out_a_format_that_cannot_be_read(install):
    from kira import clipboard_win

    install(formats={CF_UNICODETEXT: "Hallo", HTML_FORMAT: b"x"}, unreadable={HTML_FORMAT})

    assert clipboard_win.snapshot() == [(CF_UNICODETEXT, "Hallo")]


def test_snapshot_gives_up_above_the_size_limit(install, monkeypatch):
    from kira import clipboard_win

    monkeypatch.setattr(clipboard_win, "MAX_SNAPSHOT_BYTES", 10)
    install(formats={CF_DIB: b"x" * 11})

    assert clipboard_win.snapshot() is None


def test_snapshot_gives_up_when_reading_takes_too_long(install, monkeypatch):
    from kira import clipboard_win

    ticks = iter(range(0, 100))
    monkeypatch.setattr(clipboard_win.time, "monotonic", lambda: float(next(ticks)))
    install(formats={CF_UNICODETEXT: "Hallo", CF_DIB: b"DIB"})

    assert clipboard_win.snapshot() is None


def test_snapshot_gives_up_when_the_clipboard_stays_locked(install):
    from kira import clipboard_win

    fake = install(formats={CF_UNICODETEXT: "Hallo"}, locked=99)

    assert clipboard_win.snapshot() is None
    assert fake.opens == clipboard_win.OPEN_ATTEMPTS


def test_snapshot_retries_a_briefly_locked_clipboard(install):
    from kira import clipboard_win

    install(formats={CF_UNICODETEXT: "Hallo"}, locked=2)

    assert clipboard_win.snapshot() == [(CF_UNICODETEXT, "Hallo")]


def test_snapshot_closes_the_clipboard(install):
    from kira import clipboard_win

    fake = install(formats={CF_UNICODETEXT: "Hallo"})
    clipboard_win.snapshot()

    assert fake.closes == 1


def test_restore_empties_first_and_puts_every_format_back(install):
    from kira import clipboard_win

    fake = install(formats={CF_UNICODETEXT: "Diktat"})

    assert clipboard_win.restore([(CF_UNICODETEXT, "Hallo"), (CF_DIB, b"DIB")]) is True
    assert fake.calls == [("empty",), ("set", CF_UNICODETEXT, "Hallo"), ("set", CF_DIB, b"DIB")]
    assert fake.closes == 1


def test_restore_rebuilds_the_file_list_as_drop_structure(install):
    from kira import clipboard_win

    fake = install()
    clipboard_win.restore([(CF_HDROP, ("C:\\a.txt", "C:\\b.txt"))])

    expected = struct.pack("<IiiII", 20, 0, 0, 0, 1) + "C:\\a.txt\0C:\\b.txt\0\0".encode("utf-16-le")
    assert fake.calls[-1] == ("set", CF_HDROP, expected)


def test_restore_of_an_empty_snapshot_only_empties(install):
    from kira import clipboard_win

    fake = install(formats={CF_UNICODETEXT: "Diktat"})

    assert clipboard_win.restore([]) is True
    assert fake.formats == {}


def test_restore_reports_failure_when_the_clipboard_stays_locked(install):
    from kira import clipboard_win

    install(locked=99)

    assert clipboard_win.restore([(CF_UNICODETEXT, "Hallo")]) is False


def test_sequence_reads_the_clipboard_counter(install):
    from kira import clipboard_win

    fake = install()
    fake.number = 42

    assert clipboard_win.sequence() == 42


def test_save_prefers_the_full_snapshot(install, monkeypatch):
    from kira import clipboard_win

    install(formats={CF_DIB: b"DIB"})
    monkeypatch.setattr(clipboard_win.pyperclip, "paste", lambda: "nur Text")

    assert clipboard_win.save() == [(CF_DIB, b"DIB")]


def test_save_falls_back_to_text_when_no_snapshot_is_possible(install, monkeypatch):
    from kira import clipboard_win

    install(locked=99)
    monkeypatch.setattr(clipboard_win.pyperclip, "paste", lambda: "nur Text")

    assert clipboard_win.save() == "nur Text"


def test_put_back_writes_saved_text_through_pyperclip(install, monkeypatch):
    from kira import clipboard_win

    fake = install()
    copies = []
    monkeypatch.setattr(clipboard_win.pyperclip, "copy", copies.append)
    clipboard_win.put_back("nur Text")

    assert copies == ["nur Text"]
    assert fake.calls == []


def test_put_back_restores_a_snapshot(install):
    from kira import clipboard_win

    fake = install()
    clipboard_win.put_back([(CF_DIB, b"DIB")])

    assert fake.formats == {CF_DIB: b"DIB"}


def test_put_back_raises_when_the_snapshot_cannot_be_restored(install):
    from kira import clipboard_win

    install(locked=99)

    with pytest.raises(OSError):
        clipboard_win.put_back([(CF_DIB, b"DIB")])


CF_DIBV5 = 17


def test_snapshot_keeps_one_copy_of_an_image_windows_offers_twice(install):
    from kira import clipboard_win

    install(formats={CF_DIB: b"d" * 40, CF_DIBV5: b"v" * 44, CF_UNICODETEXT: "x"})

    assert clipboard_win.snapshot() == [(CF_DIBV5, b"v" * 44), (CF_UNICODETEXT, "x")]


def test_snapshot_keeps_the_plain_image_when_it_is_the_only_one(install):
    from kira import clipboard_win

    install(formats={CF_DIB: b"d" * 40})

    assert clipboard_win.snapshot() == [(CF_DIB, b"d" * 40)]


def test_image_offered_twice_counts_once_against_the_size_limit(install, monkeypatch):
    from kira import clipboard_win

    monkeypatch.setattr(clipboard_win, "MAX_SNAPSHOT_BYTES", 100)
    install(formats={CF_DIB: b"d" * 60, CF_DIBV5: b"v" * 60})

    assert clipboard_win.snapshot() == [(CF_DIBV5, b"v" * 60)]


def test_snapshot_leaves_out_private_formats(install):
    from kira import clipboard_win

    install(formats={0x0200: b"privat", 0x02FF: b"privat", CF_UNICODETEXT: "x"})

    assert clipboard_win.snapshot() == [(CF_UNICODETEXT, "x")]
