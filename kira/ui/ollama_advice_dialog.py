# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressDialog, QPushButton

from kira import progress as prog
from kira._resources import assets_dir
from kira.ollama_advice import ELSEWHERE, PORT, REMOTE, Advice, windows_ollama_dir
from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme, light_critical, light_information
from kira.ui._progress_view import ProgressView
from kira.updater import download_asset, matches_sha256

log = logging.getLogger(__name__)

SIGNER_PARTS = ("CN=Ollama Inc.", "O=Ollama Inc.")
DETACHED = 0x00000008 | 0x00000200
CREATE_NO_WINDOW = 0x08000000
OLLAMA_PROCESSES = frozenset({"ollama app.exe", "ollama.exe", "llama-server.exe", "ollama_llama_server.exe"})
CHECKING = "Prüfsumme und Signatur werden geprüft …"

_orphans: list[tuple[QThread, QObject]] = []


class _Cancelled(Exception):
    pass


def setup_dir(version: str) -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Kira" / "update"
    return base / f"ollama-{version}"


def bundled_setup() -> Path | None:
    from kira.app_update import install_root

    root = install_root()
    if root is None:
        return None
    path = root.parent / "installer" / "embedded" / "OllamaSetup.exe"
    return path if path.exists() else None


def _matches(path: Path, advice: Advice) -> bool:
    return (path.exists() and (not advice.size or path.stat().st_size == advice.size)
            and matches_sha256(path, advice.sha256))


def powershell_exe() -> str:
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    return str(Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")


def signature_ok(path: Path, run=subprocess.run) -> bool:
    script = (
        "$s = Get-AuthenticodeSignature -LiteralPath $env:S2A_PRUEFDATEI; "
        "Write-Output $s.Status; Write-Output $s.SignerCertificate.Subject"
    )
    try:
        result = run(
            [powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=120, creationflags=CREATE_NO_WINDOW,
            env=dict(os.environ, S2A_PRUEFDATEI=str(path)),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Signaturprüfung nicht ausführbar: %s", exc)
        return False
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    parts = {part.strip() for part in lines[1].split(",")} if len(lines) >= 2 else set()
    ok = len(lines) >= 2 and lines[0] == "Valid" and all(part in parts for part in SIGNER_PARTS)
    log.info("Signatur von %s: %s", path.name, " | ".join(lines[:2]) or result.returncode)
    return ok


def _inside(exe: str, folder: Path) -> bool:
    try:
        return Path(exe).resolve().is_relative_to(folder.resolve())
    except (OSError, ValueError):
        return False


def stop_ollama(folder: Path | None, processes=None) -> int:
    if folder is None:
        return 0
    if processes is None:
        import psutil
        processes = list(psutil.process_iter(["name", "exe"]))
    stopped = 0
    for proc in processes:
        info = getattr(proc, "info", None) or {}
        name = str(info.get("name") or "").lower()
        if name not in OLLAMA_PROCESSES or not _inside(str(info.get("exe") or ""), folder):
            continue
        try:
            proc.terminate()
            proc.wait(5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                log.warning("Ollama-Prozess %s ließ sich nicht beenden", name)
                continue
        stopped += 1
    log.info("Ollama-Prozesse beendet: %d", stopped)
    return stopped


def launch_setup(path: Path, popen=subprocess.Popen):
    return popen([str(path)], creationflags=DETACHED, close_fds=True)


def ollama_running(folder: Path | None, processes=None) -> bool:
    if folder is None:
        return False
    if processes is None:
        import psutil
        processes = list(psutil.process_iter(["name", "exe"]))
    for proc in processes:
        info = getattr(proc, "info", None) or {}
        if str(info.get("name") or "").lower() == "ollama.exe" and _inside(str(info.get("exe") or ""), folder):
            return True
    return False


def watch_setup(setup, folder: Path | None, running=ollama_running, restart=None,
                settle_s: float = 15.0) -> threading.Thread:
    restart = restart or start_ollama_app

    def wait_and_check() -> None:
        try:
            setup.wait()
        except Exception:
            log.debug("Warten auf das Ollama-Setup fehlgeschlagen", exc_info=True)
        threading.Event().wait(settle_s)
        if not running(folder):
            log.info("Ollama-Setup beendet, Ollama läuft nicht, starte es wieder")
            restart(folder)

    thread = threading.Thread(target=wait_and_check, daemon=True, name="kira-ollama-setup")
    thread.start()
    return thread


def start_ollama_app(folder: Path | None, popen=subprocess.Popen) -> None:
    app = folder / "ollama app.exe" if folder is not None else None
    if app is None or not app.is_file():
        return
    try:
        popen([str(app)], creationflags=DETACHED, close_fds=True)
    except OSError:
        log.warning("Ollama ließ sich nicht wieder starten: %s", app)


class _SetupWorker(QObject):
    progress = pyqtSignal('qint64', 'qint64')
    phase = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, advice: Advice, target: Path, bundled: Path | None = None) -> None:
        super().__init__()
        self._advice = advice
        self._target = target
        self._bundled = bundled
        self._cancelled = False
        self._throttle = prog.Throttle()

    def cancel(self) -> None:
        self._cancelled = True

    def _on_bytes(self, done: int, total: int) -> None:
        if self._cancelled:
            raise _Cancelled()
        if self._throttle.due(force=0 < total <= done):
            self.progress.emit(done, total)

    def run(self) -> None:
        a = self._advice
        try:
            self.phase.emit(CHECKING)
            if self._bundled is not None and _matches(self._bundled, a):
                target = self._bundled
                log.info("Ollama-Setup %s liegt bei Speech2Anywhere: %s", a.tested, target)
            else:
                target = self._target
                if not _matches(target, a):
                    self.phase.emit(prog.STARTING)
                    download_asset(a.url, target, on_bytes=self._on_bytes)
                    self.phase.emit(CHECKING)
                if not matches_sha256(target, a.sha256):
                    target.unlink(missing_ok=True)
                    self.finished.emit(False, "Die Prüfsumme des Ollama-Setups passt nicht. Es wird nicht gestartet.")
                    return
            if not signature_ok(target):
                self.finished.emit(False, "Die Signatur des Ollama-Setups ist nicht gültig. Es wird nicht gestartet.")
                return
            if self._cancelled:
                self.finished.emit(False, "Abgebrochen.")
                return
            self.finished.emit(True, str(target))
        except _Cancelled:
            self.finished.emit(False, "Abgebrochen.")
        except Exception as exc:
            if self._cancelled:
                self.finished.emit(False, "Abgebrochen.")
                return
            log.exception("Ollama-Setup: Download fehlgeschlagen")
            self.finished.emit(False, f"Das Ollama-Setup ließ sich nicht laden: {exc}")


_ELSEWHERE_TEXT = {
    PORT: "Am Ollama-Port antwortet ein anderes Ollama als das installierte Windows-Programm, etwa in WSL "
          "oder Docker. Bitte dort aktualisieren.",
    REMOTE: "Ollama läuft auf einem anderen Rechner. Bitte dort aktualisieren.",
    ELSEWHERE: "Ollama läuft hier nicht als Windows-Programm im Standardordner. Bitte von Hand aktualisieren.",
}


def _close_quietly(progress: QProgressDialog, cancel: Callable[[], None], view: ProgressView) -> None:
    view.stop()
    try:
        progress.canceled.disconnect(cancel)
    except (TypeError, RuntimeError):
        pass
    progress.close()


def _value(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("comicValue")
    label.setWordWrap(True)
    return label


def _left(widget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(widget)
    row.addStretch()
    return row


class OllamaAdviceDialog(QDialog):
    def __init__(
        self,
        advice: list[Advice],
        on_declined: Callable[[str], None],
        parent=None,
        app_version: str = "",
        on_handled: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Speech2Anywhere: Empfehlung zu Ollama")
        icon_path = assets_dir() / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setModal(True)
        self.setMinimumWidth(720)
        apply_light_theme(self)
        self._advice = list(advice)
        self._on_declined = on_declined
        self._on_handled = on_handled or (lambda key: None)
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._cancel: Callable[[], None] | None = None
        self.buttons: dict[str, QPushButton] = {}
        body = comic.dialog_frame(self, "Ollama")
        card = comic.ComicCard("Geprüfte Fassung", comic.mascot_pixmap(32))
        release = f"Speech2Anywhere {app_version}" if app_version else "Diese Fassung von Speech2Anywhere"
        for item in self._advice:
            if item.kind == "ollama":
                sub = f"Installiert {item.installed}, geprüft {item.tested}."
                if item.local:
                    button = QPushButton("Aktualisieren…")
                    button.setToolTip(
                        f"Nimmt das mitgelieferte Ollama-Setup {item.tested} oder lädt es von github.com/ollama/ollama,\n"
                        "prüft Prüfsumme und Signatur und startet es. Ollama wird dafür kurz beendet."
                    )
                    button.clicked.connect(lambda _c=False, a=item: self._update_ollama(a))
                    self.buttons["ollama"] = button
                    card.add_row("Ollama", sub, _left(button))
                else:
                    card.add_row("Ollama", sub, _value(_ELSEWHERE_TEXT.get(item.where, _ELSEWHERE_TEXT[REMOTE])))
            elif item.kind == "model":
                button = QPushButton("Aktualisieren…")
                button.setToolTip(f"Lädt {item.model} per ollama pull neu.")
                button.clicked.connect(lambda _c=False, a=item: self._update_model(a))
                self.buttons["model"] = button
                card.add_row("Politur-Modell", item.model, _left(button))
        note = _value(f"{release} ist mit diesen Fassungen gemessen. Gemeldet wird nur, was geprüft ist.")
        note.setContentsMargins(0, 8, 0, 6)
        card.add_note(note)
        body.addWidget(card)
        body.addStretch()
        later = QPushButton("Nicht mehr erinnern")
        later.setObjectName("comicLink")
        later.clicked.connect(self._decline)
        self.buttons["decline"] = later
        close = QPushButton("Schließen")
        close.setObjectName("comicPrimary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        body.addLayout(comic.footer_row(later, close))

    def _decline(self) -> None:
        for item in self._advice:
            self._on_declined(item.key)
        self.accept()

    def _confirm(self, text: str, detail: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Speech2Anywhere: Ollama")
        box.setText(text)
        box.setInformativeText(detail)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        apply_light_theme(box)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _progress(self, head: str, text: str) -> tuple[QProgressDialog, ProgressView]:
        progress = QProgressDialog(f"{head}{text}", "Abbrechen", 0, 0, self)
        progress.setWindowTitle("Speech2Anywhere: Ollama")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        apply_light_theme(progress)
        view = ProgressView(progress, progress.setLabelText, head, parent=progress)
        progress.show()
        return progress, view

    def _update_ollama(self, advice: Advice) -> None:
        size_gb = f"{advice.size / prog.GB:.1f}".replace(".", ",") if advice.size else "?"
        if not advice.url or not advice.sha256:
            light_critical(self, "Speech2Anywhere", "Für dieses Ollama-Setup fehlt die geprüfte Prüfsumme.")
            return
        if not self._confirm(
            f"Ollama auf {advice.tested} aktualisieren?",
            "Speech2Anywhere nimmt das mitgelieferte Setup, wenn es genau diese Fassung ist, sonst lädt es "
            f"das Setup von github.com/ollama/ollama (rund {size_gb} GB). Es prüft Prüfsumme und Signatur "
            "und startet das Setup. Ollama wird dafür beendet; eine laufende Politur bricht ab und kommt "
            "als Rohtext.",
        ):
            return
        progress, view = self._progress(f"Ollama-Setup {advice.tested}\n", CHECKING)
        thread = QThread()
        worker = _SetupWorker(advice, setup_dir(advice.tested) / "OllamaSetup.exe", bundled_setup())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        state = {"cancelled": False}

        def cancel() -> None:
            state["cancelled"] = True
            worker.cancel()

        def on_finished(ok: bool, message: str) -> None:
            _close_quietly(progress, cancel, view)
            thread.quit()
            thread.wait()
            if self._cancel is cancel:
                self._cancel = None
            if state["cancelled"] or message == "Abgebrochen.":
                log.info("Ollama-Update abgebrochen")
                return
            if not ok:
                light_critical(self, "Speech2Anywhere", message)
                return
            folder = windows_ollama_dir()
            stop_ollama(folder)
            try:
                watch_setup(launch_setup(Path(message)), folder)
            except Exception as exc:
                log.exception("Ollama-Setup ließ sich nicht starten")
                start_ollama_app(folder)
                light_critical(self, "Speech2Anywhere", f"Das Ollama-Setup ließ sich nicht starten: {exc}\n\n{message}")
                return
            log.info("Ollama-Setup %s gestartet: %s", advice.tested, message)
            self._on_handled(advice.key)
            light_information(
                self, "Speech2Anywhere",
                "Das Ollama-Setup läuft. Danach startet Ollama von selbst, und Speech2Anywhere poliert wieder.",
            )
            self.accept()

        worker.progress.connect(view.amount)
        worker.phase.connect(view.busy)
        worker.finished.connect(on_finished)
        progress.canceled.connect(cancel)
        self._thread, self._worker, self._cancel = thread, worker, cancel
        thread.start()

    def _update_model(self, advice: Advice) -> None:
        from kira.ui.settings_dialog import _PullWorker

        if not self._confirm(
            f"{advice.model} neu laden?",
            "Speech2Anywhere lädt das Modell per ollama pull aus der Ollama-Bibliothek. Das kann je nach "
            "Modell einige Gigabyte sein.",
        ):
            return
        progress, view = self._progress(f"Lade {advice.model}\n", prog.STARTING)
        thread = QThread()
        worker = _PullWorker(advice.model)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        seen = {"bytes": False}

        def on_progress(status: str, completed: int, total: int) -> None:
            if total > 0 and not prog.final_status(status):
                seen["bytes"] = True
                view.amount(completed, total)
            else:
                view.busy(prog.pull_phase(status, seen["bytes"]))

        state = {"cancelled": False}

        def cancel() -> None:
            state["cancelled"] = True
            worker.cancel()

        def on_finished(ok: bool, message: str) -> None:
            _close_quietly(progress, cancel, view)
            thread.quit()
            thread.wait()
            if self._cancel is cancel:
                self._cancel = None
            if state["cancelled"] or message == "Abgebrochen.":
                log.info("Modell-Update abgebrochen")
                return
            if not ok:
                light_critical(self, "Speech2Anywhere", message)
                return
            self._on_declined(advice.key)
            light_information(self, "Speech2Anywhere", f"{advice.model} ist neu geladen.")
            self.accept()

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        progress.canceled.connect(cancel)
        self._thread, self._worker, self._cancel = thread, worker, cancel
        thread.start()

    def _shutdown(self) -> None:
        worker, thread, cancel = self._worker, self._thread, self._cancel
        self._worker = self._thread = self._cancel = None
        if cancel is not None:
            cancel()
        if thread is not None and thread.isRunning():
            thread.quit()
            if not thread.wait(3000) and worker is not None:
                log.warning("Ollama-Dialog geschlossen, Hintergrundaufgabe läuft noch aus")
                _orphans.append((thread, worker))

    def done(self, result: int) -> None:
        self._shutdown()
        super().done(result)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._shutdown()
        super().closeEvent(event)
