# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)

from kira.ui import _update_runner as runner


@pytest.fixture(autouse=True)
def _reset_flag(monkeypatch):
    monkeypatch.setattr(runner, "_flow_active", False)
    infos: list[str] = []
    monkeypatch.setattr(runner, "light_information", lambda parent, title, text: infos.append(text))
    return infos


def test_second_start_during_a_running_flow_is_refused(monkeypatch, _reset_flag):
    calls: list[str] = []

    def flow(parent, on_quit):
        calls.append("flow")
        runner.run_update_flow(None)
        return False

    monkeypatch.setattr(runner, "_run_update_flow", flow)
    runner.run_update_flow(None)
    assert calls == ["flow"]
    assert _reset_flag == ["Ein Update läuft bereits."]
    assert runner._flow_active is False


def test_flag_stays_set_while_the_download_runs(monkeypatch, _reset_flag):
    monkeypatch.setattr(runner, "_run_update_flow", lambda parent, on_quit: True)
    runner.run_update_flow(None)
    assert runner._flow_active is True
    runner.run_update_flow(None)
    assert _reset_flag == ["Ein Update läuft bereits."]
    runner._flow_finished()
    assert runner._flow_active is False


def test_flag_is_released_when_the_flow_raises(monkeypatch):
    def boom(parent, on_quit):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(runner, "_run_update_flow", boom)
    with pytest.raises(RuntimeError):
        runner.run_update_flow(None)
    assert runner._flow_active is False


def test_failed_download_releases_the_flag(monkeypatch, qapp, tmp_path):
    import time

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QMessageBox

    from kira.updater import ReleaseAsset, UpdateCheckResult

    result = UpdateCheckResult(
        status="newer", remote_version="9.9.9",
        bundle_assets=[ReleaseAsset(name="Kira-Setup-v9.9.9.exe", url="https://example.invalid/s", size=1)],
    )
    monkeypatch.setattr(runner, "check_for_update", lambda **kw: result)
    monkeypatch.setattr(runner, "_bundle_dir", lambda: tmp_path)

    class _YesBox(QMessageBox):
        pass

    setattr(_YesBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(runner, "QMessageBox", _YesBox)

    def no_network(*args, **kwargs):
        raise OSError("Netz weg")

    monkeypatch.setattr(runner, "download_bundle", no_network)
    critical: list[str] = []
    monkeypatch.setattr(runner, "light_critical", lambda parent, title, text: critical.append(text))

    runner.run_update_flow(None)
    assert runner._flow_active is True
    deadline = time.monotonic() + 5
    while runner._flow_active and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert runner._flow_active is False
    assert critical and "Netz weg" in critical[0]


def test_real_early_return_releases_the_flag(monkeypatch, qapp, _reset_flag):
    from kira.updater import UpdateCheckResult

    monkeypatch.setattr(runner, "check_for_update",
                        lambda **kw: UpdateCheckResult(status="current", remote_version="0.4.1"))
    runner.run_update_flow(None)
    assert runner._flow_active is False
    assert any("aktuell" in text for text in _reset_flag)


def test_cancel_button_stops_the_download_and_releases_the_flag(monkeypatch, qapp, tmp_path):
    import time

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QMessageBox

    import kira.updater as updater
    from kira.updater import ReleaseAsset, UpdateCheckResult

    class _Endless:
        headers = {"Content-Length": str(3 * 1024**3)}
        reads = 0

        def read(self, n):
            self.reads += 1
            if self.reads > 1500:
                return b""
            time.sleep(0.002)
            return b"x" * min(n, 4096)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    result = UpdateCheckResult(
        status="newer", remote_version="9.9.9",
        bundle_assets=[ReleaseAsset(name="Kira-Setup-v9.9.9.exe", url="https://example.invalid/s", size=1)],
    )
    monkeypatch.setattr(runner, "check_for_update", lambda **kw: result)
    monkeypatch.setattr(runner, "_bundle_dir", lambda: tmp_path)
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda url, timeout, context=None: _Endless())

    class _YesBox(QMessageBox):
        pass

    setattr(_YesBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(runner, "QMessageBox", _YesBox)
    critical: list[str] = []
    monkeypatch.setattr(runner, "light_critical", lambda parent, title, text: critical.append(text))

    runner.run_update_flow(None)
    assert runner._flow_active is True
    thread, _worker, progress = runner._anchor
    time.sleep(0.05)
    progress.canceled.emit()
    deadline = time.monotonic() + 10
    while runner._flow_active and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert runner._flow_active is False
    assert runner._anchor is None
    assert critical == ["Abgebrochen."]
    assert thread.isFinished()


def _newer_flow(monkeypatch, tmp_path, *, sums_url=None):
    from PyQt6.QtWidgets import QMessageBox

    from kira.updater import ReleaseAsset, UpdateCheckResult

    result = UpdateCheckResult(
        status="newer", remote_version="9.9.9",
        bundle_assets=[ReleaseAsset(name="Kira-Setup-v9.9.9.exe", url="https://example.invalid/s", size=1)],
        sha256sums_url=sums_url,
    )
    monkeypatch.setattr(runner, "check_for_update", lambda **kw: result)
    monkeypatch.setattr(runner, "_bundle_dir", lambda: tmp_path)
    boxes: list[str] = []

    class _YesBox(QMessageBox):
        def setWindowTitle(self, title):
            boxes.append(title)
            super().setWindowTitle(title)

    setattr(_YesBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(runner, "QMessageBox", _YesBox)
    launched: list[str] = []
    monkeypatch.setattr(runner, "_launch_setup_detached", launched.append)
    critical: list[str] = []
    monkeypatch.setattr(runner, "light_critical", lambda parent, title, text: critical.append(text))
    return boxes, launched, critical


def _wait_until_released(seconds=10.0):
    import time

    from PyQt6.QtCore import QCoreApplication

    deadline = time.monotonic() + seconds
    while runner._flow_active and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)


def test_cancel_while_the_network_hangs_says_cancelled(monkeypatch, qapp, tmp_path):
    import time

    import kira.updater as updater

    boxes, launched, critical = _newer_flow(monkeypatch, tmp_path)

    class _Hanging:
        headers = {"Content-Length": "100000"}
        reads = 0

        def read(self, n):
            self.reads += 1
            if self.reads > 3:
                time.sleep(0.5)
                raise TimeoutError("The read operation timed out")
            return b"x" * 4096

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda url, timeout, context=None: _Hanging())
    runner.run_update_flow(None)
    _thread, _worker, progress = runner._anchor
    time.sleep(0.1)
    progress.canceled.emit()
    _wait_until_released()
    assert runner._flow_active is False
    assert critical == ["Abgebrochen."]
    assert launched == []


def test_cancel_after_the_worker_finished_shows_no_ready_dialog(monkeypatch, qapp, tmp_path):
    import io

    import kira.updater as updater

    boxes, launched, critical = _newer_flow(monkeypatch, tmp_path)

    class _Tiny(io.BytesIO):
        headers = {"Content-Length": "1"}

    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda url, timeout, context=None: _Tiny(b"x"))
    import time

    runner.run_update_flow(None)
    _thread, _worker, progress = runner._anchor
    time.sleep(0.5)
    progress.canceled.emit()
    _wait_until_released()
    assert runner._flow_active is False
    assert "Kira - Update bereit" not in boxes
    assert launched == []
    assert critical == ["Abgebrochen."]


def _patch_setup(monkeypatch, tmp_path, check, answer):
    from PyQt6.QtWidgets import QMessageBox

    from kira import app_update
    from kira.updater import ReleaseAsset, UpdateCheckResult

    result = UpdateCheckResult(
        status="newer", remote_version="9.9.9",
        bundle_assets=[ReleaseAsset(name="Kira-Setup-v9.9.9.exe", url="https://example.invalid/s", size=3 * 1024**3)],
        app_asset=ReleaseAsset(name="kira-9.9.9-py3-none-any.whl", url="https://example.invalid/w",
                               size=1_450_342, sha256="ab" * 32),
    )
    monkeypatch.setattr(runner, "check_for_update", lambda **kw: result)
    monkeypatch.setattr(runner, "_bundle_dir", lambda: tmp_path)
    monkeypatch.setattr(app_update, "install_root", lambda: tmp_path / "python")
    calls = {"check": [], "launch": [], "texts": []}

    def fake_check(asset, target, root):
        calls["check"].append((asset.name, target, root))
        return check

    monkeypatch.setattr(app_update, "check_patch", fake_check)
    monkeypatch.setattr(app_update, "launch_patch",
                        lambda wheel, version, sha256, root: calls["launch"].append((wheel, version, root, sha256)))

    class _Box(QMessageBox):
        pass

    def exec_(self):
        calls["texts"].append(self.text() + "\n" + self.informativeText())
        return answer

    setattr(_Box, "exec", exec_)
    monkeypatch.setattr(runner, "QMessageBox", _Box)
    return calls


def test_small_program_update_is_offered_and_handed_to_the_helper(monkeypatch, qapp, tmp_path, _reset_flag):
    from PyQt6.QtWidgets import QMessageBox

    from kira.app_update import PatchCheck

    wheel = tmp_path / "v9.9.9" / "kira-9.9.9-py3-none-any.whl"
    calls = _patch_setup(monkeypatch, tmp_path, PatchCheck(wheel, []), QMessageBox.StandardButton.Yes)
    quits = []
    runner.run_update_flow(None, on_quit_request=lambda: quits.append(True))
    assert calls["check"] == [("kira-9.9.9-py3-none-any.whl", tmp_path / "v9.9.9", tmp_path / "python")]
    assert calls["launch"] == [(wheel, "9.9.9", tmp_path / "python", "ab" * 32)]
    assert quits == [True]
    assert len(calls["texts"]) == 1
    assert "Programm-Update: 1,4 MB" in calls["texts"][0]
    assert runner._flow_active is True
    runner._flow_finished()


def test_declined_program_update_downloads_nothing_else(monkeypatch, qapp, tmp_path, _reset_flag):
    from PyQt6.QtWidgets import QMessageBox

    from kira.app_update import PatchCheck

    calls = _patch_setup(monkeypatch, tmp_path, PatchCheck(tmp_path / "w.whl", []), QMessageBox.StandardButton.No)
    runner.run_update_flow(None, on_quit_request=lambda: None)
    assert calls["launch"] == []
    assert len(calls["texts"]) == 1
    assert runner._flow_active is False


def test_full_package_names_why_the_small_update_is_not_enough(monkeypatch, qapp, tmp_path, _reset_flag):
    from PyQt6.QtWidgets import QMessageBox

    from kira.app_update import PatchCheck

    calls = _patch_setup(monkeypatch, tmp_path, PatchCheck(tmp_path / "w.whl", ["numpy 2.3.0 wird zu 2.4.4."]),
                         QMessageBox.StandardButton.No)
    runner.run_update_flow(None, on_quit_request=lambda: None)
    assert calls["launch"] == []
    assert len(calls["texts"]) == 1
    assert "reicht diesmal nicht: numpy 2.3.0 wird zu 2.4.4." in calls["texts"][0]
    assert "Bundle: 1 Dateien" in calls["texts"][0]
    assert runner._flow_active is False


def test_developer_install_goes_straight_to_the_full_package(monkeypatch, qapp, tmp_path, _reset_flag):
    from PyQt6.QtWidgets import QMessageBox

    from kira import app_update
    from kira.app_update import PatchCheck

    calls = _patch_setup(monkeypatch, tmp_path, PatchCheck(tmp_path / "w.whl", []), QMessageBox.StandardButton.No)
    monkeypatch.setattr(app_update, "install_root", lambda: None)
    runner.run_update_flow(None, on_quit_request=lambda: None)
    assert calls["check"] == []
    assert "Bundle:" in calls["texts"][0]


def test_successful_full_update_starts_the_setup(monkeypatch, qapp, tmp_path, _reset_flag):
    import time

    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QMessageBox

    from kira import app_update
    from kira.updater import ReleaseAsset, UpdateCheckResult

    result = UpdateCheckResult(
        status="newer", remote_version="9.9.9",
        bundle_assets=[ReleaseAsset(name="Kira-Setup-v9.9.9.exe", url="https://example.invalid/s", size=1)],
    )
    monkeypatch.setattr(runner, "check_for_update", lambda **kw: result)
    monkeypatch.setattr(runner, "_bundle_dir", lambda: tmp_path)
    monkeypatch.setattr(app_update, "install_root", lambda: None)

    def fake_bundle(assets, target_dir, on_progress=None):
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / assets[0].name
        path.write_bytes(b"setup")
        return [path]

    monkeypatch.setattr(runner, "download_bundle", fake_bundle)

    class _YesBox(QMessageBox):
        pass

    setattr(_YesBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(runner, "QMessageBox", _YesBox)
    launched, critical, quits = [], [], []
    monkeypatch.setattr(runner, "_launch_setup_detached", launched.append)
    monkeypatch.setattr(runner, "light_critical", lambda parent, title, text: critical.append(text))

    runner.run_update_flow(None, on_quit_request=lambda: quits.append(True))
    deadline = time.monotonic() + 5
    while runner._flow_active and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert critical == []
    assert launched == [str(tmp_path / "v9.9.9" / "Kira-Setup-v9.9.9.exe")]
    assert quits == [True]


def test_cancelling_the_package_check_stops_the_update(monkeypatch, qapp, tmp_path, _reset_flag):
    import threading

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMessageBox, QProgressDialog

    from kira.app_update import PatchCheck

    gate = threading.Event()
    calls = _patch_setup(monkeypatch, tmp_path, PatchCheck(tmp_path / "w.whl", []), QMessageBox.StandardButton.Yes)
    from kira import app_update
    original = app_update.check_patch
    seen_threads = []

    def slow(asset, target, root):
        seen_threads.append(threading.current_thread().name)
        gate.wait(5)
        return original(asset, target, root)

    monkeypatch.setattr(app_update, "check_patch", slow)

    def press_cancel():
        for widget in qapp.topLevelWidgets():
            if isinstance(widget, QProgressDialog) and widget.isVisible():
                widget.cancel()

    QTimer.singleShot(200, press_cancel)
    runner.run_update_flow(None, on_quit_request=lambda: None)
    gate.set()
    assert seen_threads == ["kira-patch-check"]
    assert calls["launch"] == [] and calls["texts"] == []
    assert runner._flow_active is False


def test_a_crashing_package_check_falls_back_to_the_full_package(monkeypatch, qapp, tmp_path, _reset_flag):
    from PyQt6.QtWidgets import QMessageBox

    from kira import app_update
    from kira.app_update import PatchCheck

    calls = _patch_setup(monkeypatch, tmp_path, PatchCheck(tmp_path / "w.whl", []), QMessageBox.StandardButton.No)

    def boom(asset, target, root):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(app_update, "check_patch", boom)
    runner.run_update_flow(None, on_quit_request=lambda: None)
    assert calls["launch"] == []
    assert "Die Prüfung ist fehlgeschlagen (kaputt)" in calls["texts"][0]


def test_update_worker_sums_all_bundle_files(qapp):
    import time
    from pathlib import Path

    from kira.updater import ReleaseAsset, UpdateCheckResult

    sizes = [2_154_496, 2_145_386_496, 961_254_400]
    names = ["Kira-Setup-v9.9.9.exe", "Kira-Setup-v9.9.9-1.bin", "Kira-Setup-v9.9.9-2.bin"]
    result = UpdateCheckResult(
        status="newer", remote_version="9.9.9",
        bundle_assets=[ReleaseAsset(name=n, url="https://example.invalid/" + n, size=s) for n, s in zip(names, sizes)],
    )
    worker = runner._UpdateWorker(result, Path("unbenutzt"))
    seen = []
    worker.progress.connect(lambda done, total: seen.append((done, total)))
    total = sum(sizes)
    worker._on_bytes(names[0], sizes[0], sizes[0])
    worker._on_bytes(names[1], 1_000_000_000, sizes[1])
    time.sleep(0.25)
    worker._on_bytes(names[1], 1_500_000_000, sizes[1])
    worker._on_bytes(names[1], sizes[1], sizes[1])
    worker._on_bytes(names[2], sizes[2], sizes[2])
    assert seen[0] == (sizes[0], total)
    assert (sizes[0] + 1_500_000_000, total) in seen
    assert seen[-1] == (total, total)
    assert all(size == total for _, size in seen)


def test_update_window_shows_bytes_then_runs_the_bar_while_checking(monkeypatch, qapp, tmp_path):
    import threading
    import time

    from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal
    from PyQt6.QtWidgets import QProgressDialog

    from kira import progress as prog

    _boxes, _launched, critical = _newer_flow(monkeypatch, tmp_path)
    labels = []
    original = QProgressDialog.setLabelText

    def record(self, text):
        labels.append(text)
        original(self, text)

    monkeypatch.setattr(QProgressDialog, "setLabelText", record)
    gate = threading.Event()

    class _Worker(QObject):
        progress = pyqtSignal('qint64', 'qint64')
        phase = pyqtSignal(str)
        succeeded = pyqtSignal(str, bool)
        failed = pyqtSignal(str)

        def __init__(self, result, target_dir):
            super().__init__()
            self._cancelled = False

        def cancel(self):
            self._cancelled = True
            gate.set()

        def run(self):
            self.phase.emit(prog.STARTING)
            self.progress.emit(1_234_567_890, 3_109_000_000)
            self.progress.emit(3_109_000_000, 3_109_000_000)
            self.phase.emit(runner.CHECKING)
            gate.wait(5)
            self.failed.emit("Abgebrochen.")

    monkeypatch.setattr(runner, "_UpdateWorker", _Worker)
    runner.run_update_flow(None)
    _thread, _worker, progress = runner._anchor
    head = "Lade Update v9.9.9\n"
    deadline = time.monotonic() + 5
    while labels[-1:] != [f"{head}{runner.CHECKING}"] and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    assert labels[-1] == f"{head}{runner.CHECKING}"
    assert f"{head}1,2 von 3,1 GB · 39 % · startet …" in labels
    assert f"{head}{prog.FINISHING}" in labels
    assert progress.isVisible()
    assert (progress.minimum(), progress.maximum()) == (0, 0)
    gate.set()
    _wait_until_released()
    assert runner._flow_active is False
    assert critical == ["Abgebrochen."]
