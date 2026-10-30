# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Callable

from kira._resources import assets_dir
from kira.config import (
    DEFAULT_HUD_STYLE, DEFAULT_SOUND_EVENTS, HUD_STYLES, SOUND_EVENTS, default_config_path, load_config,
)

log = logging.getLogger(__name__)

STATE_SOUNDS = {"RECORDING": "start", "TRANSCRIBING": "stopp", "INJECTING": "fertig", "ERROR": "fehler"}
_UNREAD = object()


def _winsound_play(path: Path) -> None:
    import winsound

    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


class SoundPlayer:
    def __init__(
        self,
        config_path: Path | None = None,
        sounds_dir: Path | None = None,
        play: Callable[[Path], None] | None = None,
        choose: Callable[[list[Path]], Path] | None = None,
    ) -> None:
        self._cfg_path = config_path or default_config_path()
        self._cfg_mtime: object = _UNREAD
        self._sounds_dir = sounds_dir or assets_dir() / "sounds"
        self._play = play or _winsound_play
        self._choose = choose or random.choice
        self._enabled = False
        self._events: tuple[str, ...] = DEFAULT_SOUND_EVENTS
        self._style = DEFAULT_HUD_STYLE
        self._reported_missing: set[Path] = set()

    def on_state(self, state) -> None:
        event = STATE_SOUNDS.get(getattr(state, "name", ""))
        if event is None:
            return
        try:
            self._reload_config()
            if self._enabled and event in self._events:
                self.play(self._style, event)
        except Exception:
            log.exception("Ton zu %s übersprungen", event)

    def play(self, style: str, event: str) -> bool:
        if style not in HUD_STYLES or event not in SOUND_EVENTS:
            return False
        variants = self._variants(self._sounds_dir / style, event)
        if not variants:
            path = self._sounds_dir / style / f"{event}.wav"
            if path not in self._reported_missing:
                self._reported_missing.add(path)
                log.warning("Ton fehlt: %s", path)
            return False
        path = self._choose(variants)
        try:
            self._play(path)
        except Exception:
            log.exception("Ton %s/%s nicht abspielbar", style, event)
            return False
        return True

    @staticmethod
    def _variants(folder: Path, event: str) -> list[Path]:
        main = folder / f"{event}.wav"
        found = [main] if main.is_file() else []
        numbered = [path for path in folder.glob(f"{event}-*.wav")
                    if path.stem[len(event) + 1:].isascii() and path.stem[len(event) + 1:].isdigit()]
        return found + sorted(numbered, key=lambda path: int(path.stem[len(event) + 1:]))

    def _reload_config(self) -> None:
        try:
            mtime: object = self._cfg_path.stat().st_mtime
        except OSError:
            mtime = None
        if mtime == self._cfg_mtime:
            return
        try:
            ui = load_config(self._cfg_path).ui
        except Exception:
            log.exception("config.yaml nicht lesbar, Töne bleiben wie sie sind")
            return
        self._cfg_mtime = mtime
        self._enabled = ui.sound_feedback
        self._events = tuple(ui.sound_events)
        self._style = ui.hud_style
