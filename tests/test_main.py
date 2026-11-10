from __future__ import annotations
import logging.handlers


def test_log_handler_is_rotating(tmp_path):
    from kira import main
    handler = main._build_log_handler(tmp_path / "kira.log")
    assert isinstance(handler, logging.handlers.RotatingFileHandler)


def test_log_handler_total_cap_at_most_30mb(tmp_path):
    from kira import main
    handler = main._build_log_handler(tmp_path / "kira.log")
    total_cap = handler.maxBytes * (1 + handler.backupCount)
    assert handler.maxBytes > 0, "maxBytes=0 deaktiviert Rotation komplett"
    assert handler.backupCount >= 1, "ohne Backup geht beim Roll-Over History verloren"
    assert total_cap <= 30 * 1024 * 1024, f"Gesamt-Cap {total_cap} überschreitet 30 MB"


def test_log_handler_writes_utf8(tmp_path):
    from kira import main
    handler = main._build_log_handler(tmp_path / "kira.log")
    normalized = (handler.encoding or "").lower().replace("-", "")
    assert normalized == "utf8", f"encoding={handler.encoding!r}, erwartet utf-8"


def test_log_files_are_named_speech2anywhere():
    from kira import main
    assert main.LOG_PATH.name == "speech2anywhere.log"
    assert main.LOG_PATH.parent.name == "Kira"
    assert main.FAULTHANDLER_PATH.name == "speech2anywhere-faulthandler.log"
    assert main.FAULTHANDLER_PATH.parent == main.LOG_PATH.parent


def test_log_lines_show_speech2anywhere_for_the_app_loggers(tmp_path):
    from kira import main
    handler = main._build_log_handler(tmp_path / "speech2anywhere.log")
    try:
        def line(name: str) -> str:
            return handler.format(logging.LogRecord(name, logging.INFO, __file__, 1, "nachricht", None, None))

        record = logging.LogRecord("kira.styler", logging.INFO, __file__, 1, "Warmup fertig", None, None)
        assert "INFO speech2anywhere.styler: Warmup fertig" in handler.format(record)
        assert record.name == "kira.styler", "der Eintrag selbst bleibt unverändert"
        assert "INFO speech2anywhere: nachricht" in line("kira")
        assert "INFO httpx: nachricht" in line("httpx")
        assert "INFO kirakira.x: nachricht" in line("kirakira.x")
    finally:
        handler.close()


def test_unsupported_hotkey_falls_back_to_f8():
    from kira import main
    erzeugt = []

    class Lauscher:
        def __init__(self, combo, on_press, on_release):
            if combo not in ("f8", "f9"):
                raise ValueError(f"Unsupported combo: {combo}")
            erzeugt.append(combo)

    listener, combo = main._dictation_listener(Lauscher, "ctrl+shift+space", lambda: None, lambda: None)
    assert combo == "f8" and erzeugt == ["f8"] and isinstance(listener, Lauscher)
    listener, combo = main._dictation_listener(Lauscher, "f9", lambda: None, lambda: None)
    assert combo == "f9"


def test_start_removes_installed_update_dirs_in_the_background(tmp_path, monkeypatch):
    from kira import main
    from kira.ui import _update_runner
    monkeypatch.setattr(_update_runner, "_bundle_dir", lambda: tmp_path)
    for name in ("v0.0.1", "v99.0.0"):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"Kira-Setup-{name}.exe").write_bytes(b"setup")
    thread = main._start_update_cleanup()
    thread.join(10)
    assert thread.name == "kira-update-cleanup"
    assert not (tmp_path / "v0.0.1").exists()
    assert (tmp_path / "v99.0.0").is_dir()


def _fake_app():
    import types
    calls = []
    return types.SimpleNamespace(
        calls=calls,
        on_hotkey_press=lambda: calls.append("press"),
        on_hotkey_release=lambda: calls.append("release"),
        on_edit_press=lambda: calls.append("edit"),
        on_hotkey_toggle=lambda: calls.append("toggle"),
        on_edit_toggle=lambda: calls.append("edit-toggle"),
    )


def test_hold_mode_wires_press_and_release():
    from kira import main
    app = _fake_app()
    press, edit_press, release = main._hotkey_callbacks(app, "hold")
    press()
    edit_press()
    release()
    assert app.calls == ["press", "edit", "release"]


def test_toggle_mode_wires_the_toggles_and_ignores_the_key_release():
    from kira import main
    app = _fake_app()
    press, edit_press, release = main._hotkey_callbacks(app, "toggle")
    press()
    edit_press()
    release()
    assert app.calls == ["toggle", "edit-toggle"]


def test_start_sets_the_interface_language_from_the_config():
    from kira import main, texte
    from kira.config import Config
    cfg = Config()
    cfg.ui.language = "en"
    try:
        main._apply_language(cfg)
        assert texte.language() == "en"
    finally:
        texte.set_language("de")


def test_restarted_instance_waits_before_the_single_instance_check(monkeypatch):
    import sys
    import pytest
    if sys.platform != "win32":
        pytest.skip("windows-only")
    import ctypes
    from kira import main, restart
    from kira.config import Config
    order = []
    for name in ("_configure_logging", "_enable_crash_diagnostics", "_start_heartbeat"):
        monkeypatch.setattr(main, name, lambda: None)
    monkeypatch.setattr(main, "load_config", lambda: Config())
    monkeypatch.setattr(main, "_apply_language", lambda cfg: None)
    monkeypatch.setattr(restart, "wait_for_predecessor", lambda: order.append("warten") or True)
    monkeypatch.setattr(main, "_acquire_windows_single_instance_lock", lambda: order.append("sperre"))
    monkeypatch.setattr(ctypes.windll.user32, "MessageBoxW", lambda *a: order.append("meldung") or 0)
    main.run()
    assert order == ["warten", "sperre", "meldung"]


def test_polish_model_follows_fast_mode_and_processor_mode():
    from kira.config import Config
    from kira.main import _polish_model
    base = {"styler": {"model": "gemma4:12b", "fast_model": "gemma4:e4b"}}
    assert _polish_model(Config.model_validate(base)) == "gemma4:12b"
    assert _polish_model(Config.model_validate({**base, "whisper": {"device": "cpu"}})) == "gemma4:e4b"
    fast = {"styler": {**base["styler"], "fast_mode": True}}
    assert _polish_model(Config.model_validate(fast)) == "gemma4:e4b"


def test_qt_arguments_pick_the_freetype_engine_on_windows(monkeypatch):
    from kira import main
    monkeypatch.setattr(main.sys, "platform", "win32")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    assert main.qt_arguments(["kira"]) == ["kira", "-platform", "windows:fontengine=freetype"]
    assert main.qt_arguments(["kira", "-platform", "offscreen"]) == ["kira", "-platform", "offscreen"]
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert main.qt_arguments(["kira"]) == ["kira"]
    monkeypatch.setattr(main.sys, "platform", "darwin")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    assert main.qt_arguments(["kira"]) == ["kira"]
