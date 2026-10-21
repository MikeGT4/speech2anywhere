from __future__ import annotations
import sys
import threading
import types
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)


@pytest.fixture(autouse=True)
def _no_live_services(monkeypatch):
    reached = []

    def refuse(*args, **kwargs):
        reached.append(args)
        raise AssertionError("Test erreicht einen echten Dienst")

    monkeypatch.setattr("kira.ollama_pull.connect", refuse)
    monkeypatch.setattr("kira.ollama_pull.registry_size", refuse)
    yield
    assert reached == [], "Test erreicht einen echten Dienst"


class _FakeClient:
    def __init__(self, events=(), error=None, hold=False):
        self.events = list(events)
        self.error = error
        self.hold = hold
        self.shut = threading.Event()

    def pull(self, model, stream=False):
        if self.error is not None:
            raise self.error
        return self._stream()

    def _stream(self):
        yield from self.events
        if self.hold and self.shut.wait(3):
            raise ConnectionError("Verbindung vom Client geschlossen")

    def close(self):
        self.shut.set()


def _install_fake_ollama(monkeypatch, events=(), error=None, hold=False, size=0):
    client = _FakeClient(events, error, hold)
    monkeypatch.setattr("kira.ollama_pull.connect", lambda: client)
    monkeypatch.setattr("kira.ollama_pull.registry_size", lambda model, timeout=None: size)
    return client


def test_resolve_edit_combo_disabled_returns_none():
    from kira.ui.settings_dialog import SettingsDialog
    assert SettingsDialog._resolve_edit_combo(False, "f9") is None
    assert SettingsDialog._resolve_edit_combo(False, "") is None


def test_resolve_edit_combo_enabled_returns_field_value():
    from kira.ui.settings_dialog import SettingsDialog
    assert SettingsDialog._resolve_edit_combo(True, "f9") == "f9"


def test_resolve_edit_combo_enabled_with_blank_field_returns_none():
    from kira.ui.settings_dialog import SettingsDialog
    assert SettingsDialog._resolve_edit_combo(True, "") is None
    assert SettingsDialog._resolve_edit_combo(True, "   ") is None


def test_resolve_edit_combo_strips_surrounding_whitespace():
    from kira.ui.settings_dialog import SettingsDialog
    assert SettingsDialog._resolve_edit_combo(True, "  f9  ") == "f9"


def test_uncensored_model_constant_is_verified_ollama_name():
    from kira.ui.settings_dialog import _UNCENSORED_MODEL
    assert _UNCENSORED_MODEL == "huihui_ai/Qwen3.6-abliterated:27b"


def test_uncensored_gpu_blocks_warns_on_tight_and_insufficient():
    from kira.ui.settings_dialog import SettingsDialog
    assert SettingsDialog._uncensored_gpu_blocks("insufficient") is True
    assert SettingsDialog._uncensored_gpu_blocks("tight") is True


def test_uncensored_gpu_blocks_passes_on_ok_and_no_gpu():
    from kira.ui.settings_dialog import SettingsDialog
    assert SettingsDialog._uncensored_gpu_blocks("ok") is False
    assert SettingsDialog._uncensored_gpu_blocks("no_gpu") is False


def test_uncensored_model_gpu_estimate_is_27b_class():
    from kira.gpu_check import estimate_polish_vram
    from kira.ui.settings_dialog import _UNCENSORED_MODEL
    assert estimate_polish_vram(_UNCENSORED_MODEL) >= 15.0


def test_pull_worker_starts_with_cancelled_flag_false(qtbot):
    from kira.ui.settings_dialog import _PullWorker
    w = _PullWorker("any-model")
    assert w._cancelled is False


def test_pull_worker_cancel_sets_flag_true(qtbot):
    from kira.ui.settings_dialog import _PullWorker
    w = _PullWorker("any-model")
    w.cancel()
    assert w._cancelled is True


def test_pull_worker_loop_aborts_when_cancel_called_between_yields(
    qtbot, monkeypatch,
):
    from kira.ui.settings_dialog import _PullWorker

    events = [
        {"status": "pulling manifest", "completed": 0, "total": 0},
        {"status": "downloading", "completed": 1_000_000, "total": 17_000_000_000},
        {"status": "downloading", "completed": 5_000_000, "total": 17_000_000_000},
    ]
    _install_fake_ollama(monkeypatch, events)

    w = _PullWorker("any")
    progress_calls: list = []
    finished_calls: list = []

    def on_progress(status, completed, total):
        progress_calls.append((status, completed, total))
        if len(progress_calls) == 1:
            w.cancel()

    w.progress.connect(on_progress)
    w.finished.connect(lambda ok, msg: finished_calls.append((ok, msg)))
    w.run()

    assert len(progress_calls) == 1
    assert finished_calls == [(False, "Abgebrochen.")]


def test_pull_worker_emits_large_byte_counts_without_int32_overflow(
    qtbot, monkeypatch,
):
    from kira.ui.settings_dialog import _PullWorker

    big_completed = 5 * 1024 ** 3
    big_total = 17 * 1024 ** 3 + 432
    assert big_completed > 2**31, "Test-Setup-Bug: Wert ist nicht overflow-gross"
    assert big_total > 2**31

    events = [{
        "status": "downloading",
        "completed": big_completed,
        "total": big_total,
    }]
    _install_fake_ollama(monkeypatch, events)

    seen: list = []
    w = _PullWorker("any")
    w.progress.connect(lambda s, c, t: seen.append((s, c, t)))
    w.finished.connect(lambda *a: None)
    w.run()

    assert len(seen) == 1
    status, completed, total = seen[0]
    assert status == "downloading"
    assert completed == big_completed
    assert total == big_total
    assert completed > 0
    assert total > 0


def test_pull_worker_finished_true_on_clean_stream(qtbot, monkeypatch):
    from kira.ui.settings_dialog import _PullWorker

    events = [
        {"status": "pulling manifest"},
        {"status": "downloading", "completed": 100, "total": 1000},
        {"status": "verifying sha256 digest"},
        {"status": "writing manifest"},
        {"status": "success"},
    ]
    _install_fake_ollama(monkeypatch, events)

    finished_calls: list = []
    w = _PullWorker("my-model")
    w.progress.connect(lambda *a: None)
    w.finished.connect(lambda ok, msg: finished_calls.append((ok, msg)))
    w.run()

    assert len(finished_calls) == 1
    ok, msg = finished_calls[0]
    assert ok is True
    assert "my-model" in msg


def test_pull_worker_finished_false_when_ollama_raises(qtbot, monkeypatch):
    from kira.ui.settings_dialog import _PullWorker

    _install_fake_ollama(monkeypatch, error=ConnectionError("Ollama-Server nicht erreichbar"))

    finished_calls: list = []
    w = _PullWorker("foo")
    w.progress.connect(lambda *a: None)
    w.finished.connect(lambda ok, msg: finished_calls.append((ok, msg)))
    w.run()

    assert len(finished_calls) == 1
    ok, msg = finished_calls[0]
    assert ok is False
    assert "Modell-Update hat nicht geklappt" in msg


def test_pull_worker_parses_pydantic_style_events(qtbot, monkeypatch):
    from kira.ui.settings_dialog import _PullWorker

    class FakeEvent:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    events = [FakeEvent(
        status="downloading",
        completed=2_000_000_000,
        total=5_000_000_000,
    )]
    _install_fake_ollama(monkeypatch, events)

    seen: list = []
    w = _PullWorker("any")
    w.progress.connect(lambda s, c, t: seen.append((s, c, t)))
    w.finished.connect(lambda *a: None)
    w.run()

    assert seen == [("downloading", 2_000_000_000, 5_000_000_000)]


def test_pull_worker_does_not_emit_progress_after_cancel(qtbot, monkeypatch):
    from kira.ui.settings_dialog import _PullWorker

    events = [
        {"status": "a", "completed": 100, "total": 1000},
        {"status": "b", "completed": 200, "total": 1000},
        {"status": "c", "completed": 300, "total": 1000},
        {"status": "d", "completed": 400, "total": 1000},
    ]
    _install_fake_ollama(monkeypatch, events)

    w = _PullWorker("any")
    progress_calls: list = []

    def on_progress(*a):
        progress_calls.append(a)
        w.cancel()

    w.progress.connect(on_progress)
    w.finished.connect(lambda *a: None)
    w.run()

    assert len(progress_calls) == 1, progress_calls


def test_ollama_client_helper_returns_module_without_bind_all_host(monkeypatch):
    fake = types.ModuleType("ollama")
    monkeypatch.setitem(sys.modules, "ollama", fake)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    from kira.ui.settings_dialog import _ollama_client
    assert _ollama_client() is fake


def test_ollama_client_helper_builds_loopback_client_for_bind_all_host(monkeypatch):
    fake = types.ModuleType("ollama")

    class FakeClient:
        def __init__(self, host=None):
            self.host = host

    fake.Client = FakeClient
    monkeypatch.setitem(sys.modules, "ollama", fake)
    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    from kira.ui.settings_dialog import _ollama_client
    assert _ollama_client().host == "http://127.0.0.1:11434"


def test_pull_worker_sums_the_layers_and_passes_phases_on(qtbot, monkeypatch):
    from kira.ui.settings_dialog import _PullWorker

    events = [
        {"status": "pulling manifest"},
        {"status": "pulling aaa", "digest": "sha256:aaa", "completed": 10_000_000_000, "total": 16_000_000_000},
        {"status": "pulling bbb", "digest": "sha256:bbb", "completed": 0, "total": 2_000_000_000},
        {"status": "verifying sha256 digest"},
        {"status": "success"},
    ]
    _install_fake_ollama(monkeypatch, events)
    seen: list = []
    w = _PullWorker("any")
    w.progress.connect(lambda s, c, t: seen.append((s, c, t)))
    w.finished.connect(lambda *a: None)
    w.run()

    assert seen == [
        ("pulling manifest", 0, 0),
        ("pulling aaa", 10_000_000_000, 16_000_000_000),
        ("pulling bbb", 10_000_000_000, 18_000_000_000),
        ("verifying sha256 digest", 18_000_000_000, 18_000_000_000),
        ("success", 18_000_000_000, 18_000_000_000),
    ]


def test_pull_worker_thins_out_repeated_byte_events(qtbot, monkeypatch):
    from kira.ui.settings_dialog import _PullWorker

    events = [
        {"status": "pulling aaa", "digest": "sha256:aaa", "completed": n, "total": 1000}
        for n in range(0, 1001, 10)
    ]
    _install_fake_ollama(monkeypatch, events)
    seen: list = []
    w = _PullWorker("any")
    w.progress.connect(lambda s, c, t: seen.append((c, t)))
    w.finished.connect(lambda *a: None)
    w.run()

    assert seen[0] == (0, 1000)
    assert seen[-1] == (1000, 1000)
    assert len(seen) < 10


def test_pull_worker_fails_when_the_stream_ends_without_success(qtbot, monkeypatch):
    from kira import ollama_pull
    from kira.ui.settings_dialog import _PullWorker

    _install_fake_ollama(monkeypatch, [
        {"status": "pulling aaa", "digest": "sha256:aaa", "completed": 400, "total": 1000},
    ])
    finished_calls: list = []
    w = _PullWorker("gemma4:e4b")
    w.finished.connect(lambda ok, msg: finished_calls.append((ok, msg)))
    w.run()

    assert finished_calls == [(False, f"Das Modell-Update hat nicht geklappt: {ollama_pull.INCOMPLETE}")]


def test_pull_worker_names_an_unknown_model_in_german(qtbot, monkeypatch):
    from ollama import ResponseError
    from kira.ui.settings_dialog import _PullWorker

    _install_fake_ollama(monkeypatch, error=ResponseError("pull model manifest: file does not exist"))
    finished_calls: list = []
    w = _PullWorker("gemma4:13b")
    w.finished.connect(lambda ok, msg: finished_calls.append((ok, msg)))
    w.run()

    assert finished_calls == [(False, "Modell gemma4:13b gibt es bei Ollama nicht.")]


def test_pull_worker_counts_the_size_from_the_library_from_the_start(qtbot, monkeypatch):
    from kira.ui.settings_dialog import _PullWorker

    _install_fake_ollama(monkeypatch, [
        {"status": "pulling proj", "digest": "sha256:proj", "completed": 0, "total": 175_115_616},
        {"status": "success"},
    ], size=8_021_618_941)
    seen: list = []
    w = _PullWorker("gemma4:12b")
    w.progress.connect(lambda s, c, t: seen.append((s, c, t)))
    w.finished.connect(lambda *a: None)
    w.run()

    assert seen[0] == ("pulling proj", 0, 8_021_618_941)


def test_pull_worker_cancel_closes_a_silent_stream(qtbot, monkeypatch):
    from PyQt6.QtCore import Qt, QThread
    from kira.ui.settings_dialog import _PullWorker

    client = _install_fake_ollama(monkeypatch, [{"status": "pulling manifest"}], hold=True)
    thread = QThread()
    w = _PullWorker("gemma4:12b")
    w.moveToThread(thread)
    thread.started.connect(w.run)
    finished_calls: list = []
    w.finished.connect(lambda ok, msg: finished_calls.append((ok, msg)))
    w.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
    try:
        with qtbot.waitSignal(w.progress, timeout=3000):
            thread.start()

        w.cancel()

        assert thread.wait(1000)
        assert client.shut.is_set()
        qtbot.waitUntil(lambda: bool(finished_calls), timeout=1000)
        assert finished_calls == [(False, "Abgebrochen.")]
    finally:
        client.close()
        thread.wait(5000)
