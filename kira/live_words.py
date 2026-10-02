# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
WINDOW_S = 3.0
MIN_AUDIO_S = 0.5
FIRST_AFTER_S = 0.6
PAUSE_S = 0.35
VOICE_RMS = 0.008
LAST_WORDS = 2
MAX_CHARS = 9

_WORD = re.compile(r"\w[\w'-]*")


def fragments(text: str, count: int = LAST_WORDS) -> list[str]:
    out: list[str] = []
    for word in _WORD.findall(text)[-count:]:
        word = word.strip("'-")
        if word:
            out.append(word if len(word) <= MAX_CHARS else word[:MAX_CHARS - 1] + "…")
    return out


class LiveWords:
    def __init__(
        self,
        transcribe: Callable[[np.ndarray], str],
        on_words: Callable[[list[str]], None],
        wanted: Callable[[], bool] = lambda: True,
    ) -> None:
        self._transcribe = transcribe
        self._on_words = on_words
        self._wanted = wanted
        self._lock = threading.Lock()
        self._chunks: deque[np.ndarray] = deque()
        self._samples = 0
        self._active = False
        self._generation = 0
        self._stop = threading.Event()

    def push(self, block) -> None:
        if not self._active:
            return
        chunk = np.asarray(block, dtype=np.float32).reshape(-1)
        keep = int(WINDOW_S * SAMPLE_RATE)
        with self._lock:
            if not self._active:
                return
            self._chunks.append(chunk)
            self._samples += chunk.size
            while self._chunks and self._samples - self._chunks[0].size >= keep:
                self._samples -= self._chunks.popleft().size

    def _is_wanted(self) -> bool:
        try:
            return bool(self._wanted())
        except Exception:
            log.debug("Live-Wörter: Abfrage der Anzeige fehlgeschlagen", exc_info=True)
            return False

    def start(self) -> None:
        stop = threading.Event()
        with self._lock:
            self._stop.set()
            self._stop = stop
            self._chunks.clear()
            self._samples = 0
            self._active = True
            self._generation += 1
            generation = self._generation
        threading.Thread(
            target=self._run, args=(generation, stop), daemon=True, name="kira-live-words",
        ).start()

    def stop(self) -> None:
        with self._lock:
            self._active = False
            self._generation += 1
            self._chunks.clear()
            self._samples = 0
            self._stop.set()

    def _window(self) -> np.ndarray:
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks)

    def _current(self, generation: int) -> bool:
        with self._lock:
            return self._active and generation == self._generation

    def _run(self, generation: int, stop: threading.Event) -> None:
        recent: deque[str] = deque(maxlen=3)
        runs = shown = 0
        spent = 0.0
        if stop.wait(FIRST_AFTER_S):
            return
        while self._current(generation) and self._is_wanted():
            audio = self._window()
            tail = audio[-SAMPLE_RATE:]
            if audio.size >= MIN_AUDIO_S * SAMPLE_RATE and float(np.sqrt(np.mean(tail ** 2))) >= VOICE_RMS:
                began = time.monotonic()
                try:
                    text = self._transcribe(audio)
                except Exception:
                    log.debug("Live-Wörter: Erkennung fehlgeschlagen", exc_info=True)
                    text = ""
                spent += time.monotonic() - began
                runs += 1
                if not self._current(generation):
                    break
                words = [w for w in fragments(text) if w not in recent]
                if words:
                    recent.extend(words)
                    shown += len(words)
                    try:
                        self._on_words(words)
                    except Exception:
                        log.debug("Live-Wörter: Anzeige nahm die Wörter nicht an", exc_info=True)
            if stop.wait(PAUSE_S):
                break
        if runs:
            log.info("Live-Wörter: %d Läufe, %d Fetzen, im Mittel %.2f s je Lauf", runs, shown, spent / runs)
