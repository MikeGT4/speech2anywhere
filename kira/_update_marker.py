from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

UPDATE_DECLINED_MARKER_NAME = ".update-declined"
ADVICE_DECLINED_MARKER_NAME = ".ollama-advice-declined"
ADVICE_NOTIFIED_MARKER_NAME = ".ollama-advice-notified"


def _kira_appdata_dir() -> Path:
    appdata_str = os.environ.get("APPDATA")
    if not appdata_str:
        raise EnvironmentError("APPDATA env var not set: Speech2Anywhere requires Windows.")
    appdata = Path(appdata_str).resolve()

    user_profile_str = os.environ.get("USERPROFILE")
    if user_profile_str:
        user_profile = Path(user_profile_str).resolve()
        try:
            appdata.relative_to(user_profile)
        except ValueError:
            raise EnvironmentError(
                f"APPDATA ({appdata}) liegt nicht unter USERPROFILE "
                f"({user_profile}), möglicherweise manipulierte Umgebung. Speech2Anywhere "
                "refusing to write outside user scope."
            )

    return appdata / "Kira"


def is_update_declined(version: str) -> bool:
    try:
        marker = _kira_appdata_dir() / UPDATE_DECLINED_MARKER_NAME
        if not marker.exists():
            return False
        return marker.read_text(encoding="utf-8").strip() == version.strip()
    except OSError as exc:
        log.warning("update-declined marker konnte nicht gelesen werden: %s", exc)
        return False


def mark_update_declined(version: str) -> None:
    try:
        kira_dir = _kira_appdata_dir()
        kira_dir.mkdir(parents=True, exist_ok=True)
        (kira_dir / UPDATE_DECLINED_MARKER_NAME).write_text(
            version.strip() + "\n", encoding="utf-8",
        )
        log.info("Update v%s vom Nutzer abgelehnt, Marker gesetzt", version)
    except OSError as exc:
        log.warning("update-declined marker konnte nicht geschrieben werden: %s", exc)


def _marker_keys(name: str) -> set[str]:
    marker = _kira_appdata_dir() / name
    if not marker.exists():
        return set()
    return {line.strip() for line in marker.read_text(encoding="utf-8").splitlines() if line.strip()}


def _add_marker_key(name: str, key: str) -> None:
    if key.strip() in _marker_keys(name):
        return
    kira_dir = _kira_appdata_dir()
    kira_dir.mkdir(parents=True, exist_ok=True)
    with (kira_dir / name).open("a", encoding="utf-8") as fh:
        fh.write(key.strip() + "\n")


def is_advice_declined(key: str) -> bool:
    try:
        return key.strip() in _marker_keys(ADVICE_DECLINED_MARKER_NAME)
    except OSError as exc:
        log.warning("Ollama-Empfehlung: Marker nicht lesbar: %s", exc)
        return False


def mark_advice_declined(key: str) -> None:
    try:
        _add_marker_key(ADVICE_DECLINED_MARKER_NAME, key)
        log.info("Ollama-Empfehlung %s abgelehnt, Marker gesetzt", key)
    except OSError as exc:
        log.warning("Ollama-Empfehlung: Marker nicht schreibbar: %s", exc)


def is_advice_notified(key: str) -> bool:
    try:
        return key.strip() in _marker_keys(ADVICE_NOTIFIED_MARKER_NAME)
    except OSError as exc:
        log.warning("Ollama-Empfehlung: Marker nicht lesbar: %s", exc)
        return False


def mark_advice_notified(key: str) -> None:
    try:
        _add_marker_key(ADVICE_NOTIFIED_MARKER_NAME, key)
    except OSError as exc:
        log.warning("Ollama-Empfehlung: Marker nicht schreibbar: %s", exc)
