from __future__ import annotations
import logging
from typing import Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal

log = logging.getLogger(__name__)


class MainThreadMarshal(QObject):
    _request = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._request.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    def _dispatch(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:
            log.exception("marshalled call failed")

    def run_on_main_thread(self, fn: Callable[[], None]) -> None:
        self._request.emit(fn)
