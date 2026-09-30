from __future__ import annotations
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMessageBox, QProgressDialog, QWidget,
)

from kira import __version__, UPDATE_REPO
from kira.ui._dialog_style import (
    apply_light_theme,
    light_critical,
    light_information,
    light_warning,
)
from kira.updater import (
    UpdateCheckResult,
    check_for_update,
    download_asset,
    download_bundle,
    verify_sha256sums,
)

log = logging.getLogger(__name__)


def _bundle_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Kira" / "update"
    return base


class _Cancelled(Exception):
    pass


class _UpdateWorker(QObject):
    progress = pyqtSignal(str, int, int)
    phase = pyqtSignal(str)
    succeeded = pyqtSignal(str, bool)
    failed = pyqtSignal(str)

    def __init__(self, result: UpdateCheckResult, target_dir: Path) -> None:
        super().__init__()
        self._result = result
        self._target_dir = target_dir
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _on_bytes(self, name: str, done: int, total: int) -> None:
        if self._cancelled:
            raise _Cancelled()
        self.progress.emit(name, done, total)

    def run(self) -> None:
        try:
            r = self._result
            if not r.bundle_assets:
                self.failed.emit(
                    "Update-Bundle leer - Release hat keine Setup-Files."
                )
                return
            self.phase.emit(
                f"Lade {len(r.bundle_assets)} Bundle-Dateien..."
            )
            try:
                paths = download_bundle(
                    r.bundle_assets,
                    self._target_dir,
                    on_progress=self._on_bytes,
                )
            except _Cancelled:
                log.info("Update-Download abgebrochen")
                self.failed.emit("Abgebrochen.")
                return
            except Exception as exc:
                if self._cancelled:
                    log.info("Update-Download abgebrochen (%s)", exc)
                    self.failed.emit("Abgebrochen.")
                    return
                log.exception("download_bundle failed")
                self.failed.emit(f"Download fehlgeschlagen: {exc}")
                return

            if self._cancelled:
                self.failed.emit("Abgebrochen.")
                return

            hash_verified = False
            if r.sha256sums_url:
                self.phase.emit("Verifiziere SHA256-Hashes...")
                sums_path = self._target_dir / "SHA256SUMS.txt"
                try:
                    download_asset(r.sha256sums_url, sums_path)
                except Exception as exc:
                    if self._cancelled:
                        self.failed.emit("Abgebrochen.")
                        return
                    log.exception("SHA256SUMS download failed")
                    self.failed.emit(
                        f"SHA256SUMS konnte nicht geladen werden: {exc}"
                    )
                    return
                ok, errors = verify_sha256sums(sums_path, self._target_dir)
                if self._cancelled:
                    self.failed.emit("Abgebrochen.")
                    return
                if not ok:
                    log.warning("SHA256 mismatch: %s", errors)
                    self.failed.emit(
                        "Hash-Verifikation fehlgeschlagen:\n\n"
                        + "\n".join(errors[:5])
                        + "\n\nDie heruntergeladenen Dateien werden NICHT gestartet."
                    )
                    return
                hash_verified = True
                log.info("SHA256SUMS verified for %d files", len(paths))
            else:
                log.warning(
                    "no SHA256SUMS in release - installing without hash check"
                )

            stub_name = r.bundle_assets[0].name
            self.succeeded.emit(str(self._target_dir / stub_name), hash_verified)
        except Exception as exc:
            log.exception("update worker crashed")
            self.failed.emit(f"Unerwarteter Fehler: {exc}")


def _launch_setup_detached(setup_path: str) -> None:
    DETACHED = 0x00000008 | 0x00000200
    subprocess.Popen(  # noqa: S603 - list-args, kein shell-Parsing
        [setup_path],
        creationflags=DETACHED,
        close_fds=True,
    )


_flow_active = False
_anchor: tuple | None = None


def flow_active() -> bool:
    return _flow_active


def run_update_flow(
    parent: QWidget | None,
    on_quit_request: Callable[[], None] | None = None,
) -> None:
    global _flow_active
    if _flow_active:
        log.info("Update-Flow läuft bereits, zweiter Start ignoriert")
        light_information(parent, "Speech2Anywhere", "Ein Update läuft bereits.")
        return
    _flow_active = True
    handed_over = False
    try:
        handed_over = _run_update_flow(parent, on_quit_request)
    finally:
        if not handed_over:
            _flow_active = False


def _flow_finished() -> None:
    global _flow_active, _anchor
    _flow_active = False
    _anchor = None


def _run_update_flow(
    parent: QWidget | None,
    on_quit_request: Callable[[], None] | None,
) -> bool:
    global _anchor
    log.info("Update-Flow gestartet, lokale Version=%s", __version__)

    busy = QProgressDialog(
        "Suche nach Updates...", "Abbrechen", 0, 0, parent,
    )
    busy.setWindowTitle("Speech2Anywhere: Update-Suche")
    busy.setWindowModality(Qt.WindowModality.ApplicationModal)
    busy.setMinimumDuration(0)
    apply_light_theme(busy)
    busy.show()
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    result = check_for_update(local_version=__version__, repo=UPDATE_REPO)
    busy.close()

    if result.status == "failed":
        light_critical(
            parent, "Speech2Anywhere",
            f"Update-Suche fehlgeschlagen.\n\n{result.error or 'Unbekannter Fehler'}",
        )
        return False
    if result.status == "current":
        light_information(
            parent, "Speech2Anywhere",
            f"Speech2Anywhere ist aktuell (v{__version__}).",
        )
        return False
    if result.status == "local_newer":
        light_information(
            parent, "Speech2Anywhere",
            f"Du nutzt schon eine neuere Version (hier v{__version__}, "
            f"veröffentlicht v{result.remote_version}). Wahrscheinlich eine Entwicklerfassung.",
        )
        return False
    if result.status == "no_asset":
        light_warning(
            parent, "Speech2Anywhere",
            f"Release v{result.remote_version} gefunden, aber kein "
            "Installationspaket dabei. Probier es bitte später noch einmal.",
        )
        return False

    bundle_count = len(result.bundle_assets)
    total_size_mb = sum(a.size for a in result.bundle_assets) / (1024 * 1024)
    msg = QMessageBox(parent)
    msg.setWindowTitle("Speech2Anywhere: Update verfügbar")
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText(
        f"Version v{result.remote_version} ist verfügbar.\n\n"
        f"Du nutzt v{__version__}."
    )
    msg.setInformativeText(
        f"Bundle: {bundle_count} Dateien (~{total_size_mb:.0f} MB).\n"
        f"Quelle: github.com/{UPDATE_REPO}\n\n"
        "Jetzt herunterladen und installieren?"
    )
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.Yes)
    apply_light_theme(msg)
    answer = msg.exec()
    if answer != QMessageBox.StandardButton.Yes:
        return False

    target = _bundle_dir() / f"v{result.remote_version}"
    progress = QProgressDialog(
        "Lade Update-Bundle...", "Abbrechen", 0, 100, parent,
    )
    progress.setWindowTitle(f"Speech2Anywhere: Update v{result.remote_version}")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setAutoClose(False)
    progress.setMinimumDuration(0)
    apply_light_theme(progress)
    progress.show()

    thread = QThread()
    worker = _UpdateWorker(result, target)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    state = {"current_asset": ""}

    def on_phase(label: str) -> None:
        progress.setLabelText(label)

    def on_progress(name: str, done: int, total: int) -> None:
        if name != state["current_asset"]:
            state["current_asset"] = name
        done_mb = done / (1024 * 1024)
        if total > 0:
            pct = int((done / total) * 100)
            progress.setValue(min(pct, 99))
        progress.setLabelText(
            f"Lade {name}\n{done_mb:.1f} MB"
            + (f" / {total / (1024 * 1024):.1f} MB" if total > 0 else "")
        )

    def on_succeeded(setup_path: str, hash_verified: bool) -> None:
        try:
            _on_succeeded(setup_path, hash_verified)
        finally:
            _flow_finished()

    def _on_succeeded(setup_path: str, hash_verified: bool) -> None:
        progress.setValue(100)
        progress.close()
        thread.quit()
        thread.wait()
        if worker._cancelled:
            light_critical(parent, "Speech2Anywhere", "Abgebrochen.")
            return

        verify_msg = (
            "SHA256-Verifikation: bestanden.\n"
            if hash_verified
            else "Achtung: Release hatte keine SHA256SUMS-Datei. Hash-"
            "Verifikation übersprungen - du lädst auf eigene Verantwortung.\n"
        )
        confirm = QMessageBox(parent)
        confirm.setWindowTitle("Speech2Anywhere: Update bereit")
        confirm.setIcon(QMessageBox.Icon.Information)
        confirm.setText("Update-Bundle wurde geladen.")
        confirm.setInformativeText(
            verify_msg
            + f"\nSetup: {setup_path}\n\n"
            "Jetzt Setup starten? Speech2Anywhere wird beendet damit Setup das "
            "Programmverzeichnis aktualisieren kann."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Yes)
        apply_light_theme(confirm)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            _launch_setup_detached(setup_path)
            log.info("Setup gestartet: %s", setup_path)
        except Exception as exc:
            log.exception("Setup-Launch failed")
            light_critical(
                parent, "Speech2Anywhere",
                f"Setup konnte nicht gestartet werden: {exc}\n\n"
                f"Manuell ausfuehren: {setup_path}",
            )
            return

        if on_quit_request is not None:
            log.info("Speech2Anywhere wird für die Setup-Installation beendet")
            on_quit_request()
        else:
            light_information(
                parent, "Speech2Anywhere",
                "Setup läuft. Bitte beende Speech2Anywhere über das Tray-Icon "
                "(rechtsklick -> Quit Speech2Anywhere), damit Setup die Aktualisierung "
                "abschließen kann.",
            )

    def on_failed(message: str) -> None:
        try:
            progress.close()
            thread.quit()
            thread.wait()
            light_critical(parent, "Speech2Anywhere", message)
        finally:
            _flow_finished()

    worker.phase.connect(on_phase)
    worker.progress.connect(on_progress)
    worker.succeeded.connect(on_succeeded)
    worker.failed.connect(on_failed)
    progress.canceled.connect(lambda: worker.cancel())
    thread.start()

    _anchor = (thread, worker, progress)
    return True
