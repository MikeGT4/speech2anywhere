# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import json
import logging
import re
import threading
import urllib.request
from typing import Callable

from kira import progress as prog
from kira.ollama_host import client_host

log = logging.getLogger(__name__)

CONNECT_TIMEOUT_S = 10.0
MANIFEST_TIMEOUT_S = 5.0
MAX_MANIFEST_BYTES = 1_000_000
REGISTRY = "registry.ollama.ai"
MANIFEST_TYPE = "application/vnd.docker.distribution.manifest.v2+json"
UNKNOWN_MODEL = "manifest: file does not exist"
INCOMPLETE = "Ollama hat den Download ohne Abschluss beendet."
_NAME_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class PullFailed(Exception):
    pass


def connect():
    import httpx
    import ollama
    return ollama.Client(host=client_host(), timeout=httpx.Timeout(None, connect=CONNECT_TIMEOUT_S))


def manifest_url(model: str) -> str | None:
    head, _, last = model.strip().rpartition("/")
    name, _, tag = last.partition(":")
    parts = head.split("/") if head else []
    if len(parts) == 2 and parts[0].lower() == REGISTRY:
        parts = parts[1:]
    if len(parts) > 1:
        return None
    path = (parts[0] if parts else "library", name, tag or "latest")
    if not all(_NAME_PART.fullmatch(part) for part in path):
        return None
    return f"https://{REGISTRY}/v2/{path[0]}/{path[1]}/manifests/{path[2]}"


def registry_size(model: str, timeout: float = MANIFEST_TIMEOUT_S) -> int:
    url = manifest_url(model)
    if url is None:
        log.info("Größe von %s: kein Modell aus der Ollama-Bibliothek", model)
        return 0
    request = urllib.request.Request(url, headers={"Accept": MANIFEST_TYPE})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            manifest = json.loads(response.read(MAX_MANIFEST_BYTES))
        size = sum(int(part["size"]) for part in [manifest["config"], *manifest["layers"]])
    except Exception as exc:
        log.info("Größe von %s aus der Ollama-Bibliothek nicht lesbar: %s", model, exc)
        return 0
    log.info("Größe von %s laut Ollama-Bibliothek: %d Byte", model, size)
    return max(0, size)


def missing_text(model: str, exc: BaseException) -> str | None:
    if UNKNOWN_MODEL in str(exc):
        return f"Modell {model} gibt es bei Ollama nicht."
    return None


def _close(client) -> None:
    close = getattr(client, "close", None) or getattr(getattr(client, "_client", None), "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        log.debug("Ollama-Verbindung ließ sich nicht schließen", exc_info=True)


class ModelPull:
    def __init__(self, model: str) -> None:
        self._model = model
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._client = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()
        with self._lock:
            client = self._client
        if client is not None:
            _close(client)

    def run(self, emit: Callable[[str, int, int], None]) -> bool:
        expected = self._expected_size()
        client = self._open()
        if client is None:
            return False
        try:
            return self._stream(client, prog.PullTracker(expected), emit)
        except Exception:
            if self.cancelled:
                return False
            raise
        finally:
            with self._lock:
                self._client = None
            _close(client)

    def _expected_size(self) -> int:
        found: list[int] = []
        ready = threading.Event()

        def fetch() -> None:
            try:
                found.append(registry_size(self._model))
            finally:
                ready.set()

        threading.Thread(target=fetch, name="kira-ollama-manifest", daemon=True).start()
        while not ready.wait(0.05):
            if self.cancelled:
                return 0
        return found[0] if found else 0

    def _open(self):
        with self._lock:
            if self.cancelled:
                return None
            self._client = connect()
            return self._client

    def _stream(self, client, tracker: prog.PullTracker, emit: Callable[[str, int, int], None]) -> bool:
        throttle = prog.Throttle()
        last: str | None = None
        succeeded = False
        events = client.pull(self._model, stream=True)
        try:
            for event in events:
                if self.cancelled:
                    return False
                status, digest, completed, total = prog.pull_fields(event)
                if prog.final_status(status):
                    done, size = tracker.complete()
                else:
                    done, size = tracker.feed(digest or status, completed, total)
                succeeded = succeeded or status.strip().lower() == prog.SUCCESS
                if throttle.due(force=status != last or (size > 0 and done >= size)):
                    last = status
                    emit(status, done, size)
        finally:
            close = getattr(events, "close", None)
            if close is not None:
                close()
        if self.cancelled:
            return False
        if not succeeded:
            raise PullFailed(INCOMPLETE)
        return True
