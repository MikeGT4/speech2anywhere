from __future__ import annotations
import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from packaging.version import InvalidVersion, parse as parse_version

from kira import tls

log = logging.getLogger(__name__)

UpdateStatus = Literal["newer", "current", "local_newer", "no_asset", "failed"]
_SETUP_PREFIX = "Kira-Setup-"
_SETUP_SUFFIX = ".exe"
_SHA256SUMS_NAME = "SHA256SUMS.txt"
_TIMEOUT_SECONDS = 10.0
_DOWNLOAD_TIMEOUT_SECONDS = 60.0
_DOWNLOAD_CHUNK = 64 * 1024

_VALID_ASSET_NAME = re.compile(
    r"^Kira-Setup-v\d+(?:\.\d+){1,3}(?:-\d+\.bin|\.exe)$"
)
_APP_WHEEL_NAME = re.compile(r"^kira-(\d+(?:\.\d+){1,3})-py3-none-any\.whl$")
_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int = 0
    sha256: str = ""


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateStatus
    remote_version: str | None = None
    asset_url: str | None = None
    asset_name: str | None = None
    bundle_assets: list[ReleaseAsset] = field(default_factory=list)
    sha256sums_url: str | None = None
    error: str | None = None
    app_asset: ReleaseAsset | None = None


def _is_setup_stub(name: str) -> bool:
    if not _VALID_ASSET_NAME.fullmatch(name):
        return False
    return name.endswith(_SETUP_SUFFIX)


def _is_setup_split(name: str) -> bool:
    if not _VALID_ASSET_NAME.fullmatch(name):
        return False
    return name.endswith(".bin")


def _app_wheel(name: str, tag: str, url: str, size: int, digest: str) -> ReleaseAsset | None:
    match = _APP_WHEEL_NAME.fullmatch(name)
    found = _DIGEST.fullmatch((digest or "").strip().lower())
    if match is None or found is None:
        return None
    try:
        if parse_version(match.group(1)) != parse_version(tag):
            return None
    except InvalidVersion:
        return None
    return ReleaseAsset(name=name, url=url, size=size, sha256=found.group(1))


def check_for_update(local_version: str, repo: str) -> UpdateCheckResult:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "User-Agent": f"Speech2Anywhere/{local_version}",
        "Accept": "application/vnd.github+json",
    }
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS, context=tls.context()) as response:
            data = json.load(response)
    except (urllib.error.URLError, ConnectionError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("update check failed: %s", exc)
        return UpdateCheckResult(status="failed", error=str(exc))

    tag = str(data.get("tag_name", "")).lstrip("v")
    try:
        remote = parse_version(tag)
        local = parse_version(local_version)
    except InvalidVersion as exc:
        log.warning("version parse failed: %s", exc)
        return UpdateCheckResult(status="failed", error=str(exc))

    if remote == local:
        return UpdateCheckResult(status="current", remote_version=tag)
    if remote < local:
        return UpdateCheckResult(status="local_newer", remote_version=tag)

    stub: ReleaseAsset | None = None
    splits: list[ReleaseAsset] = []
    sha_url: str | None = None
    app: ReleaseAsset | None = None
    for asset in data.get("assets", []):
        name = asset.get("name", "") or ""
        url_ = asset.get("browser_download_url")
        size = int(asset.get("size", 0))
        if not url_:
            continue
        if _is_setup_stub(name):
            stub = ReleaseAsset(name=name, url=url_, size=size)
        elif _is_setup_split(name):
            splits.append(ReleaseAsset(name=name, url=url_, size=size))
        elif name == _SHA256SUMS_NAME:
            sha_url = url_
        else:
            app = _app_wheel(name, tag, url_, size, str(asset.get("digest") or "")) or app

    if stub is None:
        return UpdateCheckResult(status="no_asset", remote_version=tag)

    splits.sort(key=lambda a: a.name)
    bundle = [stub] + splits
    return UpdateCheckResult(
        status="newer",
        remote_version=tag,
        asset_url=stub.url,
        asset_name=stub.name,
        bundle_assets=bundle,
        sha256sums_url=sha_url,
        app_asset=app,
    )


def _fetch(url: str, target: Path, on_bytes: Callable[[int, int], None] | None = None) -> None:
    with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS, context=tls.context()) as response:  # noqa: S310 - https-URL aus der GitHub-API
        total = int(response.headers.get("Content-Length") or -1)
        done = 0
        with open(target, "wb") as out:
            while True:
                block = response.read(_DOWNLOAD_CHUNK)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if on_bytes is not None:
                    on_bytes(done, total)
    if 0 <= total and done < total:
        raise urllib.error.ContentTooShortError(
            f"retrieval incomplete: got only {done} out of {total} bytes",
            (str(target), None),
        )


def download_asset(
    url: str, target: Path, on_bytes: Callable[[int, int], None] | None = None,
) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    _fetch(url, target, on_bytes)
    return target


def matches_sha256(path: Path, expected: str) -> bool:
    return bool(expected) and _file_sha256(path) == expected.strip().lower()


def download_bundle(
    assets: list[ReleaseAsset],
    target_dir: Path,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for asset in assets:
        if not _VALID_ASSET_NAME.fullmatch(asset.name):
            raise ValueError(
                f"asset name nicht whitelist-konform: {asset.name!r}"
            )
        target = target_dir / asset.name
        if (
            asset.size > 0
            and target.exists()
            and target.stat().st_size == asset.size
        ):
            log.info(
                "resume-skip (%s already complete: %d bytes)",
                asset.name, asset.size,
            )
            paths.append(target)
            if on_progress is not None:
                on_progress(asset.name, asset.size, asset.size)
            continue
        log.info("downloading asset %s -> %s", asset.name, target)

        def _hook(done: int, total_size: int, _name: str = asset.name) -> None:
            if on_progress is not None:
                on_progress(_name, done, total_size)

        _fetch(asset.url, target, _hook)
        paths.append(target)
    return paths


def verify_sha256sums(
    sha256sums_path: Path, files_dir: Path,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        content = sha256sums_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return False, [f"SHA256SUMS lesefehler: {exc}"]

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(f"unparsable line: {line!r}")
            continue
        expected_hash, filename = parts[0].lower(), parts[1].strip()
        if filename.startswith("*"):
            filename = filename[1:]
        target = files_dir / filename
        if not target.exists():
            errors.append(f"file fehlt: {filename}")
            continue
        actual = _file_sha256(target)
        if actual != expected_hash:
            errors.append(
                f"hash mismatch fuer {filename}: "
                f"erwartet {expected_hash[:12]}…, ist {actual[:12]}…"
            )

    return (len(errors) == 0), errors


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
