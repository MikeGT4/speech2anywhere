from __future__ import annotations
import logging
import win32gui
import win32process
import psutil
from kira.config import Config

log = logging.getLogger(__name__)


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


def active_exe() -> str | None:
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == 0:
            return None
        return psutil.Process(pid).name().lower()
    except Exception as exc:
        log.debug("active_exe error: %s", exc)
        return None


def detect_mode(config: Config) -> str:
    exe = active_exe()
    if exe is None:
        return "plain"
    return config.context_modes.get(exe, "plain")
