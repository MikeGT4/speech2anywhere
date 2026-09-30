from __future__ import annotations
import json
import logging
import time
import urllib.error
import urllib.request

from kira.permissions_win import check_all, open_microphone_settings

log = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
_RETRY_ATTEMPTS = 20
_RETRY_DELAY_S = 3.0
_REQUEST_TIMEOUT_S = 1.5


def _ollama_reachable_once(timeout: float = _REQUEST_TIMEOUT_S) -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError):
        return False


def _ollama_reachable(
    attempts: int = _RETRY_ATTEMPTS, delay: float = _RETRY_DELAY_S
) -> bool:
    for i in range(attempts):
        if _ollama_reachable_once():
            return True
        if i < attempts - 1:
            time.sleep(delay)
    return False


def _ollama_has_model(model: str) -> bool:
    try:
        with urllib.request.urlopen(
            f"{OLLAMA_URL}/api/tags", timeout=_REQUEST_TIMEOUT_S
        ) as resp:
            data = json.loads(resp.read().decode())
            short = model.split(":")[0]
            return any(m.get("name", "").startswith(short) for m in data.get("models", []))
    except Exception:
        return False


def probe_setup_status() -> tuple[bool, bool]:
    status = check_all()
    return status.microphone, _ollama_reachable()


def show_setup_hint_if_needed(mic_ok: bool, ollama_ok: bool) -> None:
    if mic_ok and ollama_ok:
        return
    if mic_ok and not ollama_ok:
        log.info(
            "Setup hint suppressed: mic_ok=True, ollama_ok=False "
            "(backend likely still booting; polish will fall back to raw)"
        )
        return
    log.info("Setup hint: mic_ok=%s ollama_ok=%s", mic_ok, ollama_ok)
    from kira.ui.setup_hint_dialog import SetupHintDialog

    dlg = SetupHintDialog(mic_ok=mic_ok, ollama_ok=ollama_ok)
    run_modal = getattr(dlg, "exec")
    run_modal()

    if dlg.user_clicked_open_mic_settings:
        open_microphone_settings()


def run_if_needed() -> bool:
    mic_ok, ollama_ok = probe_setup_status()
    show_setup_hint_if_needed(mic_ok, ollama_ok)
    return True


def ensure_ollama_model(model: str) -> bool:
    if not _ollama_reachable_once():
        log.warning("Ollama not reachable, polish will fall back to raw text")
        return False
    if not _ollama_has_model(model):
        log.warning(
            "Ollama model %s not pulled. Run: ollama pull %s", model, model,
        )
        return False
    return True
