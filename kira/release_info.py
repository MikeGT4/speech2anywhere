# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import json
import logging
import platform
import zipfile
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Callable

from packaging.version import InvalidVersion, Version

log = logging.getLogger(__name__)

RELEASE_FILE = "release.json"
WHEEL_MEMBER = f"kira/{RELEASE_FILE}"
_PACKAGE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class OllamaPin:
    version: str
    url: str = ""
    sha256: str = ""
    size: int = 0


@dataclass(frozen=True)
class ReleaseInfo:
    python: str = ""
    installer: str = ""
    requires: dict[str, str] = field(default_factory=dict)
    ollama: OllamaPin | None = None
    models: dict[str, str] = field(default_factory=dict)


def parse(data: object) -> ReleaseInfo | None:
    if not isinstance(data, dict):
        return None
    raw_ollama = data.get("ollama")
    ollama = None
    if isinstance(raw_ollama, dict) and raw_ollama.get("version"):
        ollama = OllamaPin(
            version=str(raw_ollama["version"]),
            url=str(raw_ollama.get("url") or ""),
            sha256=str(raw_ollama.get("sha256") or "").lower(),
            size=int(raw_ollama.get("size") or 0),
        )
    requires = data.get("requires") or {}
    models = data.get("models") or {}
    return ReleaseInfo(
        python=str(data.get("python") or ""),
        installer=str(data.get("installer") or ""),
        requires={str(k): str(v) for k, v in requires.items()} if isinstance(requires, dict) else {},
        ollama=ollama,
        models={str(k): str(v).lower() for k, v in models.items()} if isinstance(models, dict) else {},
    )


def _parse_text(text: str, source: str) -> ReleaseInfo | None:
    try:
        return parse(json.loads(text))
    except (ValueError, TypeError) as exc:
        log.warning("Release-Angaben in %s nicht lesbar: %s", source, exc)
        return None


def load_installed(package_dir: Path | None = None) -> ReleaseInfo | None:
    path = (package_dir or _PACKAGE_DIR) / RELEASE_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _parse_text(text, str(path))


def read_from_wheel(path: Path) -> ReleaseInfo | None:
    try:
        with zipfile.ZipFile(path) as wheel:
            text = wheel.read(WHEEL_MEMBER).decode("utf-8")
    except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        log.warning("Release-Angaben im Paket %s nicht lesbar: %s", path.name, exc)
        return None
    return _parse_text(text, path.name)


def _same_version(have: str, want: str) -> bool:
    try:
        return Version(have) == Version(want)
    except InvalidVersion:
        return have.strip() == want.strip()


def patch_blockers(
    new: ReleaseInfo,
    installed: ReleaseInfo | None,
    *,
    python_version: str | None = None,
    version_of: Callable[[str], str] = metadata.version,
) -> list[str]:
    reasons: list[str] = []
    if installed is None or not installed.installer:
        reasons.append("Diese Installation stammt aus einer Fassung ohne Angaben zu ihrer Grundlage.")
    elif installed.installer != new.installer:
        reasons.append("Das Setup selbst hat sich geändert.")
    current_python = python_version or platform.python_version()
    if not new.python or new.python != current_python:
        reasons.append(f"Python {new.python or '?'} statt {current_python}.")
    if not new.requires:
        reasons.append("Das neue Paket nennt keine Bibliotheken.")
    for name, want in sorted(new.requires.items()):
        try:
            have = version_of(name)
        except metadata.PackageNotFoundError:
            reasons.append(f"{name} {want} ist neu.")
            continue
        if not _same_version(have, want):
            reasons.append(f"{name} {have} wird zu {want}.")
    return reasons


def editable_install(dist_name: str = "kira") -> bool:
    try:
        raw = metadata.distribution(dist_name).read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return True
    if not raw:
        return False
    try:
        return bool(json.loads(raw).get("dir_info", {}).get("editable"))
    except (ValueError, AttributeError):
        return False
