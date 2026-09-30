from __future__ import annotations
import logging
import subprocess

log = logging.getLogger(__name__)

_CREATE_NO_WINDOW = 0x08000000


def kick_wsl_distro() -> None:
    try:
        subprocess.Popen(
            ["wsl.exe", "--exec", "/bin/true"],
            creationflags=_CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("WSL distro warm-up dispatched (wsl.exe --exec /bin/true)")
    except FileNotFoundError:
        log.debug("wsl.exe not on PATH, skipping WSL warm-up")
    except Exception:
        log.exception("WSL warm-up failed; setup probe may time out on cold boot")
