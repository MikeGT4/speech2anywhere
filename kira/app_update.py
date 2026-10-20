# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from kira import __version__, release_info
from kira.updater import ReleaseAsset, download_asset, matches_sha256

log = logging.getLogger(__name__)

HELPER = Path(__file__).resolve().parent / "_apply_update.py"
HELPER_NAME = "apply_update.py"
LOG_NAME = "apply_update.log"
DETACHED = 0x00000008 | 0x00000200


@dataclass(frozen=True)
class PatchCheck:
    wheel: Path | None
    reasons: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.wheel is not None and not self.reasons


def install_root(prefix: Path | None = None) -> Path | None:
    root = prefix or Path(sys.prefix)
    if release_info.editable_install():
        return None
    if not (root / "Scripts" / "kira.exe").exists() or not (root / "pythonw.exe").exists():
        return None
    return root


def check_patch(
    asset: ReleaseAsset,
    target_dir: Path,
    *,
    root: Path | None,
    fetch=download_asset,
    installed: release_info.ReleaseInfo | None = None,
) -> PatchCheck:
    if root is None:
        return PatchCheck(None, ["Diese Fassung wird nicht über das Setup verwaltet."])
    wheel = target_dir / asset.name
    part = target_dir / f"{asset.name}.{os.getpid()}.{time.monotonic_ns()}.part"
    try:
        fetch(asset.url, part)
        if not matches_sha256(part, asset.sha256):
            log.warning("Programm-Update: Prüfsumme von %s passt nicht", asset.name)
            return PatchCheck(None, ["Die Prüfsumme des Programmpakets passt nicht."])
        os.replace(part, wheel)
    except Exception as exc:
        log.warning("Programm-Update: Download fehlgeschlagen: %s", exc)
        return PatchCheck(None, [f"Das Programmpaket ließ sich nicht laden ({exc})."])
    finally:
        part.unlink(missing_ok=True)
    new = release_info.read_from_wheel(wheel)
    if new is None:
        return PatchCheck(None, ["Das Programmpaket nennt seine Grundlage nicht."])
    base = installed if installed is not None else release_info.load_installed()
    return PatchCheck(wheel, release_info.patch_blockers(new, base))


def _own_pids(root: Path) -> list[int]:
    pids = [os.getpid()]
    try:
        import psutil

        parent = psutil.Process().parent()
        if parent is not None and Path(parent.exe()).resolve() == (root / "Scripts" / "kira.exe").resolve():
            pids.append(parent.pid)
    except Exception:
        log.debug("Startprozess nicht ermittelbar", exc_info=True)
    return pids


def launch_patch(
    wheel: Path,
    version: str,
    *,
    sha256: str,
    root: Path,
    pids: list[int] | None = None,
    popen=subprocess.Popen,
) -> Path:
    script = wheel.parent / HELPER_NAME
    shutil.copyfile(HELPER, script)
    log_path = wheel.parent / LOG_NAME
    package_version = wheel.name.split("-")[1] if wheel.name.count("-") >= 4 else version
    cmd = [str(root / "pythonw.exe"), "-I", str(script), "--wheel", str(wheel), "--sha256", sha256,
           "--version", package_version, "--current", __version__, "--log", str(log_path)]
    for pid in (pids if pids is not None else _own_pids(root)):
        cmd += ["--pid", str(pid)]
    popen(cmd, creationflags=DETACHED, close_fds=True, cwd=str(root.parent))
    log.info("Programm-Update auf %s übergeben, Protokoll %s", version, log_path)
    return log_path
