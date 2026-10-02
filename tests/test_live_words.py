# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import threading
import time

import numpy as np
import pytest

import kira.live_words as lw


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(lw, "FIRST_AFTER_S", 0.0)
    monkeypatch.setattr(lw, "PAUSE_S", 0.02)


def _voice(seconds: float = 1.0, amp: float = 0.2) -> np.ndarray:
    n = int(seconds * lw.SAMPLE_RATE)
    return (amp * np.sin(np.arange(n) * 0.05)).astype(np.float32)


def _push_blocks(live: lw.LiveWords, seconds: float) -> None:
    for _ in range(round(seconds / 0.1)):
        live.push(_voice(0.1))


def _wait_for(cond, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_fragments_take_the_last_words_and_shorten_long_ones():
    assert lw.fragments("Hallo, das ist ein Spracherkennungstest.") == ["ein", "Spracher…"]
    assert lw.fragments("") == []
    assert lw.fragments("  …  ") == []


def test_new_words_are_reported_while_recording():
    got: list[str] = []
    texts = iter(["Hallo Welt", "Hallo Welt", "Welt heute"])
    live = lw.LiveWords(lambda audio: next(texts, ""), got.extend)
    live.start()
    _push_blocks(live, 1.0)
    assert _wait_for(lambda: len(got) >= 3)
    live.stop()
    assert got == ["Hallo", "Welt", "heute"]


def test_silence_never_reaches_whisper():
    calls: list[int] = []
    live = lw.LiveWords(lambda audio: calls.append(audio.size) or "Hallo", lambda words: None)
    live.start()
    for _ in range(10):
        live.push(np.zeros(1600, dtype=np.float32))
    time.sleep(0.2)
    live.stop()
    assert calls == []


def test_results_arriving_after_stop_are_dropped():
    got: list[str] = []
    gate = threading.Event()

    def slow(audio):
        gate.wait(1.0)
        return "spät"

    live = lw.LiveWords(slow, got.extend)
    live.start()
    _push_blocks(live, 1.0)
    time.sleep(0.1)
    live.stop()
    gate.set()
    time.sleep(0.15)
    assert got == []


def test_nothing_runs_when_the_display_does_not_want_words():
    calls: list[int] = []
    live = lw.LiveWords(lambda audio: calls.append(1) or "Hallo", lambda words: None, wanted=lambda: False)
    live.start()
    _push_blocks(live, 1.0)
    time.sleep(0.15)
    live.stop()
    assert calls == []


def test_only_the_last_seconds_are_transcribed():
    sizes: list[int] = []
    live = lw.LiveWords(lambda audio: sizes.append(audio.size) or "", lambda words: None)
    live.start()
    _push_blocks(live, 6.0)
    assert _wait_for(lambda: bool(sizes))
    live.stop()
    assert max(sizes) <= int(lw.WINDOW_S * lw.SAMPLE_RATE) + 1600


def test_a_failing_transcription_does_not_stop_the_worker():
    calls: list[int] = []

    def broken(audio):
        calls.append(1)
        raise RuntimeError("kaputt")

    live = lw.LiveWords(broken, lambda words: None)
    live.start()
    _push_blocks(live, 1.0)
    assert _wait_for(lambda: len(calls) >= 2)
    live.stop()
