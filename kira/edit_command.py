from __future__ import annotations
import logging
import time
import keyboard
import pyperclip

log = logging.getLogger(__name__)


class ClipboardUnavailable(RuntimeError):
    pass


_CTRL_C_SETTLE_MS = 100


def read_selection() -> str | None:
    try:
        saved = pyperclip.paste()
    except Exception as exc:
        raise ClipboardUnavailable(
            f"Clipboard-Lesen vor Strg+C fehlgeschlagen: {exc}"
        ) from exc

    try:
        pyperclip.copy("")
    except Exception as exc:
        raise ClipboardUnavailable(
            f"Clipboard-Schreiben (clear) fehlgeschlagen: {exc}"
        ) from exc

    try:
        keyboard.send("ctrl+c")
    except Exception as exc:
        try:
            pyperclip.copy(saved)
        except Exception:
            pass
        raise ClipboardUnavailable(
            f"keyboard.send(ctrl+c) fehlgeschlagen: {exc}"
        ) from exc

    time.sleep(_CTRL_C_SETTLE_MS / 1000.0)

    try:
        result = pyperclip.paste()
    except Exception as exc:
        try:
            pyperclip.copy(saved)
        except Exception:
            pass
        raise ClipboardUnavailable(
            f"Clipboard-Lesen nach Strg+C fehlgeschlagen: {exc}"
        ) from exc

    try:
        pyperclip.copy(saved)
    except Exception:
        log.warning("clipboard restore after selection-capture failed")

    if not result:
        log.info("read_selection: no selection (Strg+C did not change clipboard)")
        return None
    log.info("read_selection: captured %d chars", len(result))
    return result
