# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

from kira.config import DEFAULT_HUD_STYLE, HUD_STYLES

STYLE_LABELS: dict[str, str] = {
    "comic": "Comic (Bla-Bla)",
    "phosphor": "Phosphor (Oszilloskop)",
    "gun_barrel": "Gun Barrel",
    "zielerfassung": "Zielerfassung",
    "stimmabdruck": "Stimmabdruck (Spektrogramm)",
    "klartext": "Klartext (Terminal)",
    "klassisch": "Klassisch (bis v0.4.0)",
}

_MODULES = {
    "comic": ("kira.ui.hud.comic", "Comic"),
    "phosphor": ("kira.ui.hud.phosphor", "Phosphor"),
    "gun_barrel": ("kira.ui.hud.gun_barrel", "GunBarrel"),
    "zielerfassung": ("kira.ui.hud.zielerfassung", "Zielerfassung"),
    "stimmabdruck": ("kira.ui.hud.stimmabdruck", "Stimmabdruck"),
    "klartext": ("kira.ui.hud.klartext", "Klartext"),
    "klassisch": ("kira.ui.hud.klassisch", "Klassisch"),
}

assert tuple(STYLE_LABELS) == HUD_STYLES == tuple(_MODULES)


def create_style(key: str):
    import importlib

    module_name, class_name = _MODULES.get(key, _MODULES[DEFAULT_HUD_STYLE])
    return getattr(importlib.import_module(module_name), class_name)()
