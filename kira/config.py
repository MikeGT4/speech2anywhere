from __future__ import annotations
import math
import os
import sys
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, Field, field_validator

_HOME = Path.home()


class HotkeyConfig(BaseModel):
    combo: str = "fn"
    min_duration_ms: int = 300
    edit_combo: str | None = "f9"


class AudioConfig(BaseModel):
    input_gain: float = 1.0
    input_device: int | str | None = None


class WhisperConfig(BaseModel):
    model: str = "mlx-community/whisper-large-v3-turbo"
    language: Literal["auto", "de", "en"] = "auto"
    vad_threshold: float = 0.35
    condition_on_previous_text: bool = False
    initial_prompt: str | None = None
    replacements: dict[str, str] = Field(default_factory=dict)


class ModeConfig(BaseModel):
    model: str | None = None
    timeout_seconds: float | None = None
    temperature: float | None = None


class StylerConfig(BaseModel):
    provider: Literal["ollama", "openai"] = "ollama"
    model: str = "gemma2:2b"
    timeout_seconds: float = 3.0
    fallback_to_raw: bool = True
    keep_alive: str = "24h"
    warmup_on_start: bool = True
    fast_mode: bool = False
    fast_model: str = "gemma4:e4b"
    modes: dict[str, ModeConfig] = Field(default_factory=dict)


class InjectorConfig(BaseModel):
    strategy: Literal["clipboard", "keystrokes"] = "clipboard"
    restore_clipboard_after_ms: int = 500


HUD_STYLES = ("comic", "phosphor", "gun_barrel", "zielerfassung", "stimmabdruck", "klartext", "klassisch")
DEFAULT_HUD_STYLE = "comic"


class UIConfig(BaseModel):
    popup: bool = True
    sound_feedback: bool = False
    hud_style: str = DEFAULT_HUD_STYLE
    hud_scale: float = 1.5

    @field_validator("hud_style", mode="before")
    @classmethod
    def _known_hud_style(cls, value: object) -> str:
        key = str(value or "").strip().lower()
        return key if key in HUD_STYLES else DEFAULT_HUD_STYLE

    @field_validator("hud_scale", mode="before")
    @classmethod
    def _bounded_hud_scale(cls, value: object) -> float:
        try:
            scale = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 1.5
        if math.isnan(scale):
            return 1.5
        return min(3.0, max(0.75, scale))


class UpdatesConfig(BaseModel):
    check_on_start: bool = True
    check_interval_hours: float = 6.0

    @field_validator("check_interval_hours", mode="before")
    @classmethod
    def _bounded_interval(cls, value: object) -> float:
        try:
            hours = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 6.0
        if math.isnan(hours):
            return 6.0
        if hours <= 0:
            return 0.0
        return min(168.0, max(1.0, hours))


class LearningConfig(BaseModel):
    enabled: bool = True
    sources: list[str] = Field(default_factory=list)


DEFAULT_CONTEXT_MODES_MAC: dict[str, str] = {
    "com.apple.mail": "email",
    "com.microsoft.Outlook": "email",
    "com.readdle.SparkDesktop": "email",
    "com.apple.MobileSMS": "chat",
    "com.tinyspeck.slackmacgap": "chat",
    "com.hnc.Discord": "chat",
    "com.apple.Terminal": "terminal",
    "com.googlecode.iterm2": "terminal",
    "co.zeit.hyper": "terminal",
    "com.microsoft.VSCode": "code",
    "com.apple.dt.Xcode": "code",
    "com.jetbrains.pycharm": "code",
    "com.apple.Safari": "plain",
    "com.google.Chrome": "plain",
    "org.mozilla.firefox": "plain",
}

DEFAULT_CONTEXT_MODES_WIN: dict[str, str] = {
    "outlook.exe": "email",
    "hxoutlook.exe": "email",
    "thunderbird.exe": "email",
    "slack.exe": "chat",
    "discord.exe": "chat",
    "teams.exe": "chat",
    "ms-teams.exe": "chat",
    "signal.exe": "chat",
    "telegram.exe": "chat",
    "whatsapp.exe": "chat",
    "windowsterminal.exe": "terminal",
    "wt.exe": "terminal",
    "cmd.exe": "terminal",
    "powershell.exe": "terminal",
    "pwsh.exe": "terminal",
    "wsl.exe": "terminal",
    "alacritty.exe": "terminal",
    "code.exe": "code",
    "cursor.exe": "code",
    "idea64.exe": "code",
    "pycharm64.exe": "code",
    "devenv.exe": "code",
    "sublime_text.exe": "code",
    "notepad.exe": "plain",
    "obsidian.exe": "plain",
    "notion.exe": "plain",
    "chrome.exe": "plain",
    "msedge.exe": "plain",
    "firefox.exe": "plain",
    "brave.exe": "plain",
}


def platform_context_modes() -> dict[str, str]:
    if sys.platform == "win32":
        return DEFAULT_CONTEXT_MODES_WIN.copy()
    return DEFAULT_CONTEXT_MODES_MAC.copy()


class Config(BaseModel):
    hotkey: HotkeyConfig = Field(default_factory=HotkeyConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    whisper: WhisperConfig = Field(default_factory=WhisperConfig)
    styler: StylerConfig = Field(default_factory=StylerConfig)
    injector: InjectorConfig = Field(default_factory=InjectorConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    updates: UpdatesConfig = Field(default_factory=UpdatesConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    context_modes: dict[str, str] = Field(default_factory=platform_context_modes)


def effective_hotkey(combo: str) -> str:
    if sys.platform == "win32" and combo == "fn":
        return "f8"
    return combo


def default_config_path() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Kira" / "config.yaml"
        return _HOME / "AppData" / "Roaming" / "Kira" / "config.yaml"
    return _HOME / ".config" / "kira" / "config.yaml"


def load_config(path: Path | None = None) -> Config:
    path = path or default_config_path()
    if not path.exists():
        return Config()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(raw.get("context_modes"), dict):
        merged = platform_context_modes()
        merged.update(raw["context_modes"])
        raw["context_modes"] = merged
    return Config.model_validate(raw)
