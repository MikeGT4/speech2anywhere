# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
from pathlib import Path

from kira import restart


def _exe(folder: Path, name: str = "kira.exe") -> Path:
    path = folder / name
    path.write_bytes(b"")
    return path


def test_launcher_is_the_program_that_started_the_app(tmp_path):
    exe = _exe(tmp_path)
    assert restart.launcher(argv0=str(exe), executable=str(tmp_path / "other" / "pythonw.exe")) == exe


def test_launcher_falls_back_to_the_one_next_to_the_interpreter(tmp_path):
    exe = _exe(tmp_path)
    assert restart.launcher(argv0="-c", executable=str(tmp_path / "pythonw.exe")) == exe


def test_launcher_is_missing_when_the_app_was_started_another_way(tmp_path):
    other = _exe(tmp_path, "python.exe")
    assert restart.launcher(argv0=str(other), executable=str(other)) is None


def test_successor_starts_detached_and_knows_whom_to_wait_for(tmp_path):
    exe = _exe(tmp_path)
    calls = []
    assert restart.start_successor(popen=lambda cmd, **kw: calls.append((cmd, kw)), path=exe, pid=4711) is True
    (cmd, kw), = calls
    assert cmd == [str(exe)]
    assert kw["creationflags"] == restart.DETACHED
    assert kw["close_fds"] is True
    assert kw["env"][restart.WAIT_ENV] == "4711"


def test_successor_keeps_the_rest_of_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("S2A_PROBE", "bleibt")
    calls = []
    restart.start_successor(popen=lambda cmd, **kw: calls.append(kw), path=_exe(tmp_path), pid=1)
    assert calls[0]["env"]["S2A_PROBE"] == "bleibt"


def test_no_successor_without_a_launcher(monkeypatch):
    monkeypatch.setattr(restart, "launcher", lambda: None)
    calls = []
    assert restart.start_successor(popen=lambda *a, **kw: calls.append(a)) is False
    assert calls == []


def test_failed_start_is_reported_not_raised(tmp_path):
    def broken(*_args, **_kwargs):
        raise OSError("Zugriff verweigert")

    assert restart.start_successor(popen=broken, path=_exe(tmp_path), pid=1) is False


def test_restarted_instance_waits_for_the_old_one_and_forgets_the_hint():
    environ = {restart.WAIT_ENV: "4711", "ANDERES": "x"}
    waited = []
    done = restart.wait_for_predecessor(environ=environ, wait=lambda pid, timeout: waited.append((pid, timeout)) or True)
    assert done is True
    assert waited == [(4711, restart.WAIT_S)]
    assert environ == {"ANDERES": "x"}


def test_normal_start_does_not_wait():
    waited = []
    assert restart.wait_for_predecessor(environ={}, wait=lambda *a: waited.append(a) or True) is True
    assert waited == []


def test_garbage_in_the_hint_is_ignored():
    environ = {restart.WAIT_ENV: "abc"}
    waited = []
    assert restart.wait_for_predecessor(environ=environ, wait=lambda *a: waited.append(a) or True) is True
    assert waited == []
    assert environ == {}


def test_old_instance_that_keeps_running_is_reported():
    assert restart.wait_for_predecessor(environ={restart.WAIT_ENV: "4711"}, wait=lambda pid, timeout: False) is False
