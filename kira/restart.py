# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

WAIT_ENV = "S2A_RESTART_WAIT_PID"
WAIT_S = 20.0
DETACHED = 0x00000008 | 0x00000200
LAUNCHER_NAME = "kira.exe"


def launcher(argv0: str | None = None, executable: str | None = None) -> Path | None:
    candidates = (
        Path(sys.argv[0] if argv0 is None else argv0),
        Path(sys.executable if executable is None else executable).parent / LAUNCHER_NAME,
    )
    for path in candidates:
        if path.name.lower() == LAUNCHER_NAME and path.exists():
            return path
    return None


def start_successor(popen=subprocess.Popen, path: Path | None = None, pid: int | None = None) -> bool:
    target = path or launcher()
    if target is None:
        log.warning("Neustart: Starter nicht gefunden (argv0=%s)", sys.argv[0])
        return False
    env = dict(os.environ)
    env[WAIT_ENV] = str(os.getpid() if pid is None else pid)
    try:
        popen([str(target)], creationflags=DETACHED, close_fds=True, env=env)
    except OSError:
        log.exception("Neustart: Start von %s fehlgeschlagen", target)
        return False
    log.info("Neustart: Nachfolger gestartet (%s)", target)
    return True


def _wait_for_exit(pid: int, timeout_s: float) -> bool:
    from kira._apply_update import wait_for_exit
    return wait_for_exit(pid, timeout_s)


def wait_for_predecessor(environ=os.environ, wait=_wait_for_exit, timeout_s: float = WAIT_S) -> bool:
    raw = environ.pop(WAIT_ENV, None)
    if not raw or not raw.isdigit():
        return True
    log.info("Neustart: warte auf das Ende von Prozess %s", raw)
    done = wait(int(raw), timeout_s)
    if not done:
        log.warning("Neustart: Prozess %s läuft nach %.0f s noch", raw, timeout_s)
    return done
