# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import re
from typing import Collection
from kira.lexicon import Entry
from kira.phonetics import is_similar

GLOSSARY_MAX_TERMS = 5
GLOSSARY_MIN_SOUND = 0.8
_WORD_RE = re.compile(r"\w+")


def _grams(text: str) -> list[str]:
    words = [w.casefold() for w in _WORD_RE.findall(text)]
    grams: list[str] = []
    for n in (1, 2, 3):
        grams.extend(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))
    return grams


def _normalized(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.casefold()))


def uncertain_tokens(words: Collection[str]) -> set[str]:
    return {w for word in words for w in _WORD_RE.findall(word.casefold())}


def touches(gram: str, tokens: set[str]) -> bool:
    return any(w in tokens for w in gram.split())


def select_glossary(
    text: str, entries: list[Entry],
    limit: int = GLOSSARY_MAX_TERMS, threshold: float = GLOSSARY_MIN_SOUND,
    uncertain: Collection[str] | None = None,
) -> list[str]:
    if not text or not entries:
        return []
    grams = list(dict.fromkeys(_grams(text)))
    present = set(grams)
    if uncertain is not None:
        tokens = uncertain_tokens(uncertain)
        sound_grams = [g for g in grams if touches(g, tokens)]
    else:
        sound_grams = grams
    chosen: list[str] = []
    seen: set[str] = set()
    for entry in sorted(entries, key=lambda e: (-e.count, e.right.casefold())):
        right = _normalized(entry.right)
        if right in seen or right in present:
            continue
        if _normalized(entry.wrong) in present or any(
            is_similar(g, entry.right, threshold) for g in sound_grams
        ):
            chosen.append(entry.right)
            seen.add(right)
            if len(chosen) >= limit:
                break
    return chosen
