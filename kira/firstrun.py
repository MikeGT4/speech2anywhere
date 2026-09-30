from __future__ import annotations

import os
from pathlib import Path

FIRST_RUN_MARKER_NAME = ".first-run-complete"


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


def is_first_run() -> bool:
    return not (_kira_appdata_dir() / FIRST_RUN_MARKER_NAME).exists()


def mark_first_run_complete() -> None:
    kira_dir = _kira_appdata_dir()
    kira_dir.mkdir(parents=True, exist_ok=True)
    (kira_dir / FIRST_RUN_MARKER_NAME).write_text("done\n", encoding="utf-8")
