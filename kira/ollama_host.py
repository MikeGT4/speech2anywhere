# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import os
from collections.abc import Mapping

DEFAULT_PORT = 11434
_BIND_ALL = frozenset({"", "0.0.0.0", "::"})


def client_host(env: Mapping[str, str] | None = None) -> str | None:
    raw = (os.environ if env is None else env).get("OLLAMA_HOST", "").strip()
    if not raw:
        return None
    scheme, sep, rest = raw.partition("://")
    if not sep:
        scheme, rest = "http", raw
    rest = rest.rstrip("/")
    if rest.startswith("["):
        host, _, tail = rest[1:].partition("]")
        port = tail.lstrip(":")
    elif rest.count(":") > 1:
        host, port = rest, ""
    else:
        host, _, port = rest.partition(":")
    if host not in _BIND_ALL:
        return None
    return f"{scheme}://127.0.0.1:{port or DEFAULT_PORT}"
