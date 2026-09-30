from __future__ import annotations
import logging
import threading
import time
import pyperclip
import keyboard

log = logging.getLogger(__name__)

_LONG_TEXT_THRESHOLD = 80
_PER_CHAR_PASTE_MS = 2
_PASTE_OVERHEAD_MS = 100


class Injector:
    def __init__(self, restore_after_ms: int = 500) -> None:
        self._restore_after_ms = restore_after_ms
        self._lock = threading.Lock()
        self._restore_gen = 0
        self._pending_original: str | None = None

    def _effective_restore_ms(self, text_len: int) -> int:
        if text_len <= _LONG_TEXT_THRESHOLD:
            return self._restore_after_ms
        return max(
            self._restore_after_ms,
            _PASTE_OVERHEAD_MS + text_len * _PER_CHAR_PASTE_MS,
        )

    def inject(self, text: str) -> None:
        if not text:
            return
        delay_ms = self._effective_restore_ms(len(text))
        log.info(
            "Injecting %d chars (restore in %d ms): %r",
            len(text), delay_ms, text[:80],
        )
        with self._lock:
            self._restore_gen += 1
            gen = self._restore_gen
            if self._pending_original is None:
                try:
                    self._pending_original = pyperclip.paste()
                except Exception:
                    self._pending_original = ""
                    log.warning("pyperclip.paste failed, restore will be empty")
        try:
            pyperclip.copy(text)
        except Exception:
            log.exception("pyperclip.copy failed")
            return
        time.sleep(0.02)
        try:
            keyboard.send("ctrl+v")
        except Exception:
            log.exception("keyboard.send(ctrl+v) failed")

        def restore():
            with self._lock:
                if gen != self._restore_gen:
                    return
                saved = self._pending_original
                self._pending_original = None
            try:
                pyperclip.copy(saved if saved is not None else "")
            except Exception:
                log.warning("failed to restore clipboard")

        threading.Timer(delay_ms / 1000.0, restore).start()
