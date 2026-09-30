# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import math

import numpy as np

SAMPLE_RATE = 16000
PLAYBACK_DELAY = 2000
CATCH_UP = int(0.25 * SAMPLE_RATE)
CLIP_LEVEL = 0.99
CLIP_HOLD_S = 0.7
CLIP_ONSET_GAP_S = 0.35
SILENT_AFTER_S = 0.6
SILENT_RMS = 0.0004
SIGNAL_BACK_RMS = 0.0015
STALL_S = 0.35
VOICE_RMS = 0.02
VOICE_ON_S = 0.08
VOICE_OFF_S = 1.2
LEVEL_FLOOR_DB = -48.0
FFT_N = 256
BIN_HZ = SAMPLE_RATE / FFT_N

_HANN = np.hanning(FFT_N).astype(np.float32)


def level_of(peak: float) -> float:
    db = 20.0 * math.log10(peak + 1e-6)
    return min(1.0, max(0.0, (db - LEVEL_FLOOR_DB) / -LEVEL_FLOOR_DB))


class SignalTap:
    def __init__(self, capacity: int = SAMPLE_RATE * 4) -> None:
        self._buf = np.zeros(capacity, dtype=np.float32)
        self._cap = capacity
        self.total = 0
        self._head = 0.0
        self.stall = 0.0

    def push(self, block) -> None:
        a = np.asarray(block, dtype=np.float32).reshape(-1)
        n = a.size
        if n == 0:
            return
        if n > self._cap:
            self.total += n - self._cap
            a = a[-self._cap:]
            n = self._cap
        start = self.total % self._cap
        first = min(n, self._cap - start)
        self._buf[start:start + first] = a[:first]
        if first < n:
            self._buf[:n - first] = a[first:]
        self.total += n

    def start(self) -> None:
        self._head = float(max(0, self.total - PLAYBACK_DELAY))
        self.stall = 0.0

    def advance(self, dt: float) -> None:
        self._head += dt * SAMPLE_RATE
        target = self.total - PLAYBACK_DELAY
        if self._head < target - CATCH_UP:
            self._head = float(target)
        if self._head >= self.total:
            self._head = float(self.total)
            self.stall += dt
        else:
            self.stall = 0.0

    @property
    def position(self) -> int:
        return int(self._head)

    def tail(self, n: int, end: int | None = None) -> np.ndarray:
        end = self.position if end is None else end
        out = np.zeros(n, dtype=np.float32)
        lo = max(end - n, self.total - self._cap, 0)
        if end <= lo:
            return out
        idx = np.arange(lo, end) % self._cap
        out[n - (end - lo):] = self._buf[idx]
        return out


class SignalAnalysis:
    def __init__(self) -> None:
        self.spectrum = np.zeros(FFT_N // 2 + 1, dtype=np.float32)
        self.reset(0.0)

    def reset(self, t: float) -> None:
        self.level = 0.0
        self.peak = 0.0
        self.rms = 0.0
        self.db = -120.0
        self._db_t = -9.0
        self.clip = False
        self.clip_onset = -9.0
        self._clip_until = -9.0
        self._last_clip = -9.0
        self.silent = False
        self.voice = False
        self._voice_since = -1.0
        self._quiet_since = t
        self.onsets: list[tuple[float, float]] = []
        self._hist: list[tuple[float, float]] = []
        self._last_onset = -9.0
        self.spectrum[:] = 0.0

    def update(self, tap: SignalTap, t: float, dt: float, *, recording: bool,
               rec_elapsed: float) -> None:
        b = tap.tail(9600)
        pk = float(np.abs(b[-800:]).max())
        rms = float(np.sqrt(np.mean(b[-1600:] ** 2)))
        rms600 = float(np.sqrt(np.mean(b ** 2)))
        self.peak, self.rms = pk, rms

        target = level_of(pk)
        tau = 0.03 if target > self.level else 0.28
        self.level += (target - self.level) * (1.0 - math.exp(-dt / tau))

        self._hist.append((t, self.level))
        while self._hist and self._hist[0][0] < t - 0.08:
            self._hist.pop(0)
        if (recording and self._hist and self.level - self._hist[0][1] > 0.16
                and t - self._last_onset > 0.12):
            self.onsets.append((t, min(1.0, max(0.35, self.level))))
            self._last_onset = t
            if len(self.onsets) > 32:
                del self.onsets[:-32]

        if pk >= CLIP_LEVEL:
            if t - self._last_clip > CLIP_ONSET_GAP_S:
                self.clip_onset = t
            self._last_clip = t
            self._clip_until = t + CLIP_HOLD_S
        self.clip = t < self._clip_until

        if recording:
            stalled = tap.stall > STALL_S
            if rec_elapsed > SILENT_AFTER_S and (rms600 < SILENT_RMS or stalled):
                self.silent = True
            if rms > SIGNAL_BACK_RMS and not stalled:
                self.silent = False
        else:
            self.silent = False

        if rms > VOICE_RMS:
            if self._voice_since < 0:
                self._voice_since = t
            if t - self._voice_since >= VOICE_ON_S:
                self.voice = True
            self._quiet_since = t
        else:
            self._voice_since = -1.0
            if t - self._quiet_since > VOICE_OFF_S:
                self.voice = False

        db = 20.0 * math.log10(pk + 1e-9)
        if db >= self.db or t - self._db_t > 1.0:
            self.db = db
            self._db_t = t

        seg = b[-FFT_N:] * _HANN
        mag = np.abs(np.fft.rfft(seg)) * 4.0 / FFT_N
        self.spectrum[:] = np.clip((20.0 * np.log10(mag + 1e-9) + 74.0) / 64.0, 0.0, 1.0)

    def at(self, freq: float) -> float:
        return float(np.interp(freq / BIN_HZ, np.arange(self.spectrum.size), self.spectrum))

    def band(self, f0: float, f1: float) -> float:
        b0 = int(f0 // BIN_HZ)
        b1 = min(self.spectrum.size - 1, int(math.ceil(f1 / BIN_HZ)))
        return max(float(self.spectrum[b0:b1 + 1].max()), self.at((f0 + f1) / 2))
