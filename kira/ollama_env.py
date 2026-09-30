from __future__ import annotations

import logging
import sys
from collections.abc import Mapping

log = logging.getLogger(__name__)

TUNING_ENV: dict[str, str] = {
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
    "LLAMA_ARG_CACHE_RAM": "0",
}

_USER_ENV_SUBKEY = "Environment"


def pending_changes(current: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in TUNING_ENV.items() if current.get(k) != v}


def _read_user_env() -> dict[str, str]:
    import winreg

    values: dict[str, str] = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _USER_ENV_SUBKEY) as key:
        index = 0
        while True:
            try:
                name, data, _typ = winreg.EnumValue(key, index)
            except OSError:
                break
            values[name] = str(data)
            index += 1
    return values


def _write_user_env(name: str, value: str) -> None:
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _USER_ENV_SUBKEY, 0, winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    _broadcast_env_change()


def _broadcast_env_change() -> None:
    try:
        import ctypes

        hwnd_broadcast = 0xFFFF
        wm_settingchange = 0x001A
        smto_abortifhung = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            hwnd_broadcast, wm_settingchange, 0, "Environment",
            smto_abortifhung, 2000, None,
        )
    except Exception:  # noqa: BLE001 - Broadcast ist Komfort, nie kritisch
        log.debug("WM_SETTINGCHANGE broadcast failed (non-fatal)", exc_info=True)


def apply_tuning_env() -> list[str]:
    if sys.platform != "win32":
        return []
    try:
        current = _read_user_env()
    except OSError as exc:
        log.warning(
            "HKCU\\Environment nicht lesbar, Ollama-Tuning übersprungen (%s)",
            exc,
        )
        return []

    written: list[str] = []
    for name, value in pending_changes(current).items():
        try:
            _write_user_env(name, value)
            written.append(name)
        except OSError:
            log.exception("Konnte %s nicht in HKCU\\Environment setzen", name)

    if written:
        log.info(
            "Ollama-VRAM-Tuning gesetzt (%s), greift nach Ollama-Neustart oder Reboot",
            ", ".join(written),
        )
    return written
