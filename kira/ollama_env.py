from __future__ import annotations

import logging
import sys
from collections.abc import Mapping

log = logging.getLogger(__name__)

TUNING_ENV: dict[str, str] = {
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
    "LLAMA_ARG_CACHE_RAM": "0",
    "CUDA_CACHE_MAXSIZE": "4294967296",
}

VRAM_TUNING = ("OLLAMA_FLASH_ATTENTION", "OLLAMA_KV_CACHE_TYPE")

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


def _read_tuning_values() -> dict[str, str]:
    current = _read_user_env()
    return {name: current[name] for name in TUNING_ENV if name in current}


def read_tuning_env() -> dict[str, str] | None:
    if sys.platform != "win32":
        return None
    try:
        return _read_tuning_values()
    except OSError:
        return None


def vram_tuning_set(values: Mapping[str, str] | None) -> bool | None:
    if values is None:
        return None
    return all(values.get(name) == TUNING_ENV[name] for name in VRAM_TUNING)


def describe_tuning_env(values: Mapping[str, str] | None) -> str:
    if values is None:
        return "nicht lesbar"
    return ", ".join(
        f"{name}={values[name]}" if name in values else f"{name} fehlt"
        for name in TUNING_ENV
    )


def _tuning_outcome(written: list[str], failed: list[str]) -> str:
    parts = []
    if written:
        parts.append("neu gesetzt: " + ", ".join(written))
    if failed:
        parts.append("nicht gesetzt: " + ", ".join(failed))
    return "; ".join(parts) or "bereits gesetzt"


def apply_tuning_env(provider: str = "ollama") -> list[str]:
    if sys.platform != "win32":
        return []
    if provider != "ollama":
        log.info("Ollama-Tuning übersprungen (provider=%s)", provider)
        return []
    try:
        found = _read_tuning_values()
    except OSError as exc:
        log.warning(
            "HKCU\\Environment nicht lesbar, Ollama-Tuning übersprungen (%s)",
            exc,
        )
        return []

    written: list[str] = []
    failed: list[str] = []
    for name, value in pending_changes(found).items():
        try:
            _write_user_env(name, value)
            written.append(name)
        except OSError:
            failed.append(name)
            log.exception("Konnte %s nicht in HKCU\\Environment setzen", name)

    log.info(
        "Ollama-Tuning in HKCU\\Environment vorgefunden: %s; %s",
        describe_tuning_env(found),
        _tuning_outcome(written, failed),
    )
    if written:
        log.info(
            "Umgebungsvariablen gesetzt (%s), wirksam nach Neustart von Ollama und Speech2Anywhere oder Windows",
            ", ".join(written),
        )
    return written
