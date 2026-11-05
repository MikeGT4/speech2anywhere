# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

from kira.config import DEFAULT_HUD_STYLE, HUD_STYLES
from kira.texte import N_

STYLE_LABELS: dict[str, str] = {
    "comic": N_("Comic (Bla-Bla)"),
    "manga": "Manga (Shōnen)",
    "halloween": N_("Halloween (Hexenhut)"),
    "weihnachten": N_("Weihnachten (Winternacht)"),
    "phosphor": N_("Phosphor (Oszilloskop)"),
    "gun_barrel": "Gun Barrel",
    "zielerfassung": N_("Zielerfassung"),
    "stimmabdruck": N_("Stimmabdruck (Spektrogramm)"),
    "klartext": N_("Klartext (Terminal)"),
    "klassisch": N_("Klassisch (bis v0.4.0)"),
}

_MODULES = {
    "comic": ("kira.ui.hud.comic", "Comic"),
    "manga": ("kira.ui.hud.manga", "Manga"),
    "halloween": ("kira.ui.hud.halloween", "Halloween"),
    "weihnachten": ("kira.ui.hud.weihnachten", "Weihnachten"),
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
