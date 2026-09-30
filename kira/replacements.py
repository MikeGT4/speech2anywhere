from __future__ import annotations
import re
from collections.abc import Callable


def apply(
    text: str,
    mapping: dict[str, str],
    on_replace: Callable[[str, str], None] | None = None,
) -> str:
    if not text or not mapping:
        return text
    keys = sorted((k for k in mapping if k and k.strip()), key=len, reverse=True)
    if not keys:
        return text
    lookup = {k.lower(): mapping[k] for k in keys}
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(k) for k in keys) + r")(?!\w)",
        re.IGNORECASE,
    )

    def _substitute(match: re.Match) -> str:
        found = match.group(0)
        replacement = lookup.get(found.lower(), found)
        if on_replace is not None:
            on_replace(found, replacement)
        return replacement

    return pattern.sub(_substitute, text)
