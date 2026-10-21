# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import time
from typing import Callable

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QProgressDialog

from kira import progress as prog


class ProgressView(QObject):
    def __init__(
        self,
        bar,
        set_text: Callable[[str], None],
        head: str = "",
        amount: Callable[[float, float], str] = prog.size_text,
        with_rate: bool = True,
        total_only: Callable[[float], str] | None = prog.total_text,
        stall: float | None = 15.0,
        clock: Callable[[], float] = time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._bar = bar
        self._set_text = set_text
        self._head = head
        self._amount = amount
        self._with_rate = with_rate
        self._total_only = total_only
        self._clock = clock
        self._stall = stall
        self._meter = prog.RateMeter(clock=clock, stall=stall)
        self._done = 0.0
        self._total = 0.0
        self._stopped = False
        self._turn = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._render)
        if isinstance(bar, QProgressDialog):
            bar.setAutoReset(False)
            bar.setAutoClose(False)

    def busy(self, text: str) -> None:
        if self._dead():
            return
        self._turn += 1
        self._timer.stop()
        self._bar.setRange(0, 0)
        self._show(text)

    def amount(self, done: float, total: float) -> None:
        if self._dead():
            return
        if total <= 0:
            self.busy(prog.STARTING)
            return
        self._turn += 1
        self._done, self._total = float(done), float(total)
        self._meter.add(self._done)
        if not self._timer.isActive():
            self._timer.start()
        self._render()

    def finish(self, text: str) -> None:
        if self._dead():
            return
        self._restart()
        self._bar.setRange(0, 1)
        self._bar.setValue(1)
        self._show(text)

    def idle(self, text: str) -> None:
        if self._dead():
            return
        self._restart()
        self._bar.setRange(0, 1)
        self._bar.setValue(0)
        self._show(text)

    def stop(self) -> None:
        self._stopped = True
        self._turn += 1
        self._timer.stop()

    def _restart(self) -> None:
        self._turn += 1
        self._timer.stop()
        self._meter = prog.RateMeter(clock=self._clock, stall=self._stall)
        self._done = self._total = 0.0

    def _dead(self) -> bool:
        if self._stopped or (isinstance(self._bar, QProgressDialog) and self._bar.wasCanceled()):
            self._timer.stop()
            return True
        return False

    def _render(self) -> None:
        if self._dead() or self._total <= 0:
            return
        if self._done >= self._total:
            self._timer.stop()
            self._bar.setRange(0, 0)
            self._show(prog.FINISHING)
            return
        waiting = self._total_only is not None and prog.unmeasured(self._done, self._total, self._meter)
        if waiting or self._meter.stalled():
            self._bar.setRange(0, 0)
        else:
            maximum, value = prog.bar_scale(self._done, self._total)
            self._bar.setRange(0, maximum)
            turn = self._turn
            self._bar.setValue(value)
            if turn != self._turn or self._dead():
                return
        self._show(prog.describe(self._done, self._total, self._meter, self._amount, self._with_rate, self._total_only))

    def _show(self, text: str) -> None:
        self._set_text(f"{self._head}{text}")
