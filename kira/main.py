from __future__ import annotations
import asyncio
import faulthandler
import logging
import logging.handlers
import os
import sys
import threading
import time
from pathlib import Path

if sys.platform == "darwin":
    from kira.hotkey import HotkeyListener
    from kira.injector import Injector
    from kira.context import detect_mode
    from kira.permissions import check_all
    from kira.welcome import run_if_needed, ensure_ollama_model
    from kira.ui.menubar import KiraMenubar
    from kira.ui.popup import PopupHUD
    from kira.transcriber import Transcriber
elif sys.platform == "win32":
    from kira.hotkey_win import HotkeyListener
    from kira.injector_win import Injector
    from kira.context_win import detect_mode
    from kira.permissions_win import check_all
    from kira.welcome_win import (
        run_if_needed,
        ensure_ollama_model,
        probe_setup_status,
        show_setup_hint_if_needed,
    )
    from kira.ui.tray_win import KiraTray as KiraMenubar
    from kira.ui.hud_qt import PopupHUD
    from kira.transcriber_fw import Transcriber
else:
    raise RuntimeError(f"Unsupported platform: {sys.platform}")

from kira import FAULTHANDLER_LOG_NAME, LOG_NAME
from kira.config import load_config
from kira.recorder import Recorder
from kira.styler import Styler
from kira.app import KiraApp, State


def _log_path() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Kira" / LOG_NAME
    return Path.home() / "Library" / "Logs" / "kira.log"


LOG_PATH = _log_path()
FAULTHANDLER_PATH = LOG_PATH.parent / FAULTHANDLER_LOG_NAME

LOG_MAX_BYTES = 15 * 1024 * 1024
LOG_BACKUP_COUNT = 1
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_PACKAGE = "kira"
_SHOWN_AS = "speech2anywhere"


class _BrandFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        name = record.name
        if name != _PACKAGE and not name.startswith(_PACKAGE + "."):
            return super().format(record)
        record.name = _SHOWN_AS + name[len(_PACKAGE):]
        try:
            return super().format(record)
        finally:
            record.name = name


def _dictation_listener(listener_cls, combo: str, on_press, on_release):
    try:
        return listener_cls(combo=combo, on_press=on_press, on_release=on_release), combo
    except ValueError:
        log.warning("Diktat-Taste %r wird nicht unterstützt, es gilt f8", combo)
        return listener_cls(combo="f8", on_press=on_press, on_release=on_release), "f8"


def _build_log_handler(path: Path) -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        str(path),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(_BrandFormatter(_LOG_FORMAT))
    return handler


def _configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[_build_log_handler(LOG_PATH)])


log = logging.getLogger("kira.main")

_FAULTHANDLER_STREAM = None


def _enable_crash_diagnostics() -> None:
    global _FAULTHANDLER_STREAM
    fh_path = FAULTHANDLER_PATH
    try:
        _FAULTHANDLER_STREAM = open(fh_path, "a", buffering=1, encoding="utf-8")
        faulthandler.enable(file=_FAULTHANDLER_STREAM, all_threads=True)
    except OSError:
        log.exception("failed to open faulthandler stream at %s", fh_path)

    def _excepthook(exc_type, exc, tb) -> None:
        log.error("UNHANDLED top-level exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = _excepthook

    def _thread_excepthook(args) -> None:
        if args.exc_type is SystemExit:
            return
        log.error(
            "UNHANDLED exception in thread %r",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_excepthook


def _install_qt_message_handler() -> None:
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    _level_for = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    qt_log = logging.getLogger("kira.qt")

    def _handler(msg_type, ctx, msg) -> None:
        qt_log.log(
            _level_for.get(msg_type, logging.INFO),
            "%s [%s:%s in %s]",
            msg,
            (ctx.file or "?") if ctx else "?",
            (ctx.line or 0) if ctx else 0,
            (ctx.function or "?") if ctx else "?",
        )

    qInstallMessageHandler(_handler)


def _start_heartbeat() -> None:
    started_at = time.monotonic()

    def _loop() -> None:
        while True:
            time.sleep(60)
            uptime = int(time.monotonic() - started_at)
            log.info("heartbeat: uptime=%ds", uptime)

    threading.Thread(target=_loop, daemon=True, name="kira-heartbeat").start()


def _run_mac(cfg, recorder, transcriber, styler, injector) -> None:
    menubar = KiraMenubar(on_quit=lambda: None)
    popup = PopupHUD() if cfg.ui.popup else None

    def handle_state(s: State) -> None:
        menubar.update_state(s)
        if popup is None:
            return
        if s == State.RECORDING:
            popup.show("Recording…")
        elif s == State.TRANSCRIBING:
            popup.update_status("Transcribing…")
        elif s == State.STYLING:
            popup.update_status("Polishing…")
        elif s in (State.IDLE, State.ERROR):
            popup.hide()

    app = KiraApp(
        config=cfg, recorder=recorder, transcriber=transcriber,
        styler=styler, injector=injector, on_state_change=handle_state,
    )

    if popup is not None:
        recorder.set_level_callback(lambda lvl: popup.push_level(lvl))

    loop = asyncio.new_event_loop()
    threading.Thread(
        target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()),
        daemon=True,
    ).start()
    app.set_loop(loop)

    if cfg.styler.provider == "ollama" and cfg.styler.warmup_on_start:
        asyncio.run_coroutine_threadsafe(styler.warmup(), loop)

    hotkey = HotkeyListener(
        combo=cfg.hotkey.combo,
        on_press=app.on_hotkey_press,
        on_release=app.on_hotkey_release,
    )
    hotkey.start()
    log.info("Speech2Anywhere ready, hotkey %s", cfg.hotkey.combo)
    menubar.run()


_APP_USER_MODEL_ID = "Digitalroots.Kira.1"
_SINGLE_INSTANCE_MUTEX = "Local\\Digitalroots.Kira.SingleInstance"

def _resolve_assets_dir() -> Path:
    pkg_dir = Path(__file__).resolve().parent
    wheel_assets = pkg_dir / "_assets"
    if wheel_assets.exists():
        return wheel_assets
    return pkg_dir.parent / "assets"


_ASSETS_DIR = _resolve_assets_dir()
_ICON_PATH = _ASSETS_DIR / "icon-branded.ico"


_RESOURCE_REL_MAP = {
    "assets": "_assets",
    "prompts": "_prompts",
}


def _bundle_root() -> Path | None:
    try:
        candidate = Path(sys.executable).resolve().parent.parent
    except (OSError, ValueError):
        return None
    if (candidate / "installer" / "embedded").exists():
        return candidate
    return None


def _resource_path(rel_path: str) -> Path:
    pkg_dir = Path(__file__).resolve().parent
    rel_norm = rel_path.replace("\\", "/")

    for source_prefix, wheel_prefix in _RESOURCE_REL_MAP.items():
        if rel_norm.startswith(source_prefix + "/") or rel_norm == source_prefix:
            wheel_rel = wheel_prefix + rel_norm[len(source_prefix):]
            wheel_target = (pkg_dir / wheel_rel).resolve()
            if wheel_target.exists() and wheel_target.is_relative_to(pkg_dir):
                return wheel_target
            break

    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS).resolve()
        target = (base / rel_path).resolve()
        if not target.is_relative_to(base):
            raise ValueError(f"Path traversal attempt blocked: {rel_path!r}")
        return target

    bundle_root = _bundle_root()
    if bundle_root is not None:
        target = (bundle_root / rel_path).resolve()
        if target.exists() and target.is_relative_to(bundle_root):
            return target

    base = pkg_dir.parent
    target = (base / rel_path).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"Path traversal attempt blocked: {rel_path!r}")
    return target


def _set_windows_app_identity() -> None:
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
    except Exception:
        log.exception("SetCurrentProcessExplicitAppUserModelID failed")


def _acquire_windows_single_instance_lock() -> object | None:
    import ctypes
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    h = kernel32.CreateMutexW(None, True, _SINGLE_INSTANCE_MUTEX)
    if not h:
        log.warning("CreateMutexW failed; skipping single-instance check")
        return object()
    if ctypes.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(h)
        return None
    return h


def _run_windows(cfg, recorder, transcriber, styler, injector) -> None:
    _set_windows_app_identity()

    from kira._wsl_warmup import kick_wsl_distro
    kick_wsl_distro()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    _install_qt_message_handler()
    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)
    if _ICON_PATH.exists():
        qt_app.setWindowIcon(QIcon(str(_ICON_PATH)))
    else:
        log.warning("icon not found at %s, taskbar will use default", _ICON_PATH)

    from kira.firstrun import is_first_run as is_first_setup_run
    if is_first_setup_run():
        from kira.setup_wizard import SetupWizard

        whisper_target = Path.home() / "models" / "faster-whisper-large-v3"
        ollama_setup = _resource_path("installer/embedded/OllamaSetup.exe")

        log.info("First-run detected, launching SetupWizard")
        wizard = SetupWizard(whisper_target, ollama_setup)
        wizard_result = wizard.exec()
        if wizard_result != SetupWizard.DialogCode.Accepted:
            log.warning("First-run wizard aborted by user, exiting.")
            return

    from kira.ui.splash import make_splash
    splash = make_splash()
    if splash is not None:
        from PyQt6.QtCore import QElapsedTimer
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < 2000:
            qt_app.processEvents()
            time.sleep(0.05)
        splash.close()
        qt_app.processEvents()
        splash = None

    from kira.ui.welcome_dialog import WelcomeDialog, is_first_run
    if is_first_run():
        log.info("First run detected, showing welcome dialog")
        run_modal = getattr(WelcomeDialog(), "exec")
        run_modal()


    popup = PopupHUD() if cfg.ui.popup else None
    live_words = None
    if popup is not None:
        from kira.live_words import LiveWords
        live_words = LiveWords(
            transcriber.transcribe_partial, popup.push_words, wanted=lambda: popup.wants_live_words,
        )

    def _on_tray_quit() -> None:
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        try:
            recorder.close()
        except Exception:
            log.exception("recorder.close raised during quit")
        QTimer.singleShot(0, qt_app.quit)

    try:
        from kira.learning_win import prune_history
        prune_history()
    except Exception:
        log.exception("Verlauf: Löschfrist konnte nicht laufen")
    learning = None
    if cfg.learning.enabled:
        try:
            from kira.learning_win import LearningService
            learning = LearningService.create(cfg)
            transcriber.set_lexicon(learning.lexicon)
        except Exception:
            log.exception("Lernschleife konnte nicht starten; Speech2Anywhere läuft ohne")
            learning = None

    if sys.platform == "win32":
        from kira.ui.qt_marshal import MainThreadMarshal
        qt_marshal = MainThreadMarshal()
        tray = KiraMenubar(
            on_quit=_on_tray_quit,
            qt_marshal=qt_marshal,
            transcriber=transcriber,
            learning=learning,
        )
        styler.set_on_slow_polish_detected(
            lambda: tray.notify(
                "Speech2Anywhere: Polish auf CPU",
                "Polish-Latenz hoch. Temporaer auf schnelles Modell "
                "umgeschaltet. Pruefe Settings → GPU-Check.",
            )
        )
        def _notify_cpu_fallback(msg: str) -> None:
            try:
                from kira.ollama_diag import diagnose_ollama_port, resolve_notice
                diag = diagnose_ollama_port()
                log.warning("Ollama-Port-Diagnose: %s", diag.hint)
                msg = resolve_notice(msg, diag)
            except Exception:
                log.exception("Ollama-Port-Diagnose fehlgeschlagen")
            tray.notify("Speech2Anywhere: Polish auf CPU", msg)

        styler.set_on_cpu_fallback_detected(_notify_cpu_fallback)
        styler.set_on_connection_lost(
            lambda: tray.notify(
                "Speech2Anywhere: Politur nicht erreichbar",
                "Ollama antwortet nicht. Bis auf Weiteres wird der "
                "Rohtext eingefügt. Details im Log.",
            )
        )
    else:
        tray = KiraMenubar(on_quit=_on_tray_quit)

    def handle_state(s: State) -> None:
        try:
            tray.update_state(s)
        except Exception:
            log.exception("Tray-Zustand %s nicht gesetzt; Anzeige läuft weiter", s)
        if popup is None:
            return
        if live_words is not None and s != State.RECORDING:
            live_words.stop()
        if s == State.RECORDING:
            popup.set_phase("rec")
            if live_words is not None:
                live_words.start()
        elif s == State.TRANSCRIBING:
            popup.set_phase("trans")
        elif s == State.STYLING:
            popup.set_texts(raw=app.last_transcript)
            popup.set_phase("polish")
        elif s == State.INJECTING:
            popup.set_texts(polished=app.last_polished)
            popup.set_phase("done")
        elif s == State.ERROR:
            popup.set_phase("error", app.last_error)
        elif s == State.IDLE:
            popup.set_phase("idle")

    app = KiraApp(
        config=cfg, recorder=recorder, transcriber=transcriber,
        styler=styler, injector=injector, on_state_change=handle_state,
        learning=learning,
    )

    if popup is not None:
        def _samples(arr) -> None:
            popup.push_samples(arr)
            if live_words is not None:
                live_words.push(arr)

        recorder.set_samples_callback(_samples)

    loop = asyncio.new_event_loop()
    threading.Thread(
        target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()),
        daemon=True,
    ).start()
    app.set_loop(loop)

    if cfg.styler.provider == "ollama" and cfg.styler.warmup_on_start:
        asyncio.run_coroutine_threadsafe(styler.warmup(), loop)

    threading.Thread(
        target=transcriber.warmup,
        daemon=True, name="kira-whisper-warmup",
    ).start()

    from kira.config import effective_hotkey
    hotkey, combo = _dictation_listener(
        HotkeyListener, effective_hotkey(cfg.hotkey.combo), app.on_hotkey_press, app.on_hotkey_release,
    )
    hotkey.start()

    edit_hotkey = None
    if cfg.hotkey.edit_combo:
        try:
            edit_hotkey = HotkeyListener(
                combo=cfg.hotkey.edit_combo,
                on_press=app.on_edit_press,
                on_release=app.on_hotkey_release,
            )
            edit_hotkey.start()
            log.info(
                "Edit-Command hotkey aktiv (combo=%s)", cfg.hotkey.edit_combo,
            )
        except ValueError:
            log.warning(
                "edit_combo=%r ist nicht supported, Edit-Command-Feature "
                "deaktiviert. Erlaubt: %s",
                cfg.hotkey.edit_combo,
                ", ".join(sorted(__import__("kira.hotkey_win", fromlist=["SUPPORTED_COMBOS"]).SUPPORTED_COMBOS)),
            )

    tray.run_detached()

    if learning is not None:
        learning.start()

    if splash is not None:
        splash.close()

    log.info("Speech2Anywhere ready, hotkey %s (Windows)", combo)

    def _check_setup() -> None:
        try:
            from kira.welcome_win import _ollama_reachable_once
            mic_ok, ollama_ok = probe_setup_status()
            if not mic_ok:
                qt_marshal.run_on_main_thread(
                    lambda: show_setup_hint_if_needed(mic_ok, ollama_ok)
                )
            if ollama_ok:
                if not ensure_ollama_model(cfg.styler.model):
                    log.warning(
                        "Ollama model %s not ready, polish will fall back to raw",
                        cfg.styler.model,
                    )
                return
            log.info(
                "Ollama unreachable in initial probe; background re-probe started"
            )
            for i in range(20):
                time.sleep(30)
                if _ollama_reachable_once():
                    log.info("Ollama reachable on retry #%d", i + 1)
                    if not ensure_ollama_model(cfg.styler.model):
                        log.warning(
                            "Ollama model %s not ready, polish will fall back to raw",
                            cfg.styler.model,
                        )
                    if (
                        cfg.styler.provider == "ollama"
                        and cfg.styler.warmup_on_start
                        and not styler.warmup_succeeded
                    ):
                        log.info("Hole Styler-Warmup nach (Boot-Warmup scheiterte)")
                        asyncio.run_coroutine_threadsafe(styler.warmup(), loop)
                    return
            log.info(
                "Ollama still unreachable after 10 min; polish will use raw fallback"
            )
        except Exception:
            log.exception("background setup check failed; continuing")

    threading.Thread(
        target=_check_setup, daemon=True, name="kira-setup-check",
    ).start()

    def _check_for_app_update() -> None:
        if not cfg.updates.check_on_start:
            log.info("Start-Update-Check via Config deaktiviert (updates.check_on_start=false)")
            return
        try:
            from kira._update_marker import mark_update_declined

            remote = update_watch.start_result(_check_now())
            if remote is None:
                return
            qt_marshal.run_on_main_thread(
                lambda: tray.prompt_start_update(remote, on_declined=mark_update_declined)
            )
        except Exception:
            log.exception("Start-Update-Check fehlgeschlagen; wird ignoriert")

    from kira import __version__ as _kira_version, UPDATE_REPO as _update_repo
    from kira._update_marker import is_update_declined as _is_declined
    from kira.update_watch import UpdateWatch, start_watch

    def _check_now():
        from kira.updater import check_for_update
        return check_for_update(local_version=_kira_version, repo=_update_repo)

    update_watch = UpdateWatch(
        check=_check_now,
        is_declined=_is_declined,
        set_available=tray.set_update_available,
        notify=tray.notify_update,
    )

    threading.Thread(
        target=_check_for_app_update, daemon=True, name="kira-update-check",
    ).start()

    start_watch(
        update_watch,
        enabled=cfg.updates.check_on_start,
        interval_h=cfg.updates.check_interval_hours,
    )

    _qt_main = getattr(qt_app, "exec")
    _qt_main()


def run() -> None:
    _configure_logging()
    _enable_crash_diagnostics()
    _start_heartbeat()
    cfg = load_config()
    log.info("Starting Speech2Anywhere (platform=%s)", sys.platform)

    if sys.platform == "win32":
        _instance_lock = _acquire_windows_single_instance_lock()
        if _instance_lock is None:
            log.warning("Another Speech2Anywhere instance is already running, exiting")
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "Speech2Anywhere läuft bereits (siehe Tray-Icon rechts unten).\n"
                "Diese zweite Instanz wird beendet.",
                "Speech2Anywhere",
                0x40,
            )
            return

    if cfg.styler.provider == "ollama":
        try:
            from kira.ollama_env import apply_tuning_env
            apply_tuning_env()
        except Exception:
            log.exception("Ollama-VRAM-Tuning fehlgeschlagen; continuing")

    if sys.platform == "darwin":
        try:
            if not run_if_needed():
                log.warning("Setup incomplete; some features may not work")
            if not ensure_ollama_model(cfg.styler.model):
                log.warning(
                    "Ollama model %s not ready, polish will fall back to raw",
                    cfg.styler.model,
                )
        except Exception:
            log.exception("welcome check failed; continuing")

    recorder = Recorder(
        input_gain=cfg.audio.input_gain,
        input_device=cfg.audio.input_device,
    )
    try:
        recorder.prewarm()
    except Exception:
        log.exception("recorder.prewarm failed; falling back to lazy stream-open")
    transcriber = Transcriber(cfg)
    styler = Styler(cfg)
    injector = Injector(restore_after_ms=cfg.injector.restore_clipboard_after_ms)

    if sys.platform == "darwin":
        _run_mac(cfg, recorder, transcriber, styler, injector)
    elif sys.platform == "win32":
        _run_windows(cfg, recorder, transcriber, styler, injector)
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")


if __name__ == "__main__":
    run()
