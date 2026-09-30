from __future__ import annotations
import logging
import subprocess
from dataclasses import dataclass
import sounddevice as sd

log = logging.getLogger(__name__)


@dataclass
class PermissionStatus:
    microphone: bool

    @property
    def all_granted(self) -> bool:
        return self.microphone


def check_microphone() -> bool:
    try:
        with sd.InputStream(samplerate=16000, channels=1, blocksize=160):
            return True
    except Exception as exc:
        log.debug("microphone check failed: %s", exc)
        return False


def check_all() -> PermissionStatus:
    return PermissionStatus(microphone=check_microphone())


def open_microphone_settings() -> None:
    subprocess.Popen(["start", "ms-settings:privacy-microphone"], shell=True)
