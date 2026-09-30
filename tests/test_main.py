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
