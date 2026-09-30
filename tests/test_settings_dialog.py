from __future__ import annotations
import sys
import types
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests (PyQt6)", allow_module_level=True)


def _install_fake_ollama(monkeypatch, events):
    fake = types.ModuleType("ollama")
    fake.pull = lambda model, stream=False: iter(events)
    monkeypatch.setitem(sys.modules, "ollama", fake)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)


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


def test_progress_scale_keeps_oversize_total_in_int32_range():
    from kira.ui.settings_dialog import _progress_scale

    INT32_MAX = 2 ** 31 - 1
    completed = 5 * 1024 ** 3
    total = 17 * 1024 ** 3 + 432
    assert total > INT32_MAX, "Test-Setup: total muss overflow-gross sein"
    maximum, value = _progress_scale(completed, total)
    assert 0 < maximum <= INT32_MAX
    assert 0 <= value <= maximum
    assert abs(value / maximum - completed / total) < 0.01


def test_progress_scale_zero_total_is_indeterminate():
    from kira.ui.settings_dialog import _progress_scale

    assert _progress_scale(0, 0) == (0, 0)


def test_progress_scale_clamps_completed_over_total():
    from kira.ui.settings_dialog import _progress_scale

    maximum, value = _progress_scale(completed=200, total=100)
    assert value <= maximum


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

    fake = types.ModuleType("ollama")

    def boom(*args, **kwargs):
        raise ConnectionError("Ollama-Server nicht erreichbar")

    fake.pull = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ollama", fake)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

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
