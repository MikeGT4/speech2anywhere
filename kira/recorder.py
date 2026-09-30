from __future__ import annotations
import logging
import os
import threading
import wave
from collections import deque
from pathlib import Path
from typing import Callable
import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"
PREROLL_MS = 250
PREROLL_SAMPLES = SAMPLE_RATE * PREROLL_MS // 1000

_AUDIO_DUMP_ENABLED = os.environ.get("KIRA_AUDIO_DUMP", "1") == "1"


def _dump_wav(audio: np.ndarray) -> Path | None:
    if not _AUDIO_DUMP_ENABLED or audio.size == 0:
        return None
    base = os.environ.get("LOCALAPPDATA")
    if base is None:
        return None
    out_dir = Path(base) / "Kira"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "last_recording.wav"
        int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(int16.tobytes())
        return out_path
    except Exception:
        log.exception("WAV dump failed")
        return None


class DeviceUnavailable(RuntimeError):
    pass


class Recorder:
    def __init__(
        self,
        input_gain: float = 1.0,
        input_device: int | str | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._buffer: list[np.ndarray] = []
        self._preroll: deque[np.ndarray] = deque()
        self._preroll_samples = 0
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._on_level: Callable[[float], None] | None = None
        self._on_samples: Callable[[np.ndarray], None] | None = None
        self._input_gain = float(input_gain)
        self._device_spec = input_device
        self._input_device: int | None = None
        self._stream_dirty = False

    def _resolve_device(self) -> int | None:
        spec = self._device_spec
        if spec is None:
            return None
        if isinstance(spec, int):
            log.info("Recorder pinned to device id=%d", spec)
            return spec
        try:
            devices = list(sd.query_devices())
        except Exception:
            log.exception(
                "sd.query_devices() failed during resolve "
                "(audio service mid-disconnect?); treating as unavailable",
            )
            return None
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0 and spec.lower() in d["name"].lower():
                log.info(
                    "Recorder pinned to device id=%d (%r matched %r)",
                    i, spec, d["name"],
                )
                return i
        available = [
            f"{i}:{d['name']}"
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]
        log.warning(
            "audio.input_device=%r matched no input device. Available: %s",
            spec, available,
        )
        return None

    def set_level_callback(self, cb: Callable[[float], None] | None) -> None:
        self._on_level = cb

    def set_samples_callback(self, cb: Callable[[np.ndarray], None] | None) -> None:
        self._on_samples = cb

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            log.warning("sounddevice callback status: %s", status)
            if status.input_underflow:
                self._stream_dirty = True
        if self._input_gain != 1.0:
            audio = np.clip(indata * self._input_gain, -1.0, 1.0).astype(np.float32)
        else:
            audio = indata.copy()

        with self._lock:
            if self._recording:
                self._buffer.append(audio)
            else:
                self._preroll.append(audio)
                self._preroll_samples += len(audio)
                while self._preroll_samples > PREROLL_SAMPLES and self._preroll:
                    dropped = self._preroll.popleft()
                    self._preroll_samples -= len(dropped)

        if self._on_level is not None:
            try:
                rms = float(np.sqrt((audio ** 2).mean()))
                self._on_level(rms)
            except Exception:
                log.exception("level callback raised")

        if self._on_samples is not None:
            try:
                mono = audio[:, 0] if audio.ndim > 1 else audio
                self._on_samples(mono)
            except Exception:
                log.exception("samples callback raised")

    def prewarm(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            if self._input_device is None:
                self._input_device = self._resolve_device()
            if self._input_device is None and self._device_spec is not None:
                return
            try:
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    callback=self._callback,
                    blocksize=1600,
                    device=self._input_device,
                )
            except Exception:
                log.warning(
                    "prewarm: input stream open failed (device=%s)",
                    self._input_device, exc_info=True,
                )
                return
            self._stream = stream
        try:
            stream.start()
        except Exception:
            log.warning(
                "prewarm: input stream start failed (device=%s)",
                self._input_device, exc_info=True,
            )
            with self._lock:
                try:
                    stream.close()
                except Exception:
                    log.debug("prewarm: closing failed stream raised", exc_info=True)
                if self._stream is stream:
                    self._stream = None

    def _is_device_still_present(self) -> bool:
        if self._device_spec is None:
            return True
        if self._input_device is None:
            return False
        try:
            devices = list(sd.query_devices())
        except Exception:
            log.warning(
                "sd.query_devices() failed during health-check; "
                "treating pinned device as gone",
            )
            return False
        if self._input_device >= len(devices):
            return False
        return devices[self._input_device].get("max_input_channels", 0) > 0

    def _cycle_stream_if_unhealthy(self) -> bool:
        with self._lock:
            stream = self._stream
            dirty = self._stream_dirty
        if stream is None:
            return False
        try:
            active = bool(stream.active)
        except Exception:
            active = False
        device_present = self._is_device_still_present()
        if not dirty and active and device_present:
            return False
        log.warning(
            "Cycling input stream (dirty=%s active=%s device_present=%s), "
            "likely mic hot-unplug. Will re-resolve device on next start().",
            dirty, active, device_present,
        )
        self.close()
        self._input_device = None
        self._stream_dirty = False
        return True

    def start(self) -> None:
        self._cycle_stream_if_unhealthy()
        if self._stream is None:
            self._input_device = None
            self.prewarm()
            if self._stream is None:
                raise DeviceUnavailable(
                    f"audio.input_device={self._device_spec!r} "
                    f"not available right now"
                )
        with self._lock:
            self._buffer = list(self._preroll)
            self._preroll.clear()
            self._preroll_samples = 0
            self._recording = True

    def stop(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            if not self._buffer:
                log.warning("Recorder.stop: empty buffer (no audio captured)")
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._buffer, axis=0).reshape(-1).astype(np.float32)
            self._buffer.clear()
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0
        wav_path = _dump_wav(audio)
        log.info(
            "Recorder.stop: samples=%d duration=%.2fs peak=%.4f rms=%.4f gain=%.1f%s",
            audio.size, audio.size / SAMPLE_RATE, peak, rms, self._input_gain,
            f" wav={wav_path}" if wav_path else "",
        )
        return audio

    def close(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.exception("error closing input stream")

    @property
    def is_recording(self) -> bool:
        return self._recording
