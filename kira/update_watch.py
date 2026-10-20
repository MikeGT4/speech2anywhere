# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)

_NOTHING_TO_INSTALL = ("current", "local_newer", "no_asset")


class UpdateWatch:
    def __init__(
        self,
        check: Callable[[], object],
        is_declined: Callable[[str], bool],
        set_available: Callable[[str | None], None],
        notify: Callable[[str], None],
    ) -> None:
        self._check = check
        self._is_declined = is_declined
        self._set_available = set_available
        self._notify = notify
        self._notified: str | None = None

    def mark_notified(self, version: str) -> None:
        self._notified = version

    def start_result(self, result: object) -> str | None:
        status = getattr(result, "status", None)
        if status != "newer":
            log.info("Start-Update-Check: keine Aktion (status=%s)", status)
            return None
        remote = getattr(result, "remote_version", None) or "?"
        self._set_available(remote)
        self.mark_notified(remote)
        if self._is_declined(remote):
            log.info(
                "Start-Update-Check: v%s verfügbar, vom Nutzer bereits abgelehnt, keine Abfrage",
                remote,
            )
            return None
        log.info("Start-Update-Check: neuere Version v%s verfügbar", remote)
        return remote

    def run_once(self) -> str | None:
        result = self._check()
        status = getattr(result, "status", None)
        if status != "newer":
            log.info("Update-Prüfung: keine Aktion (status=%s)", status)
            if status in _NOTHING_TO_INSTALL:
                self._set_available(None)
            return None
        remote = getattr(result, "remote_version", None) or "?"
        self._set_available(remote)
        if remote != self._notified and not self._is_declined(remote):
            self._notified = remote
            log.info("Update-Prüfung: v%s verfügbar, Meldung im Tray", remote)
            self._notify(remote)
        return remote


def run_periodically(watch, interval_s: float, stop: threading.Event, first_s: float | None = None) -> None:
    if first_s is not None and not stop.wait(first_s):
        try:
            watch.run_once()
        except Exception:
            log.exception("Erste Prüfung fehlgeschlagen; nächster Versuch im nächsten Takt")
    while not stop.wait(interval_s):
        try:
            watch.run_once()
        except Exception:
            log.exception("Update-Prüfung fehlgeschlagen; nächster Versuch im nächsten Takt")


def start_watch(
    watch,
    *,
    enabled: bool,
    interval_h: float,
    stop: threading.Event | None = None,
    first_s: float | None = None,
    name: str = "kira-update-watch",
    label: str = "Update-Prüfung",
) -> threading.Thread | None:
    if not enabled or interval_h <= 0:
        log.info("Wiederholte %s aus (check_on_start=%s, Intervall %.1f h)",
                 label, enabled, interval_h)
        return None
    thread = threading.Thread(
        target=run_periodically,
        args=(watch, interval_h * 3600.0, stop or threading.Event(), first_s),
        daemon=True,
        name=name,
    )
    thread.start()
    log.info("%s alle %.1f h aktiv", label, interval_h)
    return thread
