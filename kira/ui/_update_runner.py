from __future__ import annotations
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMessageBox, QProgressDialog, QWidget,
)

from kira import __version__, UPDATE_REPO, app_update, progress as prog
from kira.ui._dialog_style import (
    apply_light_theme,
    light_critical,
    light_information,
    light_warning,
)
from kira.ui._progress_view import ProgressView
from kira.updater import (
    UpdateCheckResult,
    check_for_update,
    download_asset,
    download_bundle,
    verify_sha256sums,
)
from kira.texte import N_, tr

log = logging.getLogger(__name__)

CHECKING = N_("Prüfsummen werden geprüft …")


def _bundle_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Kira" / "update"
    return base


class _Cancelled(Exception):
    pass


class _UpdateWorker(QObject):
    progress = pyqtSignal('qint64', 'qint64')
    phase = pyqtSignal(str)
    succeeded = pyqtSignal(str, bool)
    failed = pyqtSignal(str)

    def __init__(self, result: UpdateCheckResult, target_dir: Path) -> None:
        super().__init__()
        self._result = result
        self._target_dir = target_dir
        self._cancelled = False
        self._done: dict[str, int] = {}
        self._sizes = {a.name: a.size for a in result.bundle_assets if a.size > 0}
        self._throttle = prog.Throttle()

    def cancel(self) -> None:
        self._cancelled = True

    def _on_bytes(self, name: str, done: int, total: int) -> None:
        if self._cancelled:
            raise _Cancelled()
        self._done[name] = done
        if total > 0:
            self._sizes[name] = max(self._sizes.get(name, 0), total)
        all_done, all_total = sum(self._done.values()), sum(self._sizes.values())
        if self._throttle.due(force=0 < all_total <= all_done):
            self.progress.emit(all_done, all_total)

    def run(self) -> None:
        try:
            r = self._result
            if not r.bundle_assets:
                self.failed.emit(
                    tr("Update-Bundle leer - Release hat keine Setup-Files.")
                )
                return
            self.phase.emit(tr(prog.STARTING))
            try:
                paths = download_bundle(
                    r.bundle_assets,
                    self._target_dir,
                    on_progress=self._on_bytes,
                )
            except _Cancelled:
                log.info("Update-Download abgebrochen")
                self.failed.emit(tr("Abgebrochen."))
                return
            except Exception as exc:
                if self._cancelled:
                    log.info("Update-Download abgebrochen (%s)", exc)
                    self.failed.emit(tr("Abgebrochen."))
                    return
                log.exception("download_bundle failed")
                self.failed.emit(tr("Download fehlgeschlagen: {}").format(exc))
                return

            if self._cancelled:
                self.failed.emit(tr("Abgebrochen."))
                return

            hash_verified = False
            if r.sha256sums_url:
                self.phase.emit(CHECKING)
                sums_path = self._target_dir / "SHA256SUMS.txt"
                try:
                    download_asset(r.sha256sums_url, sums_path)
                except Exception as exc:
                    if self._cancelled:
                        self.failed.emit(tr("Abgebrochen."))
                        return
                    log.exception("SHA256SUMS download failed")
                    self.failed.emit(
                        tr("SHA256SUMS konnte nicht geladen werden: {}").format(exc)
                    )
                    return
                ok, errors = verify_sha256sums(sums_path, self._target_dir)
                if self._cancelled:
                    self.failed.emit(tr("Abgebrochen."))
                    return
                if not ok:
                    log.warning("SHA256 mismatch: %s", errors)
                    self.failed.emit(
                        tr("Hash-Verifikation fehlgeschlagen:\n\n")
                        + "\n".join(errors[:5])
                        + tr("\n\nDie heruntergeladenen Dateien werden NICHT gestartet.")
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
            self.failed.emit(tr("Unerwarteter Fehler: {}").format(exc))


def _offer_patch(
    parent: QWidget | None,
    result: UpdateCheckResult,
    on_quit_request: Callable[[], None] | None,
) -> tuple[bool | None, str]:
    root = app_update.install_root()
    if root is None or result.app_asset is None:
        return None, ""
    busy = QProgressDialog(tr("Prüfe, ob ein kleines Programm-Update reicht..."), tr("Abbrechen"), 0, 0, parent)
    busy.setWindowTitle("Speech2Anywhere: Update")
    busy.setWindowModality(Qt.WindowModality.ApplicationModal)
    busy.setMinimumDuration(0)
    apply_light_theme(busy)
    busy.show()
    box: dict[str, app_update.PatchCheck] = {}
    asset, target = result.app_asset, _bundle_dir() / f"v{result.remote_version}"

    def work() -> None:
        try:
            box["check"] = app_update.check_patch(asset, target, root=root)
        except Exception as exc:
            log.exception("Prüfung des Programm-Updates fehlgeschlagen")
            box["check"] = app_update.PatchCheck(None, [tr("Die Prüfung ist fehlgeschlagen ({}).").format(exc)])

    from PyQt6.QtCore import QCoreApplication, QEventLoop
    checker = threading.Thread(target=work, daemon=True, name="kira-patch-check")
    checker.start()
    while checker.is_alive() and not busy.wasCanceled():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        checker.join(0.02)
    cancelled = busy.wasCanceled()
    busy.close()
    if cancelled:
        log.info("Prüfung des Programm-Updates abgebrochen")
        return False, ""
    check = box["check"]
    if not check.ready:
        log.info("Programm-Update reicht nicht: %s", "; ".join(check.reasons))
        first = check.reasons[0] if check.reasons else tr("unbekannter Grund")
        return None, tr("Ein kleines Programm-Update reicht diesmal nicht: {}").format(first)

    package_size = prog.total_text(result.app_asset.size)
    msg = QMessageBox(parent)
    msg.setWindowTitle(tr("Speech2Anywhere: Update verfügbar"))
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText(
        tr(
            "Version v{} ist verfügbar.\n"
            "\n"
            "Du nutzt v{}."
        ).format(result.remote_version, __version__)
    )
    msg.setInformativeText(
        tr(
            "Programm-Update: {} statt des ganzen Pakets. Bibliotheken und Modelle bleiben, wie sie sind.\n"
            "Quelle: github.com/{}, Prüfsumme bestanden.\n"
            "\n"
            "Speech2Anywhere beendet sich dafür kurz und startet von selbst neu. Jetzt aktualisieren?"
        ).format(package_size, UPDATE_REPO)
    )
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.Yes)
    apply_light_theme(msg)
    if msg.exec() != QMessageBox.StandardButton.Yes:
        return False, ""
    try:
        app_update.launch_patch(check.wheel, result.remote_version, sha256=asset.sha256, root=root)
    except Exception as exc:
        log.exception("Programm-Update ließ sich nicht starten")
        light_critical(parent, "Speech2Anywhere", tr("Das Programm-Update ließ sich nicht starten: {}").format(exc))
        return False, ""
    if on_quit_request is not None:
        log.info("Speech2Anywhere wird für das Programm-Update beendet")
        on_quit_request()
    else:
        light_information(
            parent, "Speech2Anywhere",
            tr(
                "Beende Speech2Anywhere über das Tray-Symbol. Danach wird das Update eingespielt, "
                "und Speech2Anywhere startet von selbst neu."
            ),
        )
    return True, ""


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
        light_information(parent, "Speech2Anywhere", tr("Ein Update läuft bereits."))
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
        tr("Suche nach Updates..."), tr("Abbrechen"), 0, 0, parent,
    )
    busy.setWindowTitle(tr("Speech2Anywhere: Update-Suche"))
    busy.setWindowModality(Qt.WindowModality.ApplicationModal)
    busy.setMinimumDuration(0)
    apply_light_theme(busy)
    busy.show()
    box: dict[str, UpdateCheckResult] = {}

    def search() -> None:
        try:
            box["result"] = check_for_update(local_version=__version__, repo=UPDATE_REPO)
        except Exception as exc:
            log.exception("Update-Suche fehlgeschlagen")
            box["result"] = UpdateCheckResult(status="failed", error=str(exc))

    from PyQt6.QtCore import QCoreApplication, QEventLoop
    searcher = threading.Thread(target=search, daemon=True, name="kira-update-search")
    searcher.start()
    while searcher.is_alive() and not busy.wasCanceled():
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        searcher.join(0.02)
    cancelled = busy.wasCanceled()
    busy.close()
    if cancelled:
        log.info("Update-Suche abgebrochen")
        return False
    result = box["result"]

    if result.status == "failed":
        light_critical(
            parent, "Speech2Anywhere",
            tr(
                "Update-Suche fehlgeschlagen.\n"
                "\n"
                "{}"
            ).format(result.error or tr('Unbekannter Fehler')),
        )
        return False
    if result.status == "current":
        light_information(
            parent, "Speech2Anywhere",
            tr("Speech2Anywhere ist aktuell (v{}).").format(__version__),
        )
        return False
    if result.status == "local_newer":
        light_information(
            parent, "Speech2Anywhere",
            tr(
                "Du nutzt schon eine neuere Version (hier v{}, veröffentlicht v{}). Wahrscheinlich eine "
                "Entwicklerfassung."
            ).format(__version__, result.remote_version),
        )
        return False
    if result.status == "no_asset":
        light_warning(
            parent, "Speech2Anywhere",
            tr("Release v{} gefunden, aber kein Installationspaket dabei. Probier es bitte später noch einmal.").format(result.remote_version),
        )
        return False

    handed_over, patch_note = _offer_patch(parent, result, on_quit_request)
    if handed_over is not None:
        return handed_over

    bundle_count = len(result.bundle_assets)
    bundle_size = prog.total_text(sum(a.size for a in result.bundle_assets))
    msg = QMessageBox(parent)
    msg.setWindowTitle(tr("Speech2Anywhere: Update verfügbar"))
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText(
        tr(
            "Version v{} ist verfügbar.\n"
            "\n"
            "Du nutzt v{}."
        ).format(result.remote_version, __version__)
    )
    msg.setInformativeText(
        (f"{patch_note}\n\n" if patch_note else "")
        + tr(
            "Bundle: {} Dateien (~{}).\n"
            "Quelle: github.com/{}\n"
            "\n"
            "Jetzt herunterladen und installieren?"
        ).format(bundle_count, bundle_size, UPDATE_REPO)
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
    head = tr("Lade Update v{}\n").format(result.remote_version)
    progress = QProgressDialog(
        f"{head}{tr(prog.STARTING)}", tr("Abbrechen"), 0, 0, parent,
    )
    progress.setWindowTitle(f"Speech2Anywhere: Update v{result.remote_version}")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)
    apply_light_theme(progress)
    view = ProgressView(progress, progress.setLabelText, head, parent=progress)
    progress.show()

    thread = QThread()
    worker = _UpdateWorker(result, target)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    def cancel_download() -> None:
        worker.cancel()

    def close_progress() -> None:
        view.stop()
        try:
            progress.canceled.disconnect(cancel_download)
        except (TypeError, RuntimeError):
            pass
        progress.close()

    def on_succeeded(setup_path: str, hash_verified: bool) -> None:
        try:
            _on_succeeded(setup_path, hash_verified)
        finally:
            _flow_finished()

    def _on_succeeded(setup_path: str, hash_verified: bool) -> None:
        close_progress()
        thread.quit()
        thread.wait()
        if worker._cancelled:
            light_critical(parent, "Speech2Anywhere", tr("Abgebrochen."))
            return

        verify_msg = (
            tr("SHA256-Verifikation: bestanden.\n")
            if hash_verified
            else tr(
                "Achtung: Release hatte keine SHA256SUMS-Datei. Hash-"
                "Verifikation übersprungen - du lädst auf eigene Verantwortung.\n"
            )
        )
        confirm = QMessageBox(parent)
        confirm.setWindowTitle(tr("Speech2Anywhere: Update bereit"))
        confirm.setIcon(QMessageBox.Icon.Information)
        confirm.setText(tr("Update-Bundle wurde geladen."))
        confirm.setInformativeText(
            verify_msg
            + tr(
                "\n"
                "Setup: {}\n"
                "\n"
                "Jetzt Setup starten? Speech2Anywhere wird beendet damit Setup das Programmverzeichnis "
                "aktualisieren kann."
            ).format(setup_path)
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
                tr(
                    "Setup konnte nicht gestartet werden: {}\n"
                    "\n"
                    "Manuell ausführen: {}"
                ).format(exc, setup_path),
            )
            return

        if on_quit_request is not None:
            log.info("Speech2Anywhere wird für die Setup-Installation beendet")
            on_quit_request()
        else:
            light_information(
                parent, "Speech2Anywhere",
                tr(
                    "Setup läuft. Bitte beende Speech2Anywhere über das Tray-Icon "
                    "(rechtsklick -> Quit Speech2Anywhere), damit Setup die Aktualisierung "
                    "abschließen kann."
                ),
            )

    def on_failed(message: str) -> None:
        try:
            close_progress()
            thread.quit()
            thread.wait()
            light_critical(parent, "Speech2Anywhere", message)
        finally:
            _flow_finished()

    worker.phase.connect(view.busy)
    worker.progress.connect(view.amount)
    worker.succeeded.connect(on_succeeded)
    worker.failed.connect(on_failed)
    progress.canceled.connect(cancel_download)
    thread.start()

    _anchor = (thread, worker, progress)
    return True
