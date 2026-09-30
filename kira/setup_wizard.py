from __future__ import annotations
import html
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download
from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QLabel,
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from kira.firstrun import mark_first_run_complete
from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme

log = logging.getLogger(__name__)


OLLAMA_API_URL = "http://127.0.0.1:11434/api/tags"

DEFAULT_WHISPER_REPO = "Systran/faster-whisper-large-v3"

DEFAULT_GEMMA_TAG = "gemma4:12b"

WHISPER_ALLOWED_FILES: tuple[str, ...] = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "vocabulary.json",
    "preprocessor_config.json",
    "*.txt",
)

def _resolve_ollama_wait_seconds() -> int:
    raw = os.environ.get("KIRA_OLLAMA_INSTALL_WAIT_SECONDS", "60")
    try:
        return int(raw)
    except ValueError:
        log.warning(
            "KIRA_OLLAMA_INSTALL_WAIT_SECONDS=%r ist nicht numerisch - "
            "fallback auf 60s.",
            raw,
        )
        return 60


_OLLAMA_API_WAIT_SECONDS = _resolve_ollama_wait_seconds()

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def find_ollama_exe() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.exists():
            return candidate
    pf = os.environ.get("PROGRAMFILES")
    if pf:
        candidate = Path(pf) / "Ollama" / "ollama.exe"
        if candidate.exists():
            return candidate
    via_path = shutil.which("ollama")
    if via_path:
        return Path(via_path)
    return None


def is_ollama_installed() -> bool:
    return find_ollama_exe() is not None


def is_ollama_reachable(timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_API_URL, timeout=timeout) as response:  # noqa: S310 - hardcoded loopback URL
            return 200 <= response.status < 300
    except (urllib.error.URLError, ConnectionError, socket.timeout, OSError) as exc:
        log.debug("Ollama unreachable: %s", exc)
        return False


def _has_model_tag(stdout: str, tag: str) -> bool:
    for line in stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == tag:
            return True
    return False


class WhisperDownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal(Path)

    def __init__(
        self,
        target_dir: Path,
        repo_id: str = DEFAULT_WHISPER_REPO,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._target_dir = Path(target_dir)
        self._repo_id = repo_id
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        log.info("Whisper-Download startet: repo=%s target=%s",
                 self._repo_id, self._target_dir)
        if self._cancelled.is_set():
            return
        self.status.emit(f"Lade Whisper-Modell ({self._repo_id})...")
        try:
            self._target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.exception("Whisper-Target-Verzeichnis konnte nicht angelegt werden")
            if self._cancelled.is_set():
                return
            self.error.emit(
                f"Whisper-Verzeichnis konnte nicht angelegt werden: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        try:
            local_path = snapshot_download(
                repo_id=self._repo_id,
                local_dir=str(self._target_dir),
                allow_patterns=list(WHISPER_ALLOWED_FILES),
            )
        except Exception as exc:
            log.exception("Whisper-Download fehlgeschlagen")
            if self._cancelled.is_set():
                return
            self.error.emit(f"Whisper-Download fehlgeschlagen: {type(exc).__name__}: {exc}")
            return

        if self._cancelled.is_set():
            return
        log.info("Whisper-Download fertig: %s", local_path)
        self.status.emit("Whisper-Modell bereit.")
        self.finished.emit(Path(local_path))


class OllamaSetupWorker(QThread):
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, installer_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._installer_path = Path(installer_path)
        self._cancelled = threading.Event()
        self._proc: subprocess.Popen | None = None

    def cancel(self) -> None:
        self._cancelled.set()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError as exc:
                log.warning("OllamaSetupWorker.cancel proc.terminate failed: %s", exc)

    def run(self) -> None:
        if self._cancelled.is_set():
            return
        if is_ollama_installed() and is_ollama_reachable():
            log.info("Ollama bereits installiert + erreichbar -> skip install")
            self.status.emit("Ollama bereits installiert.")
            self.finished.emit()
            return

        if not self._installer_path.exists():
            msg = f"Ollama-Installer nicht gefunden: {self._installer_path}"
            log.error(msg)
            self.error.emit(msg)
            return

        self.status.emit("Installiere Ollama...")
        log.info("Starting Ollama installer: %s", self._installer_path)
        try:
            # encoding="utf-8", errors="replace": vor F2-Review fehlte das.
            self._proc = subprocess.Popen(  # noqa: S603 - list-args, kein shell-Parsing
                [str(self._installer_path), "/S", "/NORESTART"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            self.error.emit(f"Ollama-Installer-Start fehlgeschlagen: {exc}")
            return

        try:
            stdout, stderr = self._proc.communicate(timeout=300)
            returncode = self._proc.returncode
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self.error.emit("Ollama-Installer Timeout (>300 s).")
            return
        except OSError as exc:
            self.error.emit(f"Ollama-Installer-Lese-Fehler: {exc}")
            return
        finally:
            self._proc = None

        if self._cancelled.is_set():
            log.info("OllamaSetupWorker cancelled waehrend Install")
            return

        if returncode != 0:
            parts: list[str] = []
            if stdout and stdout.strip():
                parts.append(f"stdout: {stdout.strip()}")
            if stderr and stderr.strip():
                parts.append(f"stderr: {stderr.strip()}")
            combined = "\n".join(parts) or "(kein Output)"
            self.error.emit(
                f"Ollama-Installer Exit-Code {returncode}.\n\n{combined}"
            )
            return

        self.status.emit("Warte auf Ollama-Service...")
        for tick in range(_OLLAMA_API_WAIT_SECONDS):
            if self._cancelled.is_set():
                log.info("OllamaSetupWorker cancelled im Wait-Loop bei %ds", tick)
                return
            if is_ollama_reachable(timeout=2.0):
                log.info("Ollama-Service erreichbar nach %ds", tick)
                self.status.emit("Ollama bereit.")
                self.finished.emit()
                return
            time.sleep(1)

        self.error.emit(
            f"Ollama ist nach {_OLLAMA_API_WAIT_SECONDS} s noch nicht bereit. "
            "Starte den Rechner bitte neu und führe den Assistenten noch einmal aus."
        )


class GemmaPullWorker(QThread):
    progress = pyqtSignal(str)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        model_tag: str = DEFAULT_GEMMA_TAG,
        ollama_exe: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._model_tag = model_tag
        self._ollama_exe = ollama_exe
        self._cancelled = threading.Event()
        self._proc: subprocess.Popen | None = None

    def _ollama_argv(self, *args: str) -> list[str]:
        exe = self._ollama_exe
        if exe is None:
            exe = find_ollama_exe()
        if exe is None:
            return ["ollama", *args]
        return [str(exe), *args]

    def cancel(self) -> None:
        self._cancelled.set()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError as exc:
                log.warning("GemmaPullWorker.cancel proc.terminate failed: %s", exc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError as exc:
                    log.warning("GemmaPullWorker.cancel proc.kill failed: %s", exc)

    def run(self) -> None:
        if self._cancelled.is_set():
            return
        self.status.emit(f"Pruefe ob {self._model_tag} bereits installiert ist...")
        try:
            list_result = subprocess.run(  # noqa: S603 - list-args
                self._ollama_argv("list"),
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
                creationflags=_CREATE_NO_WINDOW,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError, OSError) as exc:
            self.error.emit(
                f"`ollama list` fehlgeschlagen: {type(exc).__name__}: {exc}\n"
                "Ollama-Service evtl. nicht aktiv."
            )
            return

        if self._cancelled.is_set():
            return

        if _has_model_tag(list_result.stdout, self._model_tag):
            log.info("Gemma %s bereits installiert -> skip pull", self._model_tag)
            self.status.emit(f"{self._model_tag} bereits installiert.")
            self.finished.emit()
            return

        self.status.emit(f"Lade {self._model_tag} (~8 GB)...")
        log.info("Starting ollama pull %s", self._model_tag)
        try:
            self._proc = subprocess.Popen(  # noqa: S603 - list-args
                self._ollama_argv("pull", self._model_tag),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            self.error.emit(f"`ollama pull` Start fehlgeschlagen: {exc}")
            return

        proc = self._proc
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if self._cancelled.is_set():
                    break
                line_clean = line.strip()
                if line_clean:
                    self.progress.emit(line_clean)
            returncode = proc.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.error.emit(
                f"`ollama pull {self._model_tag}` ueberzogen 30 min Timeout."
            )
            return
        except OSError as exc:
            self.error.emit(f"`ollama pull` lese-Fehler: {exc}")
            return
        finally:
            self._proc = None

        if self._cancelled.is_set():
            log.info("GemmaPullWorker cancelled waehrend pull")
            return

        if returncode != 0:
            self.error.emit(
                f"`ollama pull {self._model_tag}` fehlgeschlagen "
                f"(Exit-Code {returncode})."
            )
            return

        log.info("Gemma %s installiert", self._model_tag)
        self.status.emit(f"{self._model_tag} bereit.")
        self.finished.emit()


class WelcomePage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Willkommen bei Speech2Anywhere")
        self.setSubTitle(
            "Diktieren mit Politur, gleich startklar."
        )

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Speech2Anywhere braucht beim ersten Start zwei Modelle:\n\n"
            "  - Whisper (Spracherkennung, ~3 GB)\n"
            "  - Gemma (Text-Polish, ~8 GB)\n\n"
            "Zusammen ca. 11 GB Download. Internet erforderlich, einmalig.\n\n"
            "Klicke auf »Weiter«, um fortzufahren."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addStretch(1)


class DownloadPage(QWizardPage):
    def __init__(self, whisper_target: Path, ollama_installer: Path, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Modelle werden installiert")
        self.setSubTitle("Bitte warten. Bei Abbruch geht der Download verloren.")
        self.setCommitPage(True)

        self._whisper_target = whisper_target
        self._ollama_installer = ollama_installer

        self._whisper_done = False
        self._ollama_done = False
        self._gemma_done = False

        self._abort_lock = threading.Lock()
        self._pipeline_aborted = False

        self._whisper_worker: WhisperDownloadWorker | None = None
        self._ollama_worker: OllamaSetupWorker | None = None
        self._gemma_worker: GemmaPullWorker | None = None

        outer = QVBoxLayout(self)

        self._whisper_status = QLabel("Whisper: warte...")
        self._whisper_bar = QProgressBar()
        self._whisper_bar.setRange(0, 0)
        outer.addWidget(self._whisper_status)
        outer.addWidget(self._whisper_bar)

        self._ollama_status = QLabel("Ollama: warte...")
        self._ollama_bar = QProgressBar()
        self._ollama_bar.setRange(0, 0)
        outer.addWidget(self._ollama_status)
        outer.addWidget(self._ollama_bar)

        self._gemma_status = QLabel("Gemma: warte (hängt von Ollama ab)")
        self._gemma_bar = QProgressBar()
        self._gemma_bar.setRange(0, 0)
        outer.addWidget(self._gemma_status)
        outer.addWidget(self._gemma_bar)

        log_label = QLabel("Log:")
        log_label.setFont(QFont())
        outer.addWidget(log_label)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(120)
        self._log.document().setMaximumBlockCount(500)
        outer.addWidget(self._log, stretch=1)

    def isComplete(self) -> bool:  # noqa: N802 - Qt API
        return self._whisper_done and self._ollama_done and self._gemma_done

    def initializePage(self) -> None:
        self._append_log("Starte Downloads...")

        self._whisper_worker = WhisperDownloadWorker(
            target_dir=self._whisper_target,
        )
        self._whisper_worker.status.connect(self._on_whisper_status)
        self._whisper_worker.error.connect(self._on_whisper_error)
        self._whisper_worker.finished.connect(self._on_whisper_finished)

        self._ollama_worker = OllamaSetupWorker(
            installer_path=self._ollama_installer,
        )
        self._ollama_worker.status.connect(self._on_ollama_status)
        self._ollama_worker.error.connect(self._on_ollama_error)
        self._ollama_worker.finished.connect(self._on_ollama_finished)

        self._whisper_worker.start()
        self._ollama_worker.start()

    def _on_whisper_status(self, msg: str) -> None:
        self._whisper_status.setText(f"Whisper: {msg}")
        self._append_log(f"[Whisper] {msg}")

    def _on_whisper_finished(self, path: Path) -> None:
        self._whisper_status.setText(f"Whisper: fertig ({path.name})")
        self._whisper_bar.setRange(0, 1)
        self._whisper_bar.setValue(1)
        self._whisper_done = True
        self._append_log(f"[Whisper] OK -> {path}")
        self.completeChanged.emit()

    def _on_whisper_error(self, msg: str) -> None:
        self._whisper_status.setText("Whisper: FEHLER")
        self._append_log(f"[Whisper FEHLER] {msg}", error=True)
        self._abort_pipeline()

    def _on_ollama_status(self, msg: str) -> None:
        self._ollama_status.setText(f"Ollama: {msg}")
        self._append_log(f"[Ollama] {msg}")

    def _on_ollama_finished(self) -> None:
        self._ollama_status.setText("Ollama: fertig")
        self._ollama_bar.setRange(0, 1)
        self._ollama_bar.setValue(1)
        self._ollama_done = True
        self._append_log("[Ollama] OK")
        self.completeChanged.emit()
        self._start_gemma()

    def _on_ollama_error(self, msg: str) -> None:
        self._ollama_status.setText("Ollama: FEHLER")
        self._append_log(f"[Ollama FEHLER] {msg}", error=True)
        self._abort_pipeline()

    def _start_gemma(self) -> None:
        if self._pipeline_aborted:
            log.info("Gemma-Start übersprungen, Einrichtung abgebrochen")
            self._gemma_status.setText("Gemma: abgebrochen")
            self._append_log("[Gemma] Pipeline abgebrochen, kein Pull")
            return
        self._gemma_status.setText("Gemma: starte...")
        ollama_exe = find_ollama_exe()
        self._gemma_worker = GemmaPullWorker(
            model_tag=DEFAULT_GEMMA_TAG,
            ollama_exe=ollama_exe,
        )
        self._gemma_worker.status.connect(self._on_gemma_status)
        self._gemma_worker.progress.connect(self._on_gemma_progress)
        self._gemma_worker.error.connect(self._on_gemma_error)
        self._gemma_worker.finished.connect(self._on_gemma_finished)
        self._gemma_worker.start()

    def _on_gemma_status(self, msg: str) -> None:
        self._gemma_status.setText(f"Gemma: {msg}")
        self._append_log(f"[Gemma] {msg}")

    def _on_gemma_progress(self, line: str) -> None:
        self._append_log(f"[Gemma] {line}")

    def _on_gemma_finished(self) -> None:
        self._gemma_status.setText("Gemma: fertig")
        self._gemma_bar.setRange(0, 1)
        self._gemma_bar.setValue(1)
        self._gemma_done = True
        self._append_log("[Gemma] OK")
        self.completeChanged.emit()

    def _on_gemma_error(self, msg: str) -> None:
        self._gemma_status.setText("Gemma: FEHLER")
        self._append_log(f"[Gemma FEHLER] {msg}", error=True)
        self._abort_pipeline()

    def _append_log(self, msg: str, error: bool = False) -> None:
        safe = html.escape(msg)
        if error:
            self._log.append(f'<span style="color:#cc0000">{safe}</span>')
        else:
            self._log.append(safe)

    def _abort_pipeline(self) -> None:
        with self._abort_lock:
            if self._pipeline_aborted:
                return
            self._pipeline_aborted = True
        log.warning("Pipeline aborted, stoppe alle Worker")
        self._append_log("[Pipeline] abgebrochen, laufende Worker werden gestoppt", error=True)
        self._stop_all_workers()

    def cleanupPage(self) -> None:
        self._pipeline_aborted = True
        self._stop_all_workers()

    def _stop_all_workers(self) -> None:
        for worker in (self._whisper_worker, self._ollama_worker, self._gemma_worker):
            if worker is None or not worker.isRunning():
                continue
            try:
                worker.cancel()
            except Exception:
                log.exception("worker.cancel() failed")
            worker.wait(2000)
            if worker.isRunning():
                log.warning(
                    "Worker %s nach cancel+wait(2s) noch da -> terminate()",
                    type(worker).__name__,
                )
                worker.terminate()
                worker.wait(5000)


class FinishedPage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle("Setup abgeschlossen")
        self.setSubTitle("Speech2Anywhere ist bereit.")

        layout = QVBoxLayout(self)
        hints = QLabel(
            "So funktioniert's:\n\n"
            "  - F8 gedrückt halten -> sprechen -> loslassen.\n"
            "    Dein Text erscheint am Cursor.\n\n"
            "  - F9 markieren + halten -> Sprach-Befehl auf den\n"
            "    markierten Text (z.B. 'mach den Text formeller').\n\n"
            "  - Tray-Icon (rechts unten) -> Einstellungen,\n"
            "    Anleitung, Updates.\n\n"
            "Klicke auf »Fertigstellen«, um Speech2Anywhere zu starten."
        )
        hints.setWordWrap(True)
        layout.addWidget(hints)
        layout.addStretch(1)


_WIZARD_SIZE = QSize(720, 540)


class SetupWizard(QWizard):
    def __init__(
        self,
        whisper_target: Path,
        ollama_installer: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Speech2Anywhere: Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.WizardOption.NoCancelButtonOnLastPage, True)

        apply_light_theme(self)

        self.setFixedSize(_WIZARD_SIZE)

        self.addPage(WelcomePage(self))
        self.addPage(DownloadPage(whisper_target, ollama_installer, self))
        self.addPage(FinishedPage(self))
        self._comic_look()

    def _comic_look(self) -> None:
        for button, text in (
            (QWizard.WizardButton.NextButton, "Weiter"),
            (QWizard.WizardButton.BackButton, "Zurück"),
            (QWizard.WizardButton.CancelButton, "Abbrechen"),
            (QWizard.WizardButton.FinishButton, "Fertigstellen"),
            (QWizard.WizardButton.CommitButton, "Weiter"),
        ):
            self.setButtonText(button, text)
        for button in (QWizard.WizardButton.NextButton, QWizard.WizardButton.CommitButton,
                       QWizard.WizardButton.FinishButton):
            self.button(button).setObjectName("comicPrimary")
        width = _WIZARD_SIZE.width()
        banner = QPixmap(width, 84)
        banner.fill(QColor(comic.INK))
        painter = QPainter(banner)
        painter.fillRect(0, 80, width, 4, QColor(comic.YELLOW))
        painter.end()
        self.setPixmap(QWizard.WizardPixmap.BannerPixmap, banner)
        logo = comic.mascot_pixmap(56)
        if logo is not None:
            self.setPixmap(QWizard.WizardPixmap.LogoPixmap, logo)
        self.setTitleFormat(Qt.TextFormat.RichText)
        self.setSubTitleFormat(Qt.TextFormat.RichText)
        title_font = comic.load_fonts()[800]
        for page_id in self.pageIds():
            page = self.page(page_id)
            page.setTitle(
                f"<span style='color:#FFFFFF; font-family:\"{title_font}\"; font-size:24px;"
                f" font-weight:800;'>{page.title()}</span>"
            )
            page.setSubTitle(
                f"<span style='color:#DDDDDD; font-family:\"Segoe UI\"; font-size:13px;'>"
                f"{page.subTitle()}</span>"
            )
        self.setStyleSheet(self.styleSheet())

    def _cleanup_running_workers(self) -> None:
        page = self.page(1)
        if isinstance(page, DownloadPage):
            page.cleanupPage()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._cleanup_running_workers()
        super().closeEvent(event)

    def reject(self) -> None:  # noqa: N802 - Qt override
        self._cleanup_running_workers()
        super().reject()

    def accept(self) -> None:  # noqa: N802 - Qt override
        try:
            mark_first_run_complete()
        except (OSError, RuntimeError) as exc:
            log.exception("mark_first_run_complete failed in accept()")
            QMessageBox.warning(
                self,
                "Setup-Marker nicht gespeichert",
                "Speech2Anywhere konnte den Setup-Marker nicht schreiben.\n\n"
                "Beim nächsten Start kann der Assistent erneut erscheinen "
                "(die Modelle sind schon da, es wird nichts neu geladen).\n\n"
                "Pfad: %APPDATA%\\Kira\\\n"
                f"Fehler: {type(exc).__name__}: {exc}"
            )
        super().accept()
