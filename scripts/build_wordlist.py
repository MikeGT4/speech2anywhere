# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import argparse
import re
from pathlib import Path
from wordfreq import iter_wordlist, zipf_frequency

LANGUAGES = {
    "de": "Deutsche", "en": "Englische", "fr": "Französische", "it": "Italienische",
    "nl": "Niederländische", "pl": "Polnische", "pt": "Portugiesische", "es": "Spanische",
}
HEADER = (
    "# {name} Wortliste für Kira, erzeugt aus wordfreq (Robyn Speer u. a.).",
    "# Daten: Creative Commons Attribution-ShareAlike 4.0,",
    "# https://creativecommons.org/licenses/by-sa/4.0/",
    "# Quelle: https://github.com/rspeer/wordfreq",
)
_GERMAN_WORD = re.compile(r"[a-zäöüß]+")
_WORD = re.compile(r"[^\W\d_]+")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-zipf", type=float, default=2.5)
    parser.add_argument("--lang", choices=sorted(LANGUAGES), default="de")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out is None:
        args.out = Path(__file__).resolve().parent.parent / "assets" / f"wordlist-{args.lang}.txt"
    pattern = _GERMAN_WORD if args.lang == "de" else _WORD
    words: set[str] = set()
    for word in iter_wordlist(args.lang, wordlist="large"):
        if zipf_frequency(word, args.lang, wordlist="large") < args.min_zipf:
            break
        if pattern.fullmatch(word):
            words.add(word)
    header = [line.format(name=LANGUAGES[args.lang]) for line in HEADER]
    lines = [*header, f"# Zipf ab {args.min_zipf}", *sorted(words)]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(words)} Wörter nach {args.out}")


if __name__ == "__main__":
    main()
