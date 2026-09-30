from __future__ import annotations
import subprocess
import logging
from kira.config import Config

log = logging.getLogger(__name__)

APPLESCRIPT = (
    'tell application "System Events" to get bundle identifier of '
    'first application process whose frontmost is true'
)


def active_app_bundle_id() -> str | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", APPLESCRIPT],
            capture_output=True, text=True, timeout=0.5, check=False,
        )
        if result.returncode != 0:
            log.warning("osascript failed: %s", result.stderr.strip())
            return None
        bundle = result.stdout.strip()
        return bundle or None
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.warning("active_app_bundle_id error: %s", exc)
        return None


def detect_mode(config: Config) -> str:
    bundle = active_app_bundle_id()
    if bundle is None:
        return "plain"
    return config.context_modes.get(bundle, "plain")
