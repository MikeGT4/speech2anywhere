# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import types

from kira import hardware
from kira.hardware import Measurement, recommend


def _measured(name="NVIDIA GeForce RTX 4070", total=12282, used=700, threads=16, ram=32.0):
    return Measurement(gpu_name=name, vram_total_mib=total, vram_used_mib=used, cpu_threads=threads, ram_total_gb=ram)


def test_no_nvidia_card_means_processor():
    rec = recommend(_measured(name=None, total=0, used=0))
    assert (rec.device, rec.fast_mode) == ("cpu", False)
    assert "Ohne NVIDIA-Karte" in rec.reason


def test_large_card_gets_the_quality_model():
    rec = recommend(_measured(name="NVIDIA GeForce RTX 5090", total=32607, used=1500))
    assert (rec.device, rec.fast_mode) == ("gpu", False)


def test_sixteen_gigabyte_card_still_fits_the_quality_model():
    rec = recommend(_measured(total=16376, used=900))
    assert (rec.device, rec.fast_mode) == ("gpu", False)


def test_twelve_gigabyte_card_gets_the_fast_model():
    rec = recommend(_measured(total=12282, used=700))
    assert (rec.device, rec.fast_mode) == ("gpu", True)


def test_eight_gigabyte_card_runs_on_the_processor():
    rec = recommend(_measured(total=8188, used=600))
    assert (rec.device, rec.fast_mode) == ("cpu", False)


def test_busy_card_counts_only_the_free_memory():
    rec = recommend(_measured(total=16376, used=7000))
    assert (rec.device, rec.fast_mode) == ("cpu", False)


def test_large_cards_reckon_with_the_bigger_default_context():
    assert hardware.gpu_need_mib("gemma4:12b", 24576) == 4315 + 9448 + 1024
    assert hardware.gpu_need_mib("gemma4:12b", 16376) == 4315 + 8763 + 1024
    assert hardware.gpu_need_mib("gemma4:e4b", 12282) == 4315 + 4650 + 1024


def test_little_memory_is_mentioned_on_the_processor():
    assert "Arbeitsspeicher" in recommend(_measured(name=None, total=0, used=0, ram=8.0)).reason
    assert "Arbeitsspeicher" not in recommend(_measured(name=None, total=0, used=0, ram=32.0)).reason


def test_measure_reads_name_total_and_the_lowest_use(monkeypatch):
    outputs = iter(["NVIDIA GeForce RTX 4070, 12282, 900\n", "NVIDIA GeForce RTX 4070, 12282, 700\n",
                    "NVIDIA GeForce RTX 4070, 12282, 800\n"])
    monkeypatch.setattr(hardware, "_nvidia_smi_candidates", lambda: ["nvidia-smi"])
    monkeypatch.setattr(hardware.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=next(outputs)))
    monkeypatch.setattr(hardware, "ram_total_gb", lambda: 32.0)
    measured = hardware.measure(pause_s=0)
    assert (measured.gpu_name, measured.vram_total_mib, measured.vram_used_mib) == ("NVIDIA GeForce RTX 4070", 12282, 700)
    assert measured.ram_total_gb == 32.0
    assert measured.cpu_threads >= 1


def test_measure_without_nvidia_smi_finds_no_card(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(hardware, "_nvidia_smi_candidates", lambda: ["nvidia-smi"])
    monkeypatch.setattr(hardware.subprocess, "run", missing)
    monkeypatch.setattr(hardware, "ram_total_gb", lambda: 16.0)
    measured = hardware.measure(pause_s=0)
    assert (measured.gpu_name, measured.vram_total_mib, measured.vram_used_mib) == (None, 0, 0)


def test_unknown_memory_use_still_counts_the_card(monkeypatch):
    monkeypatch.setattr(hardware, "_nvidia_smi_candidates", lambda: ["nvidia-smi"])
    monkeypatch.setattr(hardware.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout="NVIDIA RTX A2000, 12282, [N/A]\n"))
    monkeypatch.setattr(hardware, "ram_total_gb", lambda: 16.0)
    measured = hardware.measure(samples=1, pause_s=0)
    assert (measured.gpu_name, measured.vram_total_mib, measured.vram_used_mib) == ("NVIDIA RTX A2000", 12282, 0)


def test_measuring_opens_no_console_window(monkeypatch):
    seen = {}

    def run(*args, **kwargs):
        seen.update(kwargs)
        return types.SimpleNamespace(stdout="NVIDIA GeForce RTX 4070, 12282, 700\n")

    monkeypatch.setattr(hardware, "_nvidia_smi_candidates", lambda: ["nvidia-smi"])
    monkeypatch.setattr(hardware.subprocess, "run", run)
    monkeypatch.setattr(hardware, "ram_total_gb", lambda: 16.0)
    hardware.measure(samples=1, pause_s=0)
    assert seen["creationflags"] == getattr(hardware.subprocess, "CREATE_NO_WINDOW", 0)
