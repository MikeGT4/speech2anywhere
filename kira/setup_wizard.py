from __future__ import annotations
import html
import json
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
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from kira import hardware, ollama_pull, progress as prog
from kira.firstrun import mark_first_run_complete
from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme
from kira.ui._progress_view import ProgressView
from kira.ui.measure_animation import MeasureAnimation
from kira.texte import tr

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

WHISPER_FETCH_MODULE = "kira._whisper_fetch"

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

OLLAMA_SETUP_SWITCHES = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")


def _taskkill_exe() -> str:
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    return str(Path(root) / "System32" / "taskkill.exe")


def stop_process_tree(proc: subprocess.Popen) -> None:
    try:
        subprocess.run(  # noqa: S603
            [_taskkill_exe(), "/T", "/F", "/PID", str(proc.pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Ollama-Setup ließ sich nicht samt Unterprozessen beenden: %s", exc)
        try:
            proc.kill()
        except OSError as kill_exc:
            log.warning("Ollama-Setup ließ sich nicht beenden: %s", kill_exc)


def launch_fetch(repo_id: str, target_dir: Path) -> subprocess.Popen:
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-P", "-m", WHISPER_FETCH_MODULE, repo_id, str(target_dir), *WHISPER_ALLOWED_FILES],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_CREATE_NO_WINDOW,
    )


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
    progress = pyqtSignal('qint64', 'qint64')
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
        self._proc: subprocess.Popen | None = None

    def cancel(self) -> None:
        self._cancelled.set()
        self._stop_fetch()

    def _stop_fetch(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError as exc:
                log.warning("Whisper-Download ließ sich nicht beenden: %s", exc)

    def _follow(self, proc: subprocess.Popen) -> tuple[str | None, dict | None]:
        local_path = None
        failure = None
        for line in proc.stdout:
            try:
                message = json.loads(line)
            except ValueError:
                log.debug("Whisper-Download meldet: %s", line.rstrip())
                continue
            if not isinstance(message, dict):
                continue
            if "done" in message:
                self.progress.emit(int(message["done"]), int(message["total"]))
            elif "path" in message:
                local_path = str(message["path"])
            elif "error" in message:
                failure = message
        return local_path, failure

    def run(self) -> None:
        log.info("Whisper-Download startet: repo=%s target=%s",
                 self._repo_id, self._target_dir)
        if self._cancelled.is_set():
            return
        self.status.emit(tr("Lade Whisper-Modell ({})...").format(self._repo_id))
        try:
            self._target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.exception("Whisper-Target-Verzeichnis konnte nicht angelegt werden")
            if self._cancelled.is_set():
                return
            self.error.emit(
                tr("Whisper-Verzeichnis konnte nicht angelegt werden: {}: {}").format(type(exc).__name__, exc)
            )
            return

        try:
            self._proc = launch_fetch(self._repo_id, self._target_dir)
        except OSError as exc:
            log.exception("Whisper-Download ließ sich nicht starten")
            if self._cancelled.is_set():
                return
            self.error.emit(tr("Whisper-Download fehlgeschlagen: {}: {}").format(type(exc).__name__, exc))
            return

        if self._cancelled.is_set():
            self._stop_fetch()
        try:
            local_path, failure = self._follow(self._proc)
            returncode = self._proc.wait()
        except OSError as exc:
            log.exception("Whisper-Download: Verbindung zum Ladeprozess verloren")
            local_path, failure, returncode = None, {"error": f"{type(exc).__name__}: {exc}"}, None
        finally:
            self._proc = None

        if self._cancelled.is_set():
            log.info("Whisper-Download abgebrochen")
            return
        if local_path is None:
            if failure is not None:
                log.error("Whisper-Download fehlgeschlagen: %s\n%s", failure.get("error"), failure.get("trace", ""))
                self.error.emit(tr("Whisper-Download fehlgeschlagen: {}").format(failure.get('error')))
            else:
                log.error("Whisper-Download endete mit Exit-Code %s ohne Ergebnis", returncode)
                self.error.emit(tr("Whisper-Download fehlgeschlagen: Exit-Code {}.").format(returncode))
            return
        if returncode != 0:
            log.warning("Whisper-Ladeprozess endete nach dem Download mit Exit-Code %s", returncode)
        log.info("Whisper-Download fertig: %s", local_path)
        self.status.emit(tr("Whisper-Modell bereit."))
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
        self._stop_setup()

    def _stop_setup(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            stop_process_tree(proc)

    def run(self) -> None:
        if self._cancelled.is_set():
            return
        if is_ollama_installed() and is_ollama_reachable():
            log.info("Ollama bereits installiert + erreichbar -> skip install")
            self.status.emit(tr("bereits installiert"))
            self.finished.emit()
            return

        if not self._installer_path.exists():
            msg = tr("Ollama-Installer nicht gefunden: {}").format(self._installer_path)
            log.error(msg)
            self.error.emit(msg)
            return

        self.status.emit(tr("wird installiert …"))
        log.info("Starting Ollama installer: %s", self._installer_path)
        try:
            self._proc = subprocess.Popen(  # noqa: S603 - list-args, kein shell-Parsing
                [str(self._installer_path), *OLLAMA_SETUP_SWITCHES],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
            )
        except OSError as exc:
            self.error.emit(tr("Ollama-Installer-Start fehlgeschlagen: {}").format(exc))
            return

        if self._cancelled.is_set():
            self._stop_setup()
        try:
            returncode = self._proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            stop_process_tree(self._proc)
            self.error.emit(tr("Ollama-Installer Timeout (>300 s)."))
            return
        except OSError as exc:
            self.error.emit(tr("Warten auf den Ollama-Installer fehlgeschlagen: {}").format(exc))
            return
        finally:
            self._proc = None

        if self._cancelled.is_set():
            log.info("OllamaSetupWorker cancelled waehrend Install")
            return

        if returncode != 0:
            self.error.emit(tr("Ollama-Installer Exit-Code {}.").format(returncode))
            return

        self.status.emit(tr("wartet auf den Ollama-Dienst …"))
        for tick in range(_OLLAMA_API_WAIT_SECONDS):
            if self._cancelled.is_set():
                log.info("OllamaSetupWorker cancelled im Wait-Loop bei %ds", tick)
                return
            if is_ollama_reachable(timeout=2.0):
                log.info("Ollama-Service erreichbar nach %ds", tick)
                self.status.emit(tr("bereit"))
                self.finished.emit()
                return
            time.sleep(1)

        self.error.emit(
            tr(
                "Ollama ist nach {} s noch nicht bereit. Starte den Rechner bitte neu und führe den Assistenten "
                "noch einmal aus."
            ).format(_OLLAMA_API_WAIT_SECONDS)
        )


class GemmaPullWorker(QThread):
    progress = pyqtSignal(str, 'qint64', 'qint64')
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
        self._download = ollama_pull.ModelPull(model_tag)

    def _ollama_argv(self, *args: str) -> list[str]:
        exe = self._ollama_exe
        if exe is None:
            exe = find_ollama_exe()
        if exe is None:
            return ["ollama", *args]
        return [str(exe), *args]

    def cancel(self) -> None:
        self._cancelled.set()
        self._download.cancel()

    def run(self) -> None:
        if self._cancelled.is_set():
            return
        self.status.emit(tr("Bestand wird geprüft …"))
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
                tr(
                    "`ollama list` fehlgeschlagen: {}: {}\n"
                    "Ollama-Service evtl. nicht aktiv."
                ).format(type(exc).__name__, exc)
            )
            return

        if self._cancelled.is_set():
            return

        if _has_model_tag(list_result.stdout, self._model_tag):
            log.info("Gemma %s bereits installiert -> skip pull", self._model_tag)
            self.status.emit(tr("bereits installiert"))
            self.finished.emit()
            return

        self.status.emit(tr(prog.STARTING))
        log.info("Starting ollama pull %s", self._model_tag)
        try:
            pulled = self._download.run(self.progress.emit)
        except Exception as exc:
            if self._cancelled.is_set():
                log.info("GemmaPullWorker cancelled während pull (%s)", type(exc).__name__)
                return
            log.exception("ollama pull %s fehlgeschlagen", self._model_tag)
            detail = str(exc) if isinstance(exc, ollama_pull.PullFailed) else f"{type(exc).__name__}: {exc}"
            self.error.emit(
                ollama_pull.missing_text(self._model_tag, exc)
                or tr("`ollama pull {}` fehlgeschlagen: {}").format(self._model_tag, detail)
            )
            return

        if not pulled or self._cancelled.is_set():
            log.info("GemmaPullWorker cancelled während pull")
            return

        log.info("Gemma %s installiert", self._model_tag)
        self.status.emit(tr("bereit"))
        self.finished.emit()


class WelcomePage(QWizardPage):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("Willkommen bei Speech2Anywhere"))
        self.setSubTitle(
            tr("Diktieren mit Politur, gleich startklar.")
        )

        layout = QVBoxLayout(self)

        intro = QLabel(
            tr(
                "Speech2Anywhere misst zuerst deinen Rechner und lädt dann die passenden Modelle:\n\n"
                "  - mit Grafikkarte: Whisper large-v3 (~3 GB) und gemma4:12b (~8 GB)\n"
                "  - mit kleinerer Grafikkarte: Whisper large-v3 (~3 GB) und gemma4:e4b (~10 GB)\n"
                "  - mit Prozessor: Whisper small (~0,5 GB) und gemma4:e4b (~10 GB)\n\n"
                "Zusammen sind das rund 10 bis 13 GB.\n"
                "Für das einmalige Einrichten ist das Internet erforderlich.\n\n"
                "Klicke auf »Weiter«, um fortzufahren."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addStretch(1)


@dataclass(frozen=True)
class SetupChoice:
    device: str
    fast_mode: bool

    def whisper_repo(self) -> str:
        return hardware.CPU_WHISPER_REPO if self.device == "cpu" else DEFAULT_WHISPER_REPO

    def whisper_target(self, gpu_target: Path) -> Path:
        return hardware.cpu_whisper_dir() if self.device == "cpu" else gpu_target

    def polish_model(self) -> str:
        return hardware.FAST_MODEL if self.device == "cpu" or self.fast_mode else DEFAULT_GEMMA_TAG


class _MeasureWorker(QThread):
    measured = pyqtSignal(object)

    def __init__(self, measure, parent=None) -> None:
        super().__init__(parent)
        self._measure = measure

    def run(self) -> None:
        try:
            result = self._measure()
        except Exception:
            log.exception("Messung des Rechners fehlgeschlagen")
            result = hardware.Measurement(None, 0, 0, os.cpu_count() or 1, 0.0)
        self.measured.emit(result)


class HardwarePage(QWizardPage):
    MIN_SHOW_S = 2.0

    def __init__(self, measure=None, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("Dein Rechner"))
        self.setSubTitle(tr("Speech2Anywhere misst deinen Rechner und empfiehlt Prozessor oder Grafikkarte."))
        self._measure = measure or hardware.measure
        self._worker: _MeasureWorker | None = None
        self._measured: hardware.Measurement | None = None
        self._recommendation: hardware.Recommendation | None = None
        self._fixed: SetupChoice | None = None
        self._began = 0.0

        layout = QVBoxLayout(self)
        hint = QLabel(
            tr(
                "Schließe für die Messung bitte Programme, die Prozessor oder Grafikkarte stark beanspruchen, "
                "etwa Spiele oder Videoschnitt.\n"
                "So passt die Empfehlung zu deinem Rechner."
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self._start = QPushButton(tr("Messung starten"))
        self._start.setObjectName("comicPrimary")
        self._start.clicked.connect(self.start_measuring)
        row.addWidget(self._start)
        row.addStretch(1)
        layout.addLayout(row)
        self._animation = MeasureAnimation(self)
        layout.addWidget(self._animation)
        self._result = QLabel("")
        self._result.setWordWrap(True)
        layout.addWidget(self._result)
        self._gpu = QRadioButton(tr("Grafikkarte (GPU)"))
        self._cpu = QRadioButton(tr("Prozessor (CPU)"))
        choices = QHBoxLayout()
        choices.setSpacing(24)
        for button in (self._gpu, self._cpu):
            button.setVisible(False)
            choices.addWidget(button)
        choices.addStretch(1)
        layout.addLayout(choices)
        layout.addStretch(1)

    def isComplete(self) -> bool:  # noqa: N802 - Qt API
        return self._measured is not None

    def start_measuring(self) -> None:
        self._start.setEnabled(False)
        self._measured = None
        self._fixed = None
        self.completeChanged.emit()
        self._result.setText("")
        for button in (self._gpu, self._cpu):
            button.setVisible(False)
        self._animation.start()
        self._began = time.monotonic()
        self._worker = _MeasureWorker(self._measure, self)
        self._worker.measured.connect(self._finish)
        self._worker.start()

    def _finish(self, measured: hardware.Measurement) -> None:
        wait_ms = round(max(0.0, self.MIN_SHOW_S - (time.monotonic() - self._began)) * 1000)
        QTimer.singleShot(wait_ms, lambda: self._show(measured))

    def _show(self, measured: hardware.Measurement) -> None:
        self._animation.stop()
        self._measured = measured
        recommendation = hardware.recommend(measured)
        self._recommendation = recommendation
        if measured.gpu_name is not None:
            card = tr("Grafikkarte: {}, {} GB, davon frei {} GB").format(
                measured.gpu_name, hardware._gb(measured.vram_total_mib), hardware._gb(measured.vram_free_mib)
            )
        else:
            card = tr("Grafikkarte: keine NVIDIA-Karte gefunden")
        if measured.ram_total_gb > 0:
            machine = tr("Prozessor: {} logische Kerne, Arbeitsspeicher: {} GB").format(
                measured.cpu_threads, f"{measured.ram_total_gb:.0f}"
            )
        else:
            machine = tr("Prozessor: {} logische Kerne").format(measured.cpu_threads)
        advice = tr("Empfehlung: Grafikkarte") if recommendation.device == "gpu" else tr("Empfehlung: Prozessor")
        lines = [card, machine, advice, recommendation.reason]
        self._result.setText("\n".join(lines))
        self._gpu.setEnabled(measured.gpu_name is not None)
        self._gpu.setChecked(recommendation.device == "gpu")
        self._cpu.setChecked(recommendation.device == "cpu")
        for button in (self._gpu, self._cpu):
            button.setVisible(True)
        self._start.setText(tr("Erneut messen"))
        self._start.setEnabled(True)
        self.completeChanged.emit()

    def validatePage(self) -> bool:  # noqa: N802 - Qt API
        self._fixed = self._current_choice()
        return True

    def stop_measuring(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(15000)

    def choice(self) -> SetupChoice:
        return self._fixed or self._current_choice()

    def _current_choice(self) -> SetupChoice:
        if self._recommendation is None:
            return SetupChoice("gpu", False)
        if not self._gpu.isChecked():
            return SetupChoice("cpu", False)
        return SetupChoice("gpu", self._recommendation.fast_mode or self._recommendation.device == "cpu")


def apply_setup_choice(cfg, choice: SetupChoice, path: Path | None = None, gpu_target: Path | None = None) -> bool:
    from kira.config import default_config_path
    from kira.config_writer import update_scalars
    from kira.ui.settings_dialog import _MINIMAL_CONFIG
    target = path or default_config_path()
    updates = {"whisper.device": choice.device, "styler.fast_mode": choice.fast_mode}
    if choice.device == "cpu":
        updates["whisper.cpu_model"] = hardware.cpu_whisper_dir().as_posix()
    else:
        updates["styler.model"] = DEFAULT_GEMMA_TAG
        if gpu_target is not None:
            updates["whisper.model"] = Path(gpu_target).as_posix()
    for key, value in updates.items():
        section, name = key.split(".")
        setattr(getattr(cfg, section), name, value)
    log.info("Einrichtung: rechnet auf %s, schnelles Modell %s", choice.device, choice.fast_mode)
    try:
        current = target.read_text(encoding="utf-8") if target.exists() else _MINIMAL_CONFIG
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(update_scalars(current, updates), encoding="utf-8")
    except Exception:
        log.exception("Wahl der Einrichtung nicht gespeichert")
        return False
    return True


class DownloadPage(QWizardPage):
    def __init__(self, whisper_target: Path, ollama_installer: Path, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("Modelle werden installiert"))
        self.setSubTitle(tr("Bitte warten. Nach einem Abbruch lädt der nächste Start nur, was noch fehlt."))
        self.setCommitPage(True)

        self._whisper_target = whisper_target
        self._ollama_installer = ollama_installer

        self._whisper_done = False
        self._ollama_done = False
        self._gemma_done = False
        self._gemma_bytes = False
        self._gemma_phase = ""
        self._failed: set[str] = set()

        self._abort_lock = threading.Lock()
        self._pipeline_aborted = False

        self._whisper_worker: WhisperDownloadWorker | None = None
        self._ollama_worker: OllamaSetupWorker | None = None
        self._gemma_worker: GemmaPullWorker | None = None

        outer = QVBoxLayout(self)

        self._whisper_status = QLabel()
        self._whisper_bar = QProgressBar()
        outer.addWidget(self._whisper_status)
        outer.addWidget(self._whisper_bar)
        self._whisper_view = ProgressView(self._whisper_bar, self._whisper_status.setText, "Whisper: ", parent=self)
        self._whisper_view.idle(tr("wartet …"))

        self._ollama_status = QLabel()
        self._ollama_bar = QProgressBar()
        outer.addWidget(self._ollama_status)
        outer.addWidget(self._ollama_bar)
        self._ollama_view = ProgressView(self._ollama_bar, self._ollama_status.setText, "Ollama: ", parent=self)
        self._ollama_view.idle(tr("wartet …"))

        self._gemma_status = QLabel()
        self._gemma_bar = QProgressBar()
        outer.addWidget(self._gemma_status)
        outer.addWidget(self._gemma_bar)
        self._gemma_view = ProgressView(self._gemma_bar, self._gemma_status.setText, "Gemma: ", parent=self)
        self._gemma_view.idle(tr("wartet auf Ollama …"))

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

    def _choice(self) -> SetupChoice:
        getter = getattr(self.wizard(), "choice", None)
        return getter() if callable(getter) else SetupChoice("gpu", False)

    def initializePage(self) -> None:
        with self._abort_lock:
            self._pipeline_aborted = False
        self._whisper_done = self._ollama_done = self._gemma_done = False
        self._gemma_bytes = False
        self._gemma_phase = ""
        self._failed.clear()
        self._append_log(tr("Starte Downloads..."))
        self._whisper_view.busy(prog.STARTING)
        self._ollama_view.busy(prog.STARTING)
        self._gemma_view.idle(tr("wartet auf Ollama …"))

        choice = self._choice()
        self._whisper_worker = WhisperDownloadWorker(
            target_dir=choice.whisper_target(self._whisper_target),
            repo_id=choice.whisper_repo(),
        )
        self._whisper_worker.status.connect(self._on_whisper_status)
        self._whisper_worker.progress.connect(self._on_whisper_progress)
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
        self._append_log(f"[Whisper] {msg}")

    def _on_whisper_progress(self, done: int, total: int) -> None:
        if not self._pipeline_aborted:
            self._whisper_view.amount(done, total)

    def _on_whisper_finished(self, path: Path) -> None:
        self._whisper_view.finish(tr("fertig ({})").format(path.name))
        self._whisper_done = True
        self._append_log(f"[Whisper] OK -> {path}")
        self.completeChanged.emit()

    def _on_whisper_error(self, msg: str) -> None:
        self._failed.add("whisper")
        self._whisper_view.idle(tr("FEHLER"))
        self._append_log(tr("[Whisper FEHLER] {}").format(msg), error=True)
        self._abort_pipeline()

    def _on_ollama_status(self, msg: str) -> None:
        if not self._pipeline_aborted:
            self._ollama_view.busy(msg)
        self._append_log(f"[Ollama] {msg}")

    def _on_ollama_finished(self) -> None:
        self._ollama_view.finish(tr("fertig"))
        self._ollama_done = True
        self._append_log("[Ollama] OK")
        self.completeChanged.emit()
        self._start_gemma()

    def _on_ollama_error(self, msg: str) -> None:
        self._failed.add("ollama")
        self._ollama_view.idle(tr("FEHLER"))
        self._append_log(tr("[Ollama FEHLER] {}").format(msg), error=True)
        self._abort_pipeline()

    def _start_gemma(self) -> None:
        if self._pipeline_aborted:
            log.info("Gemma-Start übersprungen, Einrichtung abgebrochen")
            self._gemma_view.idle(tr("abgebrochen"))
            self._append_log(tr("[Gemma] Pipeline abgebrochen, kein Pull"))
            return
        self._gemma_view.busy(prog.STARTING)
        ollama_exe = find_ollama_exe()
        self._gemma_worker = GemmaPullWorker(
            model_tag=self._choice().polish_model(),
            ollama_exe=ollama_exe,
        )
        self._gemma_worker.status.connect(self._on_gemma_status)
        self._gemma_worker.progress.connect(self._on_gemma_progress)
        self._gemma_worker.error.connect(self._on_gemma_error)
        self._gemma_worker.finished.connect(self._on_gemma_finished)
        self._gemma_worker.start()

    def _on_gemma_status(self, msg: str) -> None:
        if self._pipeline_aborted:
            return
        self._gemma_phase = msg
        self._gemma_view.busy(msg)
        self._append_log(f"[Gemma] {msg}")

    def _on_gemma_progress(self, status: str, done: int, total: int) -> None:
        if self._pipeline_aborted:
            return
        if total > 0 and not prog.final_status(status):
            self._gemma_bytes = True
            self._gemma_view.amount(done, total)
            return
        phase = prog.pull_phase(status, self._gemma_bytes)
        self._gemma_view.busy(phase)
        if phase != self._gemma_phase:
            self._gemma_phase = phase
            self._append_log(f"[Gemma] {phase}")

    def _on_gemma_finished(self) -> None:
        self._gemma_view.finish(tr("fertig"))
        self._gemma_done = True
        self._append_log("[Gemma] OK")
        self.completeChanged.emit()

    def _on_gemma_error(self, msg: str) -> None:
        self._failed.add("gemma")
        self._gemma_view.idle(tr("FEHLER"))
        self._append_log(tr("[Gemma FEHLER] {}").format(msg), error=True)
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
        self._append_log(tr("[Pipeline] abgebrochen, laufende Worker werden gestoppt"), error=True)
        self._stop_all_workers()
        self._mark_aborted()

    def _mark_aborted(self) -> None:
        for name, view, done in (
            ("whisper", self._whisper_view, self._whisper_done),
            ("ollama", self._ollama_view, self._ollama_done),
            ("gemma", self._gemma_view, self._gemma_done),
        ):
            if not done and name not in self._failed:
                view.idle(tr("abgebrochen"))

    def cleanupPage(self) -> None:
        self._pipeline_aborted = True
        self._stop_all_workers()
        self._mark_aborted()

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
        self.setTitle(tr("Setup abgeschlossen"))
        self.setSubTitle(tr("Speech2Anywhere ist bereit."))

        layout = QVBoxLayout(self)
        hints = QLabel(
            tr(
                "So funktioniert's:\n\n"
                "  - F8 gedrückt halten -> sprechen -> loslassen.\n"
                "    Dein Text erscheint am Cursor.\n\n"
                "  - F9 markieren + halten -> Sprach-Befehl auf den\n"
                "    markierten Text (z.B. 'mach den Text formeller').\n\n"
                "  - Tray-Icon (rechts unten) -> Einstellungen,\n"
                "    Anleitung, Updates.\n\n"
                "Klicke auf »Fertigstellen«, um Speech2Anywhere zu starten."
            )
        )
        hints.setWordWrap(True)
        layout.addWidget(hints)
        layout.addStretch(1)


_WIZARD_SIZE = QSize(720, 540)


class _CreditHolder(QPushButton):
    def __init__(self) -> None:
        super().__init__()
        self.setFlat(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0; margin: 0; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(comic.credit_row())

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.layout().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


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
        self._hardware = HardwarePage(parent=self)
        self.addPage(self._hardware)
        self.addPage(DownloadPage(whisper_target, ollama_installer, self))
        self.addPage(FinishedPage(self))
        self._add_credit()
        self._comic_look()

    def _comic_look(self) -> None:
        for button, text in (
            (QWizard.WizardButton.NextButton, tr("Weiter")),
            (QWizard.WizardButton.BackButton, tr("Zurück")),
            (QWizard.WizardButton.CancelButton, tr("Abbrechen")),
            (QWizard.WizardButton.FinishButton, tr("Fertigstellen")),
            (QWizard.WizardButton.CommitButton, tr("Weiter")),
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

    def choice(self) -> SetupChoice:
        return self._hardware.choice()

    def _add_credit(self) -> None:
        holder = _CreditHolder()
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        self.setButton(QWizard.WizardButton.CustomButton1, holder)
        self.setButtonLayout([
            QWizard.WizardButton.CustomButton1, QWizard.WizardButton.Stretch, QWizard.WizardButton.BackButton,
            QWizard.WizardButton.NextButton, QWizard.WizardButton.CommitButton, QWizard.WizardButton.FinishButton,
            QWizard.WizardButton.CancelButton,
        ])

    def _cleanup_running_workers(self) -> None:
        for page_id in self.pageIds():
            page = self.page(page_id)
            if isinstance(page, DownloadPage):
                page.cleanupPage()
            elif isinstance(page, HardwarePage):
                page.stop_measuring()

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
                tr("Setup-Marker nicht gespeichert"),
                tr(
                    "Speech2Anywhere konnte den Setup-Marker nicht schreiben.\n"
                    "\n"
                    "Beim nächsten Start kann der Assistent erneut erscheinen (die Modelle sind schon da, es wird "
                    "nichts neu geladen).\n"
                    "\n"
                    "Pfad: %APPDATA%\\Kira\\\n"
                    "Fehler: {}: {}"
                ).format(type(exc).__name__, exc)
            )
        super().accept()
