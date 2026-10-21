# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import hashlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from PyQt6.QtCore import QObject, pyqtSignal

from kira.ollama_advice import ELSEWHERE, PORT, REMOTE, WINDOWS, Advice
from kira.ui import ollama_advice_dialog as dlg_mod
from kira.ui.ollama_advice_dialog import OllamaAdviceDialog

DATA = b"setup"
SHA = hashlib.sha256(DATA).hexdigest()


def _ollama(where=WINDOWS):
    return Advice("ollama", "0.35.0", "0.40.5", url="https://example.invalid/OllamaSetup.exe",
                  sha256=SHA, size=len(DATA), where=where)


def _model():
    return Advice("model", "aa" * 32, "bb" * 32, model="gemma4:26b-a4b-it-qat")


@pytest.fixture
def quiet(monkeypatch):
    shown = []
    monkeypatch.setattr(dlg_mod, "light_information", lambda parent, title, text: shown.append(text))
    monkeypatch.setattr(dlg_mod, "light_critical", lambda parent, title, text: shown.append(text))
    monkeypatch.setattr(OllamaAdviceDialog, "_confirm", lambda self, text, detail: True)
    return shown


def test_local_ollama_and_model_get_update_buttons(qtbot):
    d = OllamaAdviceDialog([_ollama(), _model()], on_declined=lambda key: None, app_version="0.5.5")
    qtbot.addWidget(d)
    assert set(d.buttons) == {"ollama", "model", "decline"}


@pytest.mark.parametrize("where,text", [
    (REMOTE, "anderen Rechner"), (PORT, "WSL"), (ELSEWHERE, "Standardordner"),
])
def test_ollama_outside_the_windows_install_only_gets_a_note(qtbot, where, text):
    from PyQt6.QtWidgets import QLabel
    d = OllamaAdviceDialog([_ollama(where)], on_declined=lambda key: None)
    qtbot.addWidget(d)
    assert "ollama" not in d.buttons
    assert any(text in label.text() for label in d.findChildren(QLabel))


def test_decline_remembers_every_shown_advice(qtbot):
    keys = []
    d = OllamaAdviceDialog([_ollama(), _model()], on_declined=keys.append)
    qtbot.addWidget(d)
    d.buttons["decline"].click()
    assert keys == ["ollama||0.40.5", f"model|gemma4:26b-a4b-it-qat|{'bb' * 32}"]
    assert d.result() == d.DialogCode.Accepted


@pytest.mark.parametrize("stdout,ok", [
    ("Valid\nCN=Ollama Inc., O=Ollama Inc., L=Toronto\n", True),
    ("NotSigned\n\n", False),
    ("Valid\nCN=Jemand Anders\n", False),
    ("Valid\nCN=Ollama Inc.X, O=Ollama Inc.X\n", False),
    ("Valid\nCN=Ollama Inc., O=Andere GmbH\n", False),
    ("", False),
])
def test_signature_needs_valid_status_and_exactly_ollama_as_signer(tmp_path, stdout, ok):
    calls = []

    def run(cmd, **kw):
        calls.append((cmd, kw))
        return SimpleNamespace(stdout=stdout, returncode=0)

    path = tmp_path / "D’Angelo O'Setup.exe"
    assert dlg_mod.signature_ok(path, run=run) is ok
    cmd, kw = calls[0]
    assert cmd[0].lower().endswith("\\system32\\windowspowershell\\v1.0\\powershell.exe")
    assert str(path) not in cmd[-1]
    assert kw["env"]["S2A_PRUEFDATEI"] == str(path)


def test_signature_check_failure_counts_as_invalid(tmp_path):
    def run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)
    assert dlg_mod.signature_ok(tmp_path / "x.exe", run=run) is False


def test_stop_ollama_ends_only_the_windows_ollama(tmp_path):
    folder = tmp_path / "Programs" / "Ollama"

    class _Proc:
        def __init__(self, name, exe):
            self.info = {"name": name, "exe": str(exe)}
            self.done = []

        def terminate(self):
            self.done.append("terminate")

        def wait(self, timeout):
            self.done.append("wait")

        def kill(self):
            self.done.append("kill")

    procs = [_Proc("ollama app.exe", folder / "ollama app.exe"), _Proc("ollama.exe", folder / "ollama.exe"),
             _Proc("llama-server.exe", folder / "lib" / "ollama" / "llama-server.exe"),
             _Proc("pythonw.exe", folder / "pythonw.exe"), _Proc("ollama.exe", tmp_path / "anderes" / "ollama.exe"),
             _Proc("ollama.exe", "")]
    assert dlg_mod.stop_ollama(folder, procs) == 3
    assert procs[0].done == ["terminate", "wait"]
    assert procs[2].done == ["terminate", "wait"]
    assert procs[3].done == [] and procs[4].done == [] and procs[5].done == []
    assert dlg_mod.stop_ollama(None, procs) == 0


def test_watch_setup_restarts_ollama_only_when_it_stayed_off(tmp_path):
    class _Setup:
        def wait(self):
            return 0

    restarted = []
    dlg_mod.watch_setup(_Setup(), tmp_path, running=lambda folder: False, restart=restarted.append,
                        settle_s=0).join(2)
    assert restarted == [tmp_path]
    dlg_mod.watch_setup(_Setup(), tmp_path, running=lambda folder: True, restart=restarted.append,
                        settle_s=0).join(2)
    assert restarted == [tmp_path]


def test_closing_during_a_running_check_keeps_the_thread_alive(qtbot, tmp_path, monkeypatch, quiet):
    import threading
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    gate = threading.Event()
    bundled = tmp_path / "OllamaSetup.exe"
    bundled.write_bytes(DATA)
    monkeypatch.setattr(dlg_mod, "bundled_setup", lambda: bundled)
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: gate.wait(5) or True)
    touched = []
    monkeypatch.setattr(dlg_mod, "stop_ollama", lambda folder: touched.append("stop"))
    d = OllamaAdviceDialog([_ollama()], on_declined=lambda k: None)
    qtbot.addWidget(d)
    d.buttons["ollama"].click()
    thread = d._thread
    d.reject()
    assert d._thread is None
    assert any(t is thread for t, _w in dlg_mod._orphans)
    d.close()
    assert sum(1 for t, _w in dlg_mod._orphans if t is thread) == 1
    gate.set()
    qtbot.waitUntil(lambda: not thread.isRunning(), timeout=5000)
    assert touched == []


def _fake_download(data=DATA):
    def download(url, target, on_bytes=None):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if on_bytes:
            on_bytes(len(data), len(data))
        return target
    return download


def _run_worker(advice, target):
    results = []
    worker = dlg_mod._SetupWorker(advice, target)
    worker.finished.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    return results[0]


def test_setup_worker_loads_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download())
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    target = tmp_path / "OllamaSetup.exe"
    assert _run_worker(_ollama(), target) == (True, str(target))


def test_setup_worker_rejects_wrong_checksum_and_deletes_it(tmp_path, monkeypatch):
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download(b"anders"))
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    target = tmp_path / "OllamaSetup.exe"
    ok, message = _run_worker(_ollama(), target)
    assert not ok and "Prüfsumme" in message
    assert not target.exists()


def test_setup_worker_rejects_invalid_signature(tmp_path, monkeypatch):
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download())
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: False)
    ok, message = _run_worker(_ollama(), tmp_path / "OllamaSetup.exe")
    assert not ok and "Signatur" in message


def test_setup_worker_reuses_a_verified_download(tmp_path, monkeypatch):
    target = tmp_path / "OllamaSetup.exe"
    target.write_bytes(DATA)
    monkeypatch.setattr(dlg_mod, "download_asset", lambda *a, **k: pytest.fail("kein zweiter Download"))
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    assert _run_worker(_ollama(), target)[0] is True


def test_update_button_stops_ollama_then_starts_the_setup(qtbot, tmp_path, monkeypatch, quiet):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(dlg_mod, "bundled_setup", lambda: None)
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download())
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    order = []
    monkeypatch.setattr(dlg_mod, "stop_ollama", lambda folder: order.append(("stop", folder)))
    monkeypatch.setattr(dlg_mod, "launch_setup", lambda path: order.append(("start", path)))
    declined, handled = [], []
    d = OllamaAdviceDialog([_ollama()], on_declined=declined.append, on_handled=handled.append)
    qtbot.addWidget(d)
    d.buttons["ollama"].click()
    qtbot.waitUntil(lambda: len(order) == 2, timeout=5000)
    assert order == [("stop", tmp_path / "Programs" / "Ollama"),
                     ("start", tmp_path / "Kira" / "update" / "ollama-0.40.5" / "OllamaSetup.exe")]
    assert handled == ["ollama||0.40.5"] and declined == []
    assert d.result() == d.DialogCode.Accepted


def test_cancel_stops_before_ollama_is_touched(qtbot, tmp_path, monkeypatch, quiet):
    import threading
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    gate = threading.Event()
    bundled = tmp_path / "OllamaSetup.exe"
    bundled.write_bytes(DATA)
    monkeypatch.setattr(dlg_mod, "bundled_setup", lambda: bundled)
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: gate.wait(5) or True)
    touched = []
    monkeypatch.setattr(dlg_mod, "stop_ollama", lambda folder: touched.append("stop"))
    monkeypatch.setattr(dlg_mod, "launch_setup", lambda path: touched.append("start"))
    d = OllamaAdviceDialog([_ollama()], on_declined=lambda k: None)
    qtbot.addWidget(d)
    d.buttons["ollama"].click()
    from PyQt6.QtWidgets import QProgressDialog
    progress = d.findChild(QProgressDialog)
    progress.canceled.emit()
    gate.set()
    qtbot.waitUntil(lambda: d._thread is not None and not d._thread.isRunning(), timeout=5000)
    qtbot.wait(100)
    assert touched == []


def test_failed_setup_start_brings_ollama_back(qtbot, tmp_path, monkeypatch, quiet):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(dlg_mod, "bundled_setup", lambda: None)
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download())
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    monkeypatch.setattr(dlg_mod, "stop_ollama", lambda folder: None)

    def broken(path):
        raise OSError("gesperrt")

    started = []
    monkeypatch.setattr(dlg_mod, "launch_setup", broken)
    monkeypatch.setattr(dlg_mod, "start_ollama_app", lambda folder: started.append(folder))
    d = OllamaAdviceDialog([_ollama()], on_declined=lambda k: None)
    qtbot.addWidget(d)
    d.buttons["ollama"].click()
    qtbot.waitUntil(lambda: bool(started), timeout=5000)
    assert started == [tmp_path / "Programs" / "Ollama"]
    assert any("gesperrt" in text for text in quiet)


class _FakePull(QObject):
    progress = pyqtSignal(str, 'qint64', 'qint64')
    finished = pyqtSignal(bool, str)
    models: list[str] = []

    def __init__(self, model):
        super().__init__()
        _FakePull.models.append(model)

    def cancel(self):
        pass

    def run(self):
        self.progress.emit("pulling", 5, 10)
        self.finished.emit(True, "ok")


class _SlowPull(QObject):
    progress = pyqtSignal(str, 'qint64', 'qint64')
    finished = pyqtSignal(bool, str)
    seen: list[bool] = []

    def __init__(self, model):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import time
        t0 = time.monotonic()
        while not self._cancelled and time.monotonic() - t0 < 3:
            time.sleep(0.02)
        _SlowPull.seen.append(self._cancelled)
        self.finished.emit(not self._cancelled, "Abgebrochen." if self._cancelled else "ok")


def test_cancel_reaches_a_running_model_pull(qtbot, monkeypatch, quiet):
    import kira.ui.settings_dialog as sd
    from PyQt6.QtWidgets import QProgressDialog
    monkeypatch.setattr(sd, "_PullWorker", _SlowPull)
    keys = []
    d = OllamaAdviceDialog([_model()], on_declined=keys.append)
    qtbot.addWidget(d)
    d.buttons["model"].click()
    d.findChild(QProgressDialog).canceled.emit()
    qtbot.waitUntil(lambda: bool(_SlowPull.seen), timeout=5000)
    assert _SlowPull.seen == [True]
    qtbot.wait(50)
    assert keys == []


def test_model_button_pulls_the_configured_model(qtbot, monkeypatch, quiet):
    import kira.ui.settings_dialog as sd
    monkeypatch.setattr(sd, "_PullWorker", _FakePull)
    keys = []
    d = OllamaAdviceDialog([_model()], on_declined=keys.append)
    qtbot.addWidget(d)
    d.buttons["model"].click()
    qtbot.waitUntil(lambda: bool(keys), timeout=5000)
    assert _FakePull.models == ["gemma4:26b-a4b-it-qat"]
    assert keys == [f"model|gemma4:26b-a4b-it-qat|{'bb' * 32}"]
    assert any("neu geladen" in text for text in quiet)


def test_setup_worker_prefers_the_setup_shipped_with_speech2anywhere(tmp_path, monkeypatch):
    bundled = tmp_path / "installer" / "embedded" / "OllamaSetup.exe"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(DATA)
    monkeypatch.setattr(dlg_mod, "download_asset", lambda *a, **k: pytest.fail("kein Download"))
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    results = []
    worker = dlg_mod._SetupWorker(_ollama(), tmp_path / "update" / "OllamaSetup.exe", bundled)
    worker.finished.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert results == [(True, str(bundled))]


def test_setup_worker_downloads_when_the_shipped_setup_is_another_version(tmp_path, monkeypatch):
    bundled = tmp_path / "OllamaSetup.exe"
    bundled.write_bytes(b"alt")
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download())
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    target = tmp_path / "update" / "OllamaSetup.exe"
    results = []
    worker = dlg_mod._SetupWorker(_ollama(), target, bundled)
    worker.finished.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    assert results == [(True, str(target))]
    assert bundled.read_bytes() == b"alt"


def test_bundled_setup_only_counts_for_a_managed_install(tmp_path, monkeypatch):
    import kira.app_update as app_update
    root = tmp_path / "Kira" / "python"
    shipped = tmp_path / "Kira" / "installer" / "embedded" / "OllamaSetup.exe"
    shipped.parent.mkdir(parents=True)
    shipped.write_bytes(DATA)
    monkeypatch.setattr(app_update, "install_root", lambda: root)
    assert dlg_mod.bundled_setup() == shipped
    monkeypatch.setattr(app_update, "install_root", lambda: None)
    assert dlg_mod.bundled_setup() is None


def test_setup_worker_names_the_check_after_the_download(tmp_path, monkeypatch):
    from kira import progress as prog
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download())
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: True)
    events = []
    worker = dlg_mod._SetupWorker(_ollama(), tmp_path / "OllamaSetup.exe")
    worker.phase.connect(lambda text: events.append(("phase", text)))
    worker.progress.connect(lambda done, total: events.append(("bytes", done, total)))
    worker.finished.connect(lambda ok, msg: events.append(("finished", ok)))
    worker.run()
    assert events == [
        ("phase", dlg_mod.CHECKING),
        ("phase", prog.STARTING),
        ("bytes", len(DATA), len(DATA)),
        ("phase", dlg_mod.CHECKING),
        ("finished", True),
    ]


def _record_labels(monkeypatch):
    from PyQt6.QtWidgets import QProgressDialog
    labels = []
    original = QProgressDialog.setLabelText

    def record(self, text):
        labels.append(text)
        original(self, text)

    monkeypatch.setattr(QProgressDialog, "setLabelText", record)
    return labels


def test_check_after_the_download_keeps_a_running_bar(qtbot, tmp_path, monkeypatch, quiet):
    import threading
    from PyQt6.QtWidgets import QProgressDialog
    from kira import progress as prog
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    gate = threading.Event()
    monkeypatch.setattr(dlg_mod, "bundled_setup", lambda: None)
    monkeypatch.setattr(dlg_mod, "download_asset", _fake_download())
    monkeypatch.setattr(dlg_mod, "signature_ok", lambda path: gate.wait(5) and False)
    labels = _record_labels(monkeypatch)
    d = OllamaAdviceDialog([_ollama()], on_declined=lambda k: None)
    qtbot.addWidget(d)
    d.buttons["ollama"].click()
    progress = d.findChild(QProgressDialog)
    head = "Ollama-Setup 0.40.5\n"
    qtbot.waitUntil(lambda: f"{head}{prog.FINISHING}" in labels and labels[-1] == f"{head}{dlg_mod.CHECKING}",
                    timeout=5000)
    assert progress.isVisible()
    assert (progress.minimum(), progress.maximum()) == (0, 0)
    gate.set()
    qtbot.waitUntil(lambda: d._thread is None or not d._thread.isRunning(), timeout=5000)


@pytest.mark.parametrize("checked", [0, 16_000_000_000])
def test_model_pull_label_speaks_german_and_runs_the_bar_while_checking(qtbot, monkeypatch, quiet, checked):
    import threading
    import kira.ui.settings_dialog as sd
    from PyQt6.QtWidgets import QProgressDialog
    gate = threading.Event()

    class _Pull(QObject):
        progress = pyqtSignal(str, 'qint64', 'qint64')
        finished = pyqtSignal(bool, str)

        def __init__(self, model):
            super().__init__()

        def cancel(self):
            gate.set()

        def run(self):
            self.progress.emit("pulling 2dd70431afed", 4_000_000_000, 16_000_000_000)
            self.progress.emit("verifying sha256 digest", checked, checked)
            gate.wait(5)
            self.finished.emit(False, "Abgebrochen.")

    monkeypatch.setattr(sd, "_PullWorker", _Pull)
    labels = _record_labels(monkeypatch)
    d = OllamaAdviceDialog([_model()], on_declined=lambda k: None)
    qtbot.addWidget(d)
    d.buttons["model"].click()
    progress = d.findChild(QProgressDialog)
    head = "Lade gemma4:26b-a4b-it-qat\n"
    qtbot.waitUntil(lambda: labels[-1:] == [f"{head}Prüfsumme wird geprüft …"], timeout=5000)
    assert f"{head}4,0 von 16,0 GB · 25 % · startet …" in labels
    assert progress.isVisible()
    assert (progress.minimum(), progress.maximum()) == (0, 0)
    progress.canceled.emit()
    qtbot.waitUntil(lambda: d._thread is None or not d._thread.isRunning(), timeout=5000)
