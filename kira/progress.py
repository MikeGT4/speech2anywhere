# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

STARTING = "startet …"
PREPARING = "wird vorbereitet …"
FINISHING = "wird abgeschlossen …"
SCALE = 1000
RESUME_SHARE = 0.25
KB = 1000
MB = 1000 ** 2
GB = 1000 ** 3

PULL_PHASES = {
    "pulling manifest": STARTING,
    "verifying sha256 digest": "Prüfsumme wird geprüft …",
    "writing manifest": "Modell wird eingetragen …",
    "removing any unused layers": "wird aufgeräumt …",
    "removing unused layers": "wird aufgeräumt …",
}
SUCCESS = "success"
FINAL_STATUSES = frozenset({"verifying sha256 digest", "writing manifest", SUCCESS})


class Cancelled(Exception):
    pass


def bar_scale(done: float, total: float) -> tuple[int, int]:
    if total <= 0:
        return (0, 0)
    safe = max(0.0, min(float(done), float(total)))
    value = round(safe / total * SCALE)
    if safe < total:
        value = min(value, SCALE - 1)
    return (SCALE, value)


def percent(done: float, total: float) -> int:
    if total <= 0:
        return 0
    return int(max(0.0, min(float(done), float(total))) * 100 // total)


def _number(value: float, digits: int) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _unit(total: float) -> tuple[int, str, int]:
    if total >= GB:
        return GB, "GB", 1
    if total >= MB:
        return MB, "MB", 0 if total >= 100 * MB else 1
    return KB, "KB", 0 if total >= 100 * KB else 1


def size_text(done: float, total: float) -> str:
    unit, name, digits = _unit(total)
    shown = max(0.0, min(float(done), float(total)))
    return f"{_number(shown / unit, digits)} von {_number(total / unit, digits)} {name}"


def total_text(total: float) -> str:
    unit, name, digits = _unit(total)
    return f"{_number(total / unit, digits)} {name}"


def clock_text(seconds: float) -> str:
    whole = max(0, int(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def time_text(done: float, total: float) -> str:
    return f"{clock_text(min(done, total))} von {clock_text(total)}"


def running_text(seconds: float) -> str:
    return f"läuft seit {clock_text(seconds)}"


def rate_text(per_second: float) -> str:
    if per_second >= MB:
        value = per_second / MB
        return f"{_number(value, 1 if value < 100 else 0)} MB/s"
    return f"{_number(per_second / KB, 0)} KB/s"


def eta_text(seconds: float) -> str:
    if seconds < 60:
        return "noch unter einer Minute"
    minutes = round(seconds / 60)
    if minutes == 1:
        return "noch etwa 1 Minute"
    if minutes < 100:
        return f"noch etwa {minutes} Minuten"
    return f"noch etwa {round(seconds / 3600)} Stunden"


class RateMeter:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        warmup: float = 2.0,
        span: float = 3.0,
        window: float = 10.0,
        stall: float | None = 15.0,
    ) -> None:
        self._clock = clock
        self._warmup = warmup
        self._span = span
        self._window = window
        self._stall = stall
        self._start: float | None = None
        self._changed: float | None = None
        self._last: float | None = None
        self._recent: float | None = None
        self._samples: deque[tuple[float, float]] = deque()

    def add(self, done: float) -> None:
        now = self._clock()
        if self._start is None:
            self._start = now
        changed = done != self._last
        if changed:
            if self._resumed_from_standstill(now, done):
                self._samples.clear()
                self._recent = None
            self._last = done
            self._changed = now
        if now - self._start < self._warmup:
            return
        self._samples.append((now, float(done)))
        while len(self._samples) > 2 and now - self._samples[1][0] >= self._window:
            self._samples.popleft()
        if changed:
            self._recent = self._flow() or self._recent

    def _resumed_from_standstill(self, now: float, done: float) -> bool:
        if not self._stalled_at(now) or self._recent is None or self._last is None:
            return False
        return (done - self._last) / (now - self._changed) < self._recent * RESUME_SHARE

    def elapsed(self) -> float:
        if self._start is None:
            return 0.0
        return max(0.0, self._clock() - self._start)

    def starting(self) -> bool:
        return self.elapsed() < self._warmup + self._span

    def stalled(self) -> bool:
        return self._stalled_at(self._clock())

    def _stalled_at(self, now: float) -> bool:
        if self._stall is None or self._changed is None:
            return False
        return now - self._changed >= self._stall

    def rate(self) -> float | None:
        if self.stalled():
            return None
        return self._flow()

    def _flow(self) -> float | None:
        if len(self._samples) < 2:
            return None
        (t0, d0), (t1, d1) = self._samples[0], self._samples[-1]
        if t1 - t0 < self._span or d1 <= d0:
            return None
        return (d1 - d0) / (t1 - t0)


def unmeasured(done: float, total: float, meter: RateMeter) -> bool:
    return meter.rate() is None and percent(done, total) == 0


def describe(
    done: float,
    total: float,
    meter: RateMeter,
    amount: Callable[[float, float], str] = size_text,
    with_rate: bool = True,
    total_only: Callable[[float], str] | None = total_text,
) -> str:
    if total_only is not None and unmeasured(done, total, meter):
        return f"{total_only(total)} · {running_text(meter.elapsed())}"
    parts = [amount(done, total), f"{percent(done, total)} %"]
    rate = meter.rate()
    if rate is None:
        parts.append(STARTING if meter.starting() else running_text(meter.elapsed()))
        return " · ".join(parts)
    if with_rate:
        parts.append(rate_text(rate))
    parts.append(eta_text(max(0.0, total - done) / rate))
    return " · ".join(parts)


class Throttle:
    def __init__(self, interval: float = 0.2, clock: Callable[[], float] = time.monotonic) -> None:
        self._interval = interval
        self._clock = clock
        self._last: float | None = None
        self._lock = threading.Lock()

    def due(self, force: bool = False) -> bool:
        now = self._clock()
        with self._lock:
            if force or self._last is None or now - self._last >= self._interval:
                self._last = now
                return True
            return False


def pull_fields(event) -> tuple[str, str, int, int]:
    def field(name: str):
        value = getattr(event, name, None)
        if value is None and isinstance(event, dict):
            value = event.get(name)
        return value

    return (
        str(field("status") or ""),
        str(field("digest") or ""),
        int(field("completed") or 0),
        int(field("total") or 0),
    )


class PullTracker:
    def __init__(self, expected: int = 0) -> None:
        self._layers: dict[str, tuple[int, int]] = {}
        self._expected = max(0, int(expected))

    @property
    def started(self) -> bool:
        return bool(self._layers)

    def feed(self, key: str, completed: int, total: int) -> tuple[int, int]:
        if total <= 0:
            return (0, 0)
        self._layers[key] = (max(0, min(completed, total)), total)
        return self._sums()

    def complete(self) -> tuple[int, int]:
        self._layers = {key: (size, size) for key, (_, size) in self._layers.items()}
        _, size = self._sums()
        return (size, size)

    def _sums(self) -> tuple[int, int]:
        done = sum(done for done, _ in self._layers.values())
        size = sum(size for _, size in self._layers.values())
        return (done, max(size, self._expected))


def final_status(status: str) -> bool:
    return status.strip().lower() in FINAL_STATUSES


def pull_phase(status: str, started: bool) -> str:
    known = PULL_PHASES.get(status.strip().lower())
    if known is not None:
        return known
    return FINISHING if started else PREPARING


def byte_progress_class(report: Callable[[int, int], None]):
    from tqdm.auto import tqdm

    lock = threading.Lock()

    class ByteProgress(tqdm):
        monitor_interval = 0

        def __init__(self, *args, **kwargs) -> None:
            self._counts = kwargs.get("unit") == "B"
            self._done = 0.0
            kwargs.pop("name", None)
            kwargs["disable"] = True
            super().__init__(*args, **kwargs)

        def update(self, n=1):
            if not self._counts or not n:
                return None
            with lock:
                self._done += n
                done = self._done
            report(int(done), int(self.total or 0))
            return None

        def refresh(self, *args, **kwargs):
            if self._counts:
                report(int(self._done), int(self.total or 0))
            return None

    return ByteProgress
