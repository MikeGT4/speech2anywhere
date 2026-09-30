from __future__ import annotations
import asyncio
import logging
import sys
import threading
import time
from enum import Enum, auto
from typing import Callable
import numpy as np
from kira.config import Config
from kira.recorder import Recorder, DeviceUnavailable, SAMPLE_RATE

if sys.platform == "win32":
    from kira.transcriber_fw import TranscriptionResult
    from kira.context_win import detect_mode
    from kira.edit_command import ClipboardUnavailable, read_selection
else:
    from kira.transcriber import TranscriptionResult
    from kira.context import detect_mode

    class ClipboardUnavailable(RuntimeError):  # type: ignore[no-redef]
        pass

    def read_selection() -> str | None:  # type: ignore[misc]
        return None

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    STYLING = auto()
    INJECTING = auto()
    ERROR = auto()


class KiraApp:
    def __init__(
        self,
        config: Config,
        recorder: Recorder,
        transcriber,
        styler,
        injector,
        on_state_change: Callable[[State], None] = lambda s: None,
        learning=None,
    ) -> None:
        self._config = config
        self._recorder = recorder
        self._transcriber = transcriber
        self._styler = styler
        self._injector = injector
        self._on_state_change = on_state_change
        self._learning = learning
        self._state = State.IDLE
        self._press_time: float | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._edit_mode: bool = False
        self._captured_selection: str | None = None
        self.last_transcript: str = ""
        self.last_polished: str = ""
        self.last_error: str = ""

    @classmethod
    def for_test(cls) -> "KiraApp":
        cfg = Config()
        return cls(
            config=cfg,
            recorder=Recorder(),
            transcriber=_StubTranscriber(),
            styler=_StubStyler(cfg),
            injector=_StubInjector(),
        )

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def state(self) -> State:
        return self._state

    def _set_state(self, s: State) -> None:
        self._state = s
        try:
            self._on_state_change(s)
        except Exception:
            log.exception("state change handler raised")

    def on_hotkey_press(self) -> None:
        if self._state != State.IDLE:
            return
        self._press_time = time.monotonic()
        self.last_transcript = ""
        self.last_polished = ""
        self.last_error = ""
        try:
            self._recorder.start()
        except DeviceUnavailable as e:
            log.warning("Hotkey press but input device unavailable: %s", e)
            self._press_time = None
            self.last_error = "Mikrofon nicht gefunden.|Gerät prüfen, dann erneut drücken."
            self._set_state(State.ERROR)
            threading.Timer(
                3.0, lambda: self._set_state(State.IDLE)
                if self._state == State.ERROR else None
            ).start()
            return
        self._set_state(State.RECORDING)

    def on_edit_press(self) -> None:
        if self._state != State.IDLE:
            return
        try:
            selection = read_selection()
        except ClipboardUnavailable as exc:
            log.warning("Edit hotkey aborted (clipboard unavailable): %s", exc)
            self._flash_error_briefly("Zwischenablage nicht erreichbar.|Gleich noch einmal versuchen.")
            return
        if selection is None:
            log.info("Edit hotkey pressed without selection, flashing ERROR")
            self._flash_error_briefly("Nichts markiert.|Erst Text markieren, dann erneut.")
            return
        self._captured_selection = selection
        self._edit_mode = True
        self.on_hotkey_press()
        if self._state != State.RECORDING:
            self._edit_mode = False
            self._captured_selection = None

    def _flash_error_briefly(self, reason: str = "") -> None:
        if self._state != State.IDLE:
            return
        self.last_error = reason
        self._set_state(State.ERROR)
        threading.Timer(
            1.5, lambda: self._set_state(State.IDLE)
            if self._state == State.ERROR else None
        ).start()

    def on_hotkey_release(self, duration_ms: int | None = None) -> None:
        if self._state != State.RECORDING:
            return
        if duration_ms is None and self._press_time is not None:
            duration_ms = int((time.monotonic() - self._press_time) * 1000)
        self._press_time = None
        audio = self._recorder.stop()
        if (duration_ms or 0) < self._config.hotkey.min_duration_ms:
            self._edit_mode = False
            self._captured_selection = None
            self._set_state(State.IDLE)
            return
        if self._loop is None:
            log.warning("no event loop set, running pipeline synchronously via new loop")
            asyncio.run(self._run_pipeline(audio))
            return
        if not self._loop.is_running():
            log.warning("event loop not running, pipeline dropped, resetting to IDLE")
            self._set_state(State.IDLE)
            return
        asyncio.run_coroutine_threadsafe(self._run_pipeline(audio), self._loop)

    async def _run_pipeline(self, audio: np.ndarray) -> None:
        edit_mode = self._edit_mode
        captured_selection = self._captured_selection
        mode: str | None = None
        try:
            self._set_state(State.TRANSCRIBING)
            transcription = await asyncio.to_thread(
                self._transcriber.transcribe, audio
            )
            log.info(
                "Whisper out (%d chars, lang=%s): %r",
                len(transcription.text), transcription.language,
                transcription.text[:80],
            )
            if not transcription.text:
                log.warning("Whisper returned empty text, pipeline aborted before polish")
                self._set_state(State.IDLE)
                return
            self.last_transcript = transcription.text
            self._set_state(State.STYLING)
            if edit_mode and captured_selection:
                polished = await self._styler.edit_command(
                    selection=captured_selection,
                    command=transcription.text,
                )
                log.info(
                    "Edit-command out (sel=%d chars, cmd=%r, out=%d chars): %r",
                    len(captured_selection), transcription.text[:60],
                    len(polished), polished[:80],
                )
            else:
                mode = detect_mode(self._config)
                glossary = self._glossary_for(transcription.text)
                extra = {"glossary": glossary} if glossary else {}
                polished = await self._styler.polish(
                    transcription.text, mode=mode, **extra,
                )
                log.info(
                    "Polish out (mode=%s, %d chars): %r",
                    mode, len(polished), polished[:80],
                )
            if not polished:
                log.warning("Polish returned empty, skipping inject")
                return
            self.last_polished = polished
            self._set_state(State.INJECTING)
            self._injector.inject(polished)
            if mode is not None:
                self._record_dictation(mode, transcription, polished, audio)
        except Exception:
            log.exception("pipeline failed")
            self.last_error = "Verarbeitung fehlgeschlagen.|Details im Log."
            self._set_state(State.ERROR)
        finally:
            self._edit_mode = False
            self._captured_selection = None
            if self._state == State.ERROR:
                threading.Timer(
                    3.0, lambda: self._set_state(State.IDLE)
                    if self._state == State.ERROR else None
                ).start()
            else:
                self._set_state(State.IDLE)

    def _glossary_for(self, text: str) -> list[str] | None:
        if self._learning is None:
            return None
        try:
            return self._learning.glossary_for(text) or None
        except Exception:
            log.exception("Lernen: Glossar-Auswahl fehlgeschlagen, Diktat läuft ohne")
            return None

    def _record_dictation(self, mode: str, transcription, text: str, audio: np.ndarray) -> None:
        if self._learning is None:
            return
        try:
            self._learning.after_inject(
                mode=mode, transcription=transcription, text=text,
                duration_s=audio.size / SAMPLE_RATE,
            )
        except Exception:
            log.exception("Lernen: Verlaufseintrag fehlgeschlagen")


class _StubTranscriber:
    def transcribe(self, audio):
        return TranscriptionResult(text="stub", language="de")


class _StubStyler:
    def __init__(self, cfg): self.cfg = cfg
    async def polish(self, text, mode, glossary=None): return text


class _StubInjector:
    def __init__(self): self.last = None
    def inject(self, text): self.last = text
