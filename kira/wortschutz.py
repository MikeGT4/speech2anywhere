# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import difflib
import re
from typing import Collection

from kira.glossary import uncertain_tokens

MAX_SUFFIX_DIFF = 2
_KEY_RE = re.compile(r"[^\W_]+")
_TRAILING_RE = re.compile(r"[^\w]+$")
_SENTENCE_END = (".", "!", "?", ":")
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _key(token: str) -> str:
    return "".join(_KEY_RE.findall(token.casefold()))


def _close(a: str, b: str) -> bool:
    if a == b or a.translate(_UMLAUTS) == b.translate(_UMLAUTS):
        return True
    short, long_ = sorted((a, b), key=len)
    return bool(short) and long_.startswith(short) and len(long_) - len(short) <= MAX_SUFFIX_DIFF


def _acceptable(src: list[str], dst: list[str], allowed: set[str]) -> bool:
    if "".join(src) == "".join(dst):
        return True
    if dst and all(k.isdigit() for k in dst):
        return True
    if dst and all(k in allowed for k in dst):
        return True
    return len(src) == len(dst) and all(_close(a, b) for a, b in zip(src, dst))


def _restore(source_tokens: list[str], polished_tokens: list[str], out: list[str]) -> list[str]:
    restored = list(source_tokens)
    if not restored:
        return restored
    trailing = _TRAILING_RE.search(polished_tokens[-1]) if polished_tokens else None
    restored[-1] = _TRAILING_RE.sub("", restored[-1]) + (trailing.group(0) if trailing else "")
    at_start = not out or out[-1].endswith(_SENTENCE_END)
    first = restored[0]
    if at_start and first[:1].islower():
        restored[0] = first[:1].upper() + first[1:]
    return restored


def protect(
    source: str, polished: str, uncertain: Collection[str],
    allowed: Collection[str] = (),
) -> tuple[str, list[tuple[str, str]]]:
    src_tokens = source.split()
    dst_tokens = polished.split()
    src_keys = [_key(t) for t in src_tokens]
    dst_keys = [_key(t) for t in dst_tokens]
    unsure = uncertain_tokens(uncertain)
    allowed_keys = {_key(w) for term in allowed for w in term.split()}
    out: list[str] = []
    reverted: list[tuple[str, str]] = []
    matcher = difflib.SequenceMatcher(a=src_keys, b=dst_keys, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        span = dst_tokens[j1:j2]
        if op == "equal" or op == "delete":
            out.extend(span)
            continue
        src = [k for k in src_keys[i1:i2] if k]
        dst = [k for k in dst_keys[j1:j2] if k]
        if not dst:
            out.extend(span)
            continue
        if op == "insert":
            if all(k in allowed_keys for k in dst):
                out.extend(span)
            else:
                reverted.append(("", " ".join(span)))
            continue
        touched_unsure = any(w in unsure for k in src_tokens[i1:i2] for w in uncertain_tokens([k]))
        if touched_unsure or _acceptable(src, dst, allowed_keys):
            out.extend(span)
            continue
        restored = _restore(src_tokens[i1:i2], span, out)
        reverted.append((" ".join(span), " ".join(restored)))
        out.extend(restored)
    if not reverted:
        return polished, reverted
    return " ".join(out), reverted
