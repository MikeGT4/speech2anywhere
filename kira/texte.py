# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import sys
from typing import Callable
from kira.texte_en import EN, EN_CONTEXT

LANGUAGES = ("de", "en")
_WINDOWS_PRIMARY = {0x07: "de", 0x09: "en"}
_language = "de"


def language() -> str:
    return _language


def set_language(code: str) -> None:
    global _language
    if code in LANGUAGES:
        _language = code


def tr(text: str, place: str | None = None) -> str:
    if _language != "en":
        return text
    if place is not None:
        fitted = EN_CONTEXT.get((place, text))
        if fitted is not None:
            return fitted
    return EN.get(text, text)


def decimal_mark() -> str:
    return "." if _language == "en" else ","


def N_(text: str) -> str:
    return text


def language_of_windows_id(langid: int) -> str:
    return _WINDOWS_PRIMARY.get(langid & 0x3FF, "")


def system_language() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        return language_of_windows_id(ctypes.windll.kernel32.GetUserDefaultUILanguage())
    except Exception:
        return ""


def resolve_language(setting: str, system: Callable[[], str | None] = system_language) -> str:
    if setting in LANGUAGES:
        return setting
    return "de" if system() == "de" else "en"
