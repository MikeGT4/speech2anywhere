# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import ctypes
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from kira.gpu_check import POLISH_GPU_MIB, WHISPER_GPU_MIB, _nvidia_smi_candidates
from kira.texte import decimal_mark, tr

log = logging.getLogger(__name__)

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

RESERVE_MIB = 1024
LARGE_CONTEXT_FROM_MIB = 23 * 1024
QUALITY_MODEL = "gemma4:12b"
FAST_MODEL = "gemma4:e4b"
CPU_POLISH_RAM_GB = 12.0
CPU_WHISPER_REPO = "Systran/faster-whisper-small"


def cpu_whisper_dir() -> Path:
    return Path.home() / "models" / "faster-whisper-small"


@dataclass(frozen=True)
class Measurement:
    gpu_name: str | None
    vram_total_mib: int
    vram_used_mib: int
    cpu_threads: int
    ram_total_gb: float

    @property
    def vram_free_mib(self) -> int:
        return max(0, self.vram_total_mib - self.vram_used_mib)


@dataclass(frozen=True)
class Recommendation:
    device: str
    fast_mode: bool
    reason: str


def _gb(mib: float) -> str:
    return f"{mib / 1024:.1f}".replace(".", decimal_mark())


def gpu_need_mib(model: str, vram_total_mib: int) -> int:
    small_context, large_context = POLISH_GPU_MIB[model]
    polish = large_context if vram_total_mib >= LARGE_CONTEXT_FROM_MIB else small_context
    return WHISPER_GPU_MIB + polish + RESERVE_MIB


def recommend(measured: Measurement) -> Recommendation:
    if measured.gpu_name is not None:
        free = measured.vram_free_mib
        if free >= gpu_need_mib(QUALITY_MODEL, measured.vram_total_mib):
            return Recommendation(
                "gpu", False,
                tr("Frei sind {} GB Grafikspeicher.\nDas reicht für Whisper large-v3 und gemma4:12b.").format(_gb(free)),
            )
        if free >= gpu_need_mib(FAST_MODEL, measured.vram_total_mib):
            return Recommendation(
                "gpu", True,
                tr("Frei sind {} GB Grafikspeicher.\nDas reicht für Whisper large-v3 und das schnelle Modell gemma4:e4b.").format(
                    _gb(free)
                ),
            )
        reason = tr("Frei sind nur {} GB Grafikspeicher, gebraucht werden mindestens {} GB.\nDer Prozessor ist hier die bessere Wahl.").format(
            _gb(free), _gb(gpu_need_mib(FAST_MODEL, measured.vram_total_mib))
        )
    else:
        reason = tr("Ohne NVIDIA-Karte rechnet Speech2Anywhere auf dem Prozessor.")
    if 0 < measured.ram_total_gb < CPU_POLISH_RAM_GB:
        reason += tr("\nMit {} GB Arbeitsspeicher kann die Politur stocken.\nAbschalten kannst du sie in den Einstellungen.").format(
            f"{measured.ram_total_gb:.0f}"
        )
    return Recommendation("cpu", False, reason)


def _query_gpu() -> tuple[str, int, int] | None:
    for executable in _nvidia_smi_candidates():
        try:
            output = subprocess.run(  # noqa: S603
                [executable, "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5.0, check=True, stdin=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
            ).stdout.strip()
        except Exception as exc:  # noqa: BLE001
            log.info("nvidia-smi %s nicht nutzbar: %r", executable, exc)
            continue
        first = output.splitlines()[0] if output else ""
        match = re.match(r"^(.+?),\s*(\d+),\s*(\d+|\[N/A\])\s*$", first)
        if match:
            used = 0 if match.group(3).startswith("[") else int(match.group(3))
            return match.group(1).strip(), int(match.group(2)), used
        log.info("nvidia-smi %s meldet unerwartet: %r", executable, first)
    return None


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def ram_total_gb() -> float:
    if sys.platform != "win32":
        return 0.0
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0.0
    return status.ullTotalPhys / 1024 ** 3


def measure(samples: int = 3, pause_s: float = 1.0) -> Measurement:
    readings = []
    for index in range(samples):
        reading = _query_gpu()
        if reading is None:
            break
        readings.append(reading)
        if index + 1 < samples:
            time.sleep(pause_s)
    threads = os.cpu_count() or 1
    ram = ram_total_gb()
    if not readings:
        measured = Measurement(None, 0, 0, threads, ram)
    else:
        name, total, _used = readings[0]
        measured = Measurement(name, total, min(reading[2] for reading in readings), threads, ram)
    log.info("Rechner gemessen: %s", measured)
    return measured
