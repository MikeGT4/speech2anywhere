# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import logging
import re
from functools import lru_cache
from pathlib import Path
from kira._resources import assets_dir

log = logging.getLogger(__name__)
WORDLIST_FILE = "wordlist-de.txt"
_WORD_RE = re.compile(r"[^\W\d_]+")


def load_wordlist(path: Path) -> frozenset[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        log.warning("Wortliste nicht lesbar: %s", path)
        return frozenset()
    return frozenset(
        line.strip().casefold()
        for line in lines
        if line.strip() and not line.startswith("#")
    )


@lru_cache(maxsize=1)
def default_wordlist() -> frozenset[str]:
    return load_wordlist(assets_dir() / WORDLIST_FILE)


def is_common(phrase: str, words: frozenset[str]) -> bool:
    tokens = _WORD_RE.findall(phrase.casefold())
    return bool(tokens) and all(t in words for t in tokens)
