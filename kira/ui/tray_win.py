from __future__ import annotations
import ctypes
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable
import pystray
from PIL import Image, ImageDraw
from pystray._util import win32 as _ps_win32
from pystray._win32 import Icon as _PystrayWin32Icon, _dispatcher
from kira import LOG_NAME
from kira.app import State

log = logging.getLogger(__name__)


_KIRA_TRAY_CLASS = "KiraDigitalrootsTrayIcon"
_KIRA_TRAY_TITLE = "Speech2Anywhere"
MENU_HEADER = "Speech2Anywhere"


_WM_SETTEXT = 0x000C
_WM_GETTEXT = 0x000D
_WM_GETTEXTLENGTH = 0x000E


class _KiraPystrayIcon(_PystrayWin32Icon):
    ICON_HANDLE_LIMIT = 16

    def __init__(self, *args, **kwargs):
        self._icon_handles: dict[int, tuple[Image.Image, int]] = {}
        super().__init__(*args, **kwargs)

        def _passthrough(msg):
            def _handler(wParam, lParam):
                return _ps_win32.DefWindowProc(self._hwnd, msg, wParam, lParam)
            return _handler

        for msg in (_WM_SETTEXT, _WM_GETTEXT, _WM_GETTEXTLENGTH):
            self._message_handlers[msg] = _passthrough(msg)

    on_context_menu: Callable[[], bool] | None = None

    def _assert_icon_handle(self):
        if self._icon_handle:
            return
        image = self.icon
        cached = self._icon_handles.get(id(image))
        if cached is not None and cached[0] is image:
            self._icon_handle = cached[1]
            return
        super()._assert_icon_handle()
        if len(self._icon_handles) < self.ICON_HANDLE_LIMIT:
            self._icon_handles[id(image)] = (image, self._icon_handle)

    def _release_icon(self):
        handle = self._icon_handle
        if handle and all(handle != cached for _image, cached in self._icon_handles.values()):
            _ps_win32.DestroyIcon(handle)
        self._icon_handle = None

    def _on_notify(self, wparam, lparam):
        if lparam == _ps_win32.WM_RBUTTONUP and self.on_context_menu is not None:
            _ps_win32.SetForegroundWindow(self._hwnd)
            if self.on_context_menu():
                return
        super()._on_notify(wparam, lparam)

    def _register_class(self):
        wndclass = _ps_win32.WNDCLASSEX(
            cbSize=ctypes.sizeof(_ps_win32.WNDCLASSEX),
            style=0,
            lpfnWndProc=_dispatcher,
            cbClsExtra=0,
            cbWndExtra=0,
            hInstance=_ps_win32.GetModuleHandle(None),
            hIcon=None,
            hCursor=None,
            hbrBackground=_ps_win32.COLOR_WINDOW + 1,
            lpszMenuName=None,
            lpszClassName=_KIRA_TRAY_CLASS,
            hIconSm=None,
        )
        atom = _ps_win32.RegisterClassEx(wndclass)
        if atom == 0:
            try:
                ctypes.windll.user32.UnregisterClassW(
                    _KIRA_TRAY_CLASS, _ps_win32.GetModuleHandle(None),
                )
                atom = _ps_win32.RegisterClassEx(wndclass)
                if atom != 0:
                    log.info(
                        "Recovered stale tray window class %r from previous "
                        "Speech2Anywhere process, registration succeeded on retry",
                        _KIRA_TRAY_CLASS,
                    )
            except Exception:
                log.exception(
                    "tray window-class recovery failed (atom=%s)", atom,
                )
        return atom


def _set_tray_window_title(icon_holder: "KiraTray", timeout_s: float = 5.0) -> None:
    SetWindowTextW = ctypes.windll.user32.SetWindowTextW
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        icon = icon_holder._icon
        if icon is not None:
            hwnd = getattr(icon, "_hwnd", None)
            if hwnd:
                SetWindowTextW(hwnd, _KIRA_TRAY_TITLE)
                log.info(
                    "Tray window labelled %r (class=%s, hwnd=0x%x)",
                    _KIRA_TRAY_TITLE, _KIRA_TRAY_CLASS, hwnd,
                )
                return
        time.sleep(0.05)
    log.warning(
        "Tray window did not appear within %.1fs, title not patched",
        timeout_s,
    )

from kira._resources import assets_dir as _assets_dir  # noqa: E402
ASSETS = _assets_dir()

ICON_SIZE = 64
ICON_BG_COLOR = (255, 196, 0, 255)
ICON_BG_RADIUS = 12
ICON_PADDING = 10


def _overlay_dot(img: Image.Image, rgba: tuple[int, int, int, int]) -> None:
    d = ImageDraw.Draw(img)
    w, h = img.size
    r = min(w, h) // 5
    d.ellipse((w - r*2, h - r*2, w, h), fill=rgba)


PLAPPER_INTERVAL_S = 0.25
CONTEXT_MENU_WAIT_S = 0.3
_PLAPPER_LOGO = "speech2anywhere-logo-plappern-256.png"


def _make_rounded_square(
    size: int,
    color: tuple[int, int, int, int],
    radius: int,
) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=color,
    )
    return img


_LOGO_CACHE: Image.Image | None = None
_LOGO_CACHE_FAILED = False
_PLAPPER_CACHE: Image.Image | None = None
_ICON_CACHE: dict[State, Image.Image] = {}


def _get_logo() -> Image.Image | None:
    global _LOGO_CACHE, _LOGO_CACHE_FAILED
    if _LOGO_CACHE is not None or _LOGO_CACHE_FAILED:
        return _LOGO_CACHE
    ico = ASSETS / "icon.ico"
    if not ico.exists():
        _LOGO_CACHE_FAILED = True
        return None
    try:
        _LOGO_CACHE = Image.open(ico).convert("RGBA")
    except Exception:
        log.exception("failed to load icon.ico, falling back to placeholder")
        _LOGO_CACHE_FAILED = True
    return _LOGO_CACHE


def _get_plapper_logo() -> Image.Image | None:
    global _PLAPPER_CACHE
    if _PLAPPER_CACHE is None:
        path = ASSETS / "brand" / _PLAPPER_LOGO
        try:
            _PLAPPER_CACHE = Image.open(path).convert("RGBA")
        except OSError:
            log.warning("Tray: Plapperbild fehlt (%s), Aufnahme zeigt das Logo", path)
            return None
    return _PLAPPER_CACHE


def _build_icon(state: State) -> Image.Image:
    logo = _get_logo()
    if logo is not None:
        bg = logo.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    else:
        bg = _make_rounded_square(ICON_SIZE, ICON_BG_COLOR, ICON_BG_RADIUS)
        ImageDraw.Draw(bg).ellipse(
            (ICON_PADDING + 2, ICON_PADDING + 2,
             ICON_SIZE - ICON_PADDING - 3, ICON_SIZE - ICON_PADDING - 3),
            fill=(0, 0, 0, 255),
        )

    if state == State.RECORDING:
        plapper = _get_plapper_logo() if logo is not None else None
        if plapper is not None:
            bg = plapper.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    elif state == State.ERROR:
        _overlay_dot(bg, (255, 80, 0, 255))
    return bg


def _load_or_generate_icon(state: State) -> Image.Image:
    cached = _ICON_CACHE.get(state)
    if cached is not None:
        return cached
    icon = _build_icon(state)
    _ICON_CACHE[state] = icon
    return icon


class KiraTray:
    def __init__(
        self,
        on_quit: Callable[[], None],
        qt_marshal=None,
        transcriber=None,
        learning=None,
    ) -> None:
        self._on_quit = on_quit
        self._qt_marshal = qt_marshal
        self._transcriber = transcriber
        self._state = State.IDLE
        self._status_label = "Bereit"
        self._context_menu = None
        self._icon: pystray.Icon | None = None
        self._settings_dlg = None
        self._learning = learning
        self._learned_dlg = None
        self._transcribe_thread = None
        self._transcribe_worker = None
        self._transcribe_progress = None
        self._update_available: str | None = None
        self._icon_lock = threading.Lock()
        self._plapper_stop: threading.Event | None = None

    def set_transcriber(self, transcriber) -> None:
        self._transcriber = transcriber

    def _build_menu(self) -> pystray.Menu:
        items = [
            pystray.MenuItem(MENU_HEADER, None, enabled=False),
            pystray.MenuItem(self._status_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
        ]
        if self._update_available:
            items.append(
                pystray.MenuItem(
                    f"Update auf v{self._update_available} installieren…",
                    self._check_for_updates,
                ),
            )
        items.append(
            pystray.MenuItem(
                "Einstellungen…", self._open_settings, default=True,
            ),
        )
        if self._learning is not None:
            items.append(
                pystray.MenuItem(self._learned_words_label(), self._open_learned_words),
            )
        if self._transcriber is not None:
            items.append(
                pystray.MenuItem(
                    "Datei transkribieren…", self._open_transcribe_file,
                ),
            )
        items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Anleitung…", self._open_help),
            pystray.MenuItem("Protokoll öffnen…", self._open_log),
            pystray.MenuItem("Updates suchen…", self._check_for_updates),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Über Speech2Anywhere", self._about),
            pystray.MenuItem("Beenden", self._quit),
        ])
        return pystray.Menu(*items)

    def _comic_menu(self):
        from kira.ui import _comic as comic
        menu = comic.ComicMenu()
        menu.addAction(comic.menu_header(menu))
        separated = True
        for item in self._build_menu().items:
            if item is pystray.Menu.SEPARATOR:
                if not separated:
                    menu.addSeparator()
                    separated = True
                continue
            if item.text == MENU_HEADER or not item.visible:
                continue
            if not item.enabled:
                menu.addAction(f"●  {item.text}").setEnabled(False)
            else:
                action = menu.addAction(item.text)
                action.triggered.connect(lambda _checked=False, entry=item: entry(self._icon))
                if item.default:
                    menu.setDefaultAction(action)
            separated = False
        return menu

    def _request_context_menu(self) -> bool:
        if self._qt_marshal is None:
            return False
        responsive = threading.Event()
        self._qt_marshal.run_on_main_thread(responsive.set)
        if not responsive.wait(CONTEXT_MENU_WAIT_S):
            log.info("Tray-Menü: Qt-Hauptthread belegt, zeige das Windows-Menü")
            return False
        self._marshal_to_qt(self._show_context_menu, "tray menu")
        return True

    def _show_context_menu(self) -> None:
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QCursor
        if self._context_menu is not None:
            self._context_menu.close()
        menu = self._comic_menu()

        def forget() -> None:
            if self._context_menu is menu:
                self._context_menu = None
            menu.deleteLater()

        menu.aboutToHide.connect(forget)
        self._context_menu = menu
        size = menu.sizeHint()
        pos = QCursor.pos()
        menu.popup(QPoint(pos.x() - size.width() + 8, pos.y() - size.height()))
        menu.activateWindow()

    def update_state(self, state: State) -> None:
        self._state = state
        self._status_label = {
            State.IDLE: "Bereit",
            State.RECORDING: "Aufnahme läuft…",
            State.TRANSCRIBING: "Transkribiere…",
            State.STYLING: "Poliere…",
            State.INJECTING: "Füge ein…",
            State.ERROR: "Fehler, siehe Protokoll",
        }.get(state, "Unbekannt")
        with self._icon_lock:
            if self._plapper_stop is not None:
                self._plapper_stop.set()
                self._plapper_stop = None
            if self._icon is None:
                return
            self._icon.icon = _load_or_generate_icon(state)
            self._icon.menu = self._build_menu()
            if state == State.RECORDING:
                stop = threading.Event()
                self._plapper_stop = stop
                threading.Thread(
                    target=self._plapper, args=(stop,), daemon=True, name="tray-plapper",
                ).start()

    def _plapper(self, stop: threading.Event) -> None:
        frames = (_load_or_generate_icon(State.IDLE), _load_or_generate_icon(State.RECORDING))
        i = 0
        while not stop.wait(PLAPPER_INTERVAL_S):
            with self._icon_lock:
                if stop.is_set() or self._icon is None:
                    return
                self._icon.icon = frames[i % 2]
            i += 1

    def _open_settings(self, _icon, _item) -> None:
        self._marshal_to_qt(self._show_settings_dialog, "settings dialog")

    def _show_settings_dialog(self) -> None:
        if self._settings_dlg is not None:
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return
        from kira.ui.settings_dialog import SettingsDialog
        if self._learning is not None:
            dlg = SettingsDialog(open_learned_words=self._show_learned_words_dialog)
        else:
            dlg = SettingsDialog()
        self._settings_dlg = dlg
        try:
            getattr(dlg, "exec")()
        finally:
            self._settings_dlg = None

    def _learned_words_label(self) -> str:
        try:
            pending = self._learning.pending_count()
        except Exception:
            log.exception("Lernen: Zähler fürs Tray-Menü nicht lesbar")
            pending = 0
        return f"Gelernte Wörter ({pending} neu)…" if pending else "Gelernte Wörter…"

    def _open_learned_words(self, _icon, _item) -> None:
        self._marshal_to_qt(self._show_learned_words_dialog, "learned words dialog")

    def _show_learned_words_dialog(self) -> None:
        if self._learning is None:
            return
        if self._learned_dlg is not None:
            self._learned_dlg.raise_()
            self._learned_dlg.activateWindow()
            return
        from kira.ui.learned_words_dialog import LearnedWordsDialog
        dlg = LearnedWordsDialog(self._learning)
        self._learned_dlg = dlg
        try:
            getattr(dlg, "exec")()
        finally:
            self._learned_dlg = None
            if self._icon is not None:
                self._icon.menu = self._build_menu()

    def _open_log(self, _icon, _item) -> None:
        log_path = Path(os.environ["LOCALAPPDATA"]) / "Kira" / LOG_NAME
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            log_path.write_text("", encoding="utf-8")
        try:
            subprocess.Popen(["notepad.exe", str(log_path)])
        except (OSError, FileNotFoundError) as exc:
            log.exception("notepad launch failed for log %s", log_path)
            message = str(exc)
            self._marshal_to_qt(
                lambda: self._show_notepad_fallback(str(log_path), message),
                "notepad fallback",
            )

    @staticmethod
    def _show_notepad_fallback(file_path: str, exc_msg: str) -> None:
        from kira.ui._dialog_style import light_warning
        light_warning(
            None, "Speech2Anywhere",
            f"Notepad konnte nicht gestartet werden: {exc_msg}\n\n"
            f"Datei manuell öffnen:\n{file_path}",
        )

    def _open_help(self, _icon, _item) -> None:
        self._marshal_to_qt(self._show_help_dialog, "help dialog")

    @staticmethod
    def _show_help_dialog() -> None:
        from kira.ui.welcome_dialog import WelcomeDialog
        dlg = WelcomeDialog(as_help=True)
        getattr(dlg, "exec")()

    def _open_transcribe_file(self, _icon, _item) -> None:
        if self._transcriber is None:
            log.warning("transcribe-file menu fired but no transcriber wired")
            return
        self._marshal_to_qt(
            lambda: self._show_transcribe_file_dialog(self._transcriber),
            "transcribe-file dialog",
        )

    def _show_transcribe_file_dialog(self, transcriber) -> None:
        from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
        from PyQt6.QtWidgets import (
            QFileDialog, QProgressDialog,
        )
        from kira.ui._dialog_style import (
            apply_light_theme,
            light_critical,
            light_information,
        )

        if self._transcribe_thread is not None and self._transcribe_thread.isRunning():
            light_information(
                None, "Speech2Anywhere",
                "Es läuft bereits eine Datei-Transkription. Bitte warten, "
                "bis sie abgeschlossen ist.",
            )
            return

        path, _filter = QFileDialog.getOpenFileName(
            None,
            "Audio- oder Videodatei zum Transkribieren auswählen",
            "",
            "Medien (*.wav *.mp3 *.m4a *.flac *.ogg *.opus *.mp4 *.mov *.mkv *.webm);;Alle Dateien (*.*)",
        )
        if not path:
            return
        log.info("File-Transcription requested: %s", path)

        progress = QProgressDialog(
            f"Transkribiere {Path(path).name}…",
            "Abbrechen", 0, 0, None,
        )
        progress.setWindowTitle("Speech2Anywhere: Datei transkribieren")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        apply_light_theme(progress)
        progress.show()

        class _Worker(QObject):
            done = pyqtSignal(str, str)
            failed = pyqtSignal(str)

            def __init__(self, src_path: str):
                super().__init__()
                self._src = src_path

            def run(self) -> None:
                try:
                    result = transcriber.transcribe_file(self._src)
                    if not result.text:
                        self.failed.emit(
                            "Das Transkript ist leer. Entweder ist die Datei still, "
                            "oder die Spracherkennung hat nichts verstanden."
                        )
                        return
                    out = Path(self._src).with_suffix(".txt")
                    out.write_text(result.text, encoding="utf-8")
                    self.done.emit(str(out), result.language)
                except Exception as exc:
                    log.exception("file-transcription worker crashed")
                    self.failed.emit(f"Fehler: {exc}")

        thread = QThread()
        worker = _Worker(path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        cancelled = {"val": False}

        def on_cancelled() -> None:
            cancelled["val"] = True
            log.info(
                "File-Transcription abgebrochen (Worker laeuft im "
                "Hintergrund aus, Ergebnis wird verworfen)"
            )

        progress.canceled.connect(on_cancelled)

        def _teardown() -> None:
            thread.quit()
            thread.wait()
            self._transcribe_thread = None
            self._transcribe_worker = None
            self._transcribe_progress = None

        def on_done(out_path: str, language: str) -> None:
            progress.close()
            _teardown()
            if cancelled["val"]:
                return
            light_information(
                None, "Speech2Anywhere",
                f"Fertig.\n\nTranskript gespeichert unter:\n{out_path}\n\n"
                f"Erkannte Sprache: {language}",
            )

        def on_failed(message: str) -> None:
            progress.close()
            _teardown()
            if cancelled["val"]:
                return
            light_critical(None, "Speech2Anywhere", message)

        worker.done.connect(on_done)
        worker.failed.connect(on_failed)
        thread.start()
        self._transcribe_thread = thread
        self._transcribe_worker = worker
        self._transcribe_progress = progress

    def _about(self, _icon, _item) -> None:
        self._marshal_to_qt(self._show_about_dialog, "about dialog")

    @staticmethod
    def _show_about_dialog() -> None:
        from kira.ui.about_dialog import AboutDialog
        dlg = AboutDialog()
        getattr(dlg, "exec")()

    def _marshal_to_qt(self, func, label: str) -> None:
        if self._qt_marshal is None:
            log.warning(
                "%s: no qt_marshal wired up, skipping (Qt loop unavailable)",
                label,
            )
            return
        self._qt_marshal.run_on_main_thread(func)

    def _check_for_updates(self, _icon, _item) -> None:
        self._marshal_to_qt(
            lambda: self._run_update_flow_marshalled(self._on_quit),
            "update flow",
        )

    def set_update_available(self, version: str | None) -> None:
        if version == self._update_available:
            return
        self._update_available = version
        if self._icon is not None:
            self._icon.menu = self._build_menu()

    def notify_update(self, version: str) -> None:
        self.notify(
            "Speech2Anywhere: Update verfügbar",
            f"Speech2Anywhere v{version} ist verfügbar. Installieren im "
            f"Tray-Menü: „Update auf v{version} installieren…“.",
        )

    @staticmethod
    def _run_update_flow_marshalled(quit_callback) -> None:
        from kira.ui._update_runner import run_update_flow
        run_update_flow(parent=None, on_quit_request=quit_callback)

    def prompt_start_update(self, remote_version: str, on_declined=None) -> None:
        from PyQt6.QtWidgets import QMessageBox
        from kira import __version__
        from kira.ui._dialog_style import apply_light_theme
        from kira.ui._update_runner import flow_active

        if flow_active():
            log.info("Start-Update-Check: Update läuft bereits, keine Abfrage für v%s", remote_version)
            return

        msg = QMessageBox(None)
        msg.setWindowTitle("Speech2Anywhere: Update verfügbar")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(f"Eine neue Version ist verfügbar: v{remote_version}.")
        msg.setInformativeText(
            f"Du verwendest v{__version__}.\n\n"
            "Jetzt herunterladen und installieren?"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        apply_light_theme(msg)
        accepted = msg.exec() == QMessageBox.StandardButton.Yes

        if accepted:
            log.info("Start-Update-Check: Nutzer hat v%s akzeptiert", remote_version)
            self._run_update_flow_marshalled(self._on_quit)
        else:
            log.info("Start-Update-Check: Nutzer hat v%s abgelehnt", remote_version)
            if on_declined is not None:
                on_declined(remote_version)

    def _quit(self, _icon, _item) -> None:
        try:
            self._on_quit()
        except Exception:
            log.exception("on_quit raised")
        if self._icon is not None:
            self._icon.stop()

    def run(self) -> None:
        self._icon = _KiraPystrayIcon(
            "kira",
            icon=_load_or_generate_icon(State.IDLE),
            title="Speech2Anywhere",
            menu=self._build_menu(),
        )
        if self._qt_marshal is not None:
            self._icon.on_context_menu = self._request_context_menu
        self._icon.run()

    def run_detached(self) -> threading.Thread:
        t = threading.Thread(target=self.run, daemon=True, name="kira-tray")
        t.start()
        threading.Thread(
            target=lambda: _set_tray_window_title(self),
            daemon=True, name="kira-tray-title",
        ).start()
        return t

    def notify(self, title: str, message: str) -> None:
        if self._icon is None:
            log.warning(
                "tray.notify called before tray is up, dropping %r", title,
            )
            return
        if len(message) > 255:
            message = message[:254] + "…"
        if len(title) > 63:
            title = title[:62] + "…"
        try:
            self._icon.notify(message, title)
        except Exception:
            log.exception("tray notification failed (title=%r)", title)
