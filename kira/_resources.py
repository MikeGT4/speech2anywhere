from __future__ import annotations

from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent


def assets_dir() -> Path:
    wheel_assets = _PKG_DIR / "_assets"
    if wheel_assets.exists():
        return wheel_assets
    return _PKG_DIR.parent / "assets"


def prompts_dir() -> Path:
    wheel_prompts = _PKG_DIR / "_prompts"
    if wheel_prompts.exists():
        return wheel_prompts
    return _PKG_DIR.parent / "prompts"
