from __future__ import annotations
import subprocess
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class PermissionStatus:
    microphone: bool
    accessibility: bool
    input_monitoring: bool

    @property
    def all_granted(self) -> bool:
        return self.microphone and self.accessibility and self.input_monitoring


def check_microphone() -> bool:
    try:
        import sounddevice as sd
        with sd.InputStream(samplerate=16000, channels=1, blocksize=160):
            return True
    except Exception as exc:
        log.debug("microphone check failed: %s", exc)
        return False


def check_accessibility() -> bool:
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception as exc:
        log.debug("accessibility check failed: %s", exc)
        return False


def check_input_monitoring() -> bool:
    try:
        from pynput import keyboard
        listener = keyboard.Listener(on_press=lambda k: False)
        listener.start()
        listener.stop()
        return True
    except Exception as exc:
        log.debug("input monitoring check failed: %s", exc)
        return False


def check_all() -> PermissionStatus:
    return PermissionStatus(
        microphone=check_microphone(),
        accessibility=check_accessibility(),
        input_monitoring=check_input_monitoring(),
    )


SETTINGS_URLS = {
    "microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "input_monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
}


def open_settings(pane: str) -> None:
    url = SETTINGS_URLS.get(pane)
    if url:
        subprocess.Popen(["open", url])
