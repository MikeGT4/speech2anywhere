from __future__ import annotations
import logging
import threading
from typing import Callable
import keyboard

log = logging.getLogger(__name__)

SUPPORTED_COMBOS = {"f8", "f9"}


class HotkeyListener:
    def __init__(
        self,
        combo: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        if combo not in SUPPORTED_COMBOS:
            raise ValueError(
                f"Unsupported combo: {combo}. "
                f"Supported: {sorted(SUPPORTED_COMBOS)}"
            )
        self._combo = combo
        self._on_press = on_press
        self._on_release = on_release
        self._active = False
        self._started = False
        self._lock = threading.Lock()
        self._hook_handles: list = []

    def _handle_press(self, _event) -> None:
        with self._lock:
            if self._active:
                return
            self._active = True
        try:
            self._on_press()
        except Exception:
            log.exception("on_press raised")

    def _handle_release(self, _event) -> None:
        with self._lock:
            if not self._active:
                return
            self._active = False
        try:
            self._on_release()
        except Exception:
            log.exception("on_release raised")

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            h1 = keyboard.on_release_key(self._combo, self._handle_release, suppress=False)
            h2 = keyboard.on_press_key(self._combo, self._handle_press, suppress=False)
            self._hook_handles = [h1, h2]
            self._started = True
            log.info("HotkeyListener running (combo=%s, pass-through)", self._combo)

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            for h in self._hook_handles:
                try:
                    keyboard.unhook(h)
                except Exception:
                    log.exception("keyboard.unhook raised for handle %r", h)
            self._hook_handles = []
            self._started = False
