# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from packaging.version import InvalidVersion, Version

from kira.ollama_host import DEFAULT_PORT, client_host
from kira.release_info import ReleaseInfo

log = logging.getLogger(__name__)

TIMEOUT_S = 3.0
MAX_ANSWER_BYTES = 1_000_000
CREATE_NO_WINDOW = 0x08000000
WINDOWS, PORT, REMOTE, ELSEWHERE = "windows", "port", "remote", "elsewhere"
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_DIGEST = re.compile(r"[0-9a-f]{64}")
_CLIENT_VERSION = re.compile(r"client version is (\S+)")
_SERVER_VERSION = re.compile(r"ollama version is (\S+)")


@dataclass(frozen=True)
class Advice:
    kind: str
    installed: str
    tested: str
    model: str = ""
    url: str = ""
    sha256: str = ""
    size: int = 0
    where: str = WINDOWS

    @property
    def local(self) -> bool:
        return self.where == WINDOWS

    @property
    def key(self) -> str:
        return f"{self.kind}|{self.model}|{self.tested}"


def server_url(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    bound = client_host(env)
    if bound:
        return bound
    raw = env.get("OLLAMA_HOST", "").strip()
    if not raw:
        return f"http://127.0.0.1:{DEFAULT_PORT}"
    explicit = "://" in raw
    parsed = urlparse(raw if explicit else f"http://{raw}")
    scheme = parsed.scheme or "http"
    default = (443 if scheme == "https" else 80) if explicit else DEFAULT_PORT
    host = parsed.hostname or "127.0.0.1"
    if ":" in host:
        host = f"[{host}]"
    return f"{scheme}://{host}:{parsed.port or default}"


def is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in _LOCAL_HOSTS


def windows_ollama_dir(env: Mapping[str, str] | None = None) -> Path | None:
    local = (os.environ if env is None else env).get("LOCALAPPDATA")
    return Path(local) / "Programs" / "Ollama" if local else None


def windows_ollama_exe(env: Mapping[str, str] | None = None) -> Path | None:
    folder = windows_ollama_dir(env)
    exe = folder / "ollama.exe" if folder else None
    return exe if exe is not None and exe.is_file() else None


def windows_ollama_version(exe: Path, run=subprocess.run) -> str | None:
    try:
        result = run([str(exe), "--version"], capture_output=True, text=True, timeout=15,
                     creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        log.info("Version des Windows-Ollama nicht lesbar: %s", exc)
        return None
    text = f"{result.stdout or ''}\n{result.stderr or ''}"
    found = _CLIENT_VERSION.search(text) or _SERVER_VERSION.search(text)
    return found.group(1) if found else None


def placement(base: str, server_version: str | None, windows_version: str | None) -> str:
    if not is_local(base):
        return REMOTE
    if windows_version is None:
        return ELSEWHERE
    return WINDOWS if windows_version == server_version else PORT


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:  # noqa: S310
        return json.loads(response.read(MAX_ANSWER_BYTES))


def full_name(model: str) -> str:
    model = model.strip()
    return model if ":" in model else f"{model}:latest"


def fetch_state(base: str, get: Callable[[str], object] = _get_json) -> tuple[str | None, dict[str, str]]:
    try:
        data = get(f"{base}/api/version")
        version = str(data.get("version") or "") if isinstance(data, dict) else ""
    except (OSError, ValueError, urllib.error.URLError) as exc:
        log.info("Ollama-Version nicht abrufbar (%s): %s", base, exc)
        return None, {}
    digests: dict[str, str] = {}
    try:
        data = get(f"{base}/api/tags")
        for item in (data.get("models") or []) if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "")
            digest = str(item.get("digest") or "").lower()
            if name and _DIGEST.fullmatch(digest):
                digests[full_name(name)] = digest
    except (OSError, ValueError, urllib.error.URLError) as exc:
        log.info("Ollama-Modelle nicht abrufbar (%s): %s", base, exc)
    return version or None, digests


def _older(have: str, want: str) -> bool:
    try:
        return Version(have) < Version(want)
    except InvalidVersion:
        return False


def evaluate(
    info: ReleaseInfo | None,
    server_version: str | None,
    digests: Mapping[str, str],
    model: str,
    *,
    where: str = WINDOWS,
) -> list[Advice]:
    if info is None:
        return []
    advice: list[Advice] = []
    tested = info.ollama
    if tested is not None and server_version and _older(server_version, tested.version):
        advice.append(Advice(
            kind="ollama", installed=server_version, tested=tested.version,
            url=tested.url, sha256=tested.sha256, size=tested.size, where=where,
        ))
    name = full_name(model) if model else ""
    want = {full_name(k): v for k, v in info.models.items()}.get(name, "")
    have = digests.get(name, "")
    if want and have and have != want:
        advice.append(Advice(kind="model", installed=have, tested=want, model=name, where=where))
    return advice


def _port_owner(base: str) -> str:
    from kira.ollama_diag import diagnose_ollama_port

    return diagnose_ollama_port(urlparse(base).port or DEFAULT_PORT).kind


def check(model: str, info: ReleaseInfo | None, env: Mapping[str, str] | None = None,
          fetch=fetch_state, version_of=windows_ollama_version, owner=_port_owner) -> list[Advice]:
    base = server_url(env)
    server_version, digests = fetch(base)
    exe = windows_ollama_exe(env) if is_local(base) else None
    windows_version = version_of(exe) if exe is not None else None
    where = placement(base, server_version, windows_version)
    if where == WINDOWS and owner(base) in ("wsl", "docker"):
        where = PORT
    return evaluate(info, server_version, digests, model, where=where)


class AdviceWatch:
    def __init__(
        self,
        check: Callable[[], list[Advice]],
        is_declined: Callable[[str], bool],
        set_advice: Callable[[list[Advice]], None],
        notify: Callable[[Advice], None],
        is_notified: Callable[[str], bool] | None = None,
        mark_notified: Callable[[str], None] | None = None,
    ) -> None:
        self._check = check
        self._is_declined = is_declined
        self._set_advice = set_advice
        self._notify = notify
        self._notified: set[str] = set()
        self._is_notified = is_notified or self._notified.__contains__
        self._mark_notified = mark_notified or self._notified.add

    def run_once(self) -> list[Advice]:
        advice = [a for a in self._check() if not self._is_declined(a.key)]
        self._set_advice(advice)
        for item in advice:
            if not self._is_notified(item.key):
                self._mark_notified(item.key)
                log.info("Ollama-Empfehlung: %s %s, geprüft %s", item.kind, item.installed, item.tested)
                self._notify(item)
        if not advice:
            log.info("Ollama-Empfehlung: nichts zu melden")
        return advice
