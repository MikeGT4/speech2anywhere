from __future__ import annotations
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)


_WHISPER_VRAM_GB: dict[str, float] = {
    "large-v3-turbo": 1.6,
    "large-v3": 3.0,
    "large-v2": 3.0,
    "large": 3.0,
    "medium": 1.0,
    "small": 0.5,
    "base": 0.3,
    "tiny": 0.1,
}

_OLLAMA_VRAM_GB: dict[str, float] = {
    "llama3.3:70b": 40.0,
    "gemma4:26b": 16.0,
    "gemma3:27b": 16.0,
    "gemma2:27b": 16.0,
    "qwen3:14b": 8.5,
    "gemma4:12b": 7.5,
    "gemma3:12b": 7.0,
    "gemma2:9b": 5.5,
    "qwen3:8b": 5.0,
    "llama3.1:8b": 5.0,
    "llama3:8b": 5.0,
    "qwen3:4b": 2.5,
    "gemma4:e4b": 3.0,
    "gemma3:4b": 2.5,
    "llama3.2:3b": 2.0,
    "gemma2:2b": 1.5,
    "gemma3:1b": 1.0,
    "llama3.2:1b": 1.0,
}


@dataclass(frozen=True)
class GpuInfo:
    name: str
    vram_gb: float
    cuda_available: bool


@dataclass(frozen=True)
class VramAssessment:
    status: Literal["ok", "tight", "insufficient", "no_gpu"]
    gpu: GpuInfo | None
    whisper_model: str
    whisper_vram_gb: float
    polish_model: str
    polish_vram_gb: float
    total_required_gb: float
    headroom_gb: float
    message: str


def _nvidia_smi_candidates() -> list[str]:
    candidates = []
    windir = os.environ.get("WINDIR") or "C:\\Windows"
    candidates.append(str(Path(windir) / "System32" / "nvidia-smi.exe"))
    candidates.append(
        "C:\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe"
    )
    return candidates


def detect_gpu() -> GpuInfo | None:
    result = None
    for executable in _nvidia_smi_candidates():
        exists = os.path.exists(executable)
        try:
            result = subprocess.run(  # noqa: S603 - list-args, kein shell
                [
                    executable,
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=30.0,
                check=True,
                stdin=subprocess.DEVNULL,
            )
            log.info("nvidia-smi OK via %s", executable)
            break
        except Exception as exc:  # noqa: BLE001 - jeder Fehlschlag soll ins Log
            log.warning(
                "nvidia-smi-Kandidat gescheitert: %s "
                "(os.path.exists=%s) -> %r",
                executable, exists, exc,
            )
            continue
    else:
        log.warning(
            "nvidia-smi nicht verfügbar, alle %d Kandidaten gescheitert",
            len(_nvidia_smi_candidates()),
        )
        return None

    output = result.stdout.strip()
    if not output:
        return None
    first_line = output.splitlines()[0]
    match = re.match(r"^(.+?),\s*(\d+)\s*MiB\s*$", first_line)
    if not match:
        log.warning("nvidia-smi output unparseable: %r", first_line)
        return None
    name = match.group(1).strip()
    vram_mib = int(match.group(2))
    return GpuInfo(
        name=name, vram_gb=round(vram_mib / 1024.0, 1), cuda_available=True,
    )


def estimate_whisper_vram(model_name: str) -> float:
    name = model_name.lower().strip().replace("\\", "/")
    name = name.rsplit("/", 1)[-1]
    if name.startswith("faster-whisper-"):
        name = name[len("faster-whisper-"):]
    elif name.startswith("whisper-"):
        name = name[len("whisper-"):]
    for prefix, gb in _WHISPER_VRAM_GB.items():
        if name.startswith(prefix):
            return gb
    return 2.0


def estimate_polish_vram(model_name: str) -> float:
    name = model_name.lower().strip()
    for key, gb in _OLLAMA_VRAM_GB.items():
        if key in name:
            return gb
    match = re.search(r":(\d+(?:\.\d+)?)b\b", name)
    if match:
        params_b = float(match.group(1))
        return round(params_b * 0.6, 1)
    return 4.0


def _suggest_smaller_polish(current: str) -> str:
    name = current.lower()
    if "gemma" in name:
        return "gemma2:2b"
    if "llama" in name:
        return "llama3.2:3b"
    if "qwen" in name:
        return "qwen3:4b"
    return "gemma2:2b"


def assess(whisper_model: str, polish_model: str) -> VramAssessment:
    gpu = detect_gpu()
    w_vram = estimate_whisper_vram(whisper_model)
    p_vram = estimate_polish_vram(polish_model)
    total = round(w_vram + p_vram, 1)

    if gpu is None:
        return VramAssessment(
            status="no_gpu",
            gpu=None,
            whisper_model=whisper_model,
            whisper_vram_gb=w_vram,
            polish_model=polish_model,
            polish_vram_gb=p_vram,
            total_required_gb=total,
            headroom_gb=0.0,
            message=(
                "Keine NVIDIA-GPU erkannt.\n\n"
                "Speech2Anywhere ist für NVIDIA-Grafikkarten mit CUDA gebaut. "
                f"Geschätzter Bedarf: rund {total:.1f} GB Grafikspeicher "
                f"({whisper_model} + {polish_model}).\n\n"
                "Nur mit dem Prozessor wäre die Spracherkennung etwa zehnmal langsamer "
                "und das Sprachmodell kaum nutzbar. Grafik von AMD oder Intel wird "
                "nicht unterstützt (nvidia-smi nicht gefunden)."
            ),
        )

    headroom = round(gpu.vram_gb - total, 1)
    common = (
        f"GPU: {gpu.name}\n"
        f"Grafikspeicher: {gpu.vram_gb:.1f} GB\n\n"
        f"Spracherkennung ({whisper_model}): ~{w_vram:.1f} GB\n"
        f"Sprachmodell ({polish_model}): ~{p_vram:.1f} GB\n"
        f"Summe: ~{total:.1f} GB\n"
        f"Reserve: {headroom:+.1f} GB\n\n"
    )

    if headroom >= 2.0:
        return VramAssessment(
            status="ok", gpu=gpu,
            whisper_model=whisper_model, whisper_vram_gb=w_vram,
            polish_model=polish_model, polish_vram_gb=p_vram,
            total_required_gb=total, headroom_gb=headroom,
            message="Das passt mit Komfort: Deine Grafikkarte hat genug Speicher.\n\n" + common + (
                "Genug Reserve für Desktop, Browser und leichte Last auf der Grafikkarte nebenher."
            ),
        )
    if headroom >= 0.5:
        return VramAssessment(
            status="tight", gpu=gpu,
            whisper_model=whisper_model, whisper_vram_gb=w_vram,
            polish_model=polish_model, polish_vram_gb=p_vram,
            total_required_gb=total, headroom_gb=headroom,
            message="Knapp, aber es geht.\n\n" + common + (
                "Es klappt, solange nichts anderes die Grafikkarte stark belastet "
                "(Spiele, viele Browserfenster mit Grafikbeschleunigung, Bildgeneratoren). "
                "Beim Kaltstart kann der Speicher ausgehen.\n\n"
                "Empfehlung: ein kleineres Sprachmodell wählen."
            ),
        )
    suggestion = _suggest_smaller_polish(polish_model)
    return VramAssessment(
        status="insufficient", gpu=gpu,
        whisper_model=whisper_model, whisper_vram_gb=w_vram,
        polish_model=polish_model, polish_vram_gb=p_vram,
        total_required_gb=total, headroom_gb=headroom,
        message="Nicht genug Grafikspeicher.\n\n" + common + (
            f"Empfehlung: Sprachmodell wechseln auf '{suggestion}' "
            f"(~{estimate_polish_vram(suggestion):.1f} GB statt ~{p_vram:.1f} GB). "
            f"Die Spracherkennung ({whisper_model}) kann bleiben."
        ),
    )
