from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

UPDATE_DECLINED_MARKER_NAME = ".update-declined"


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
