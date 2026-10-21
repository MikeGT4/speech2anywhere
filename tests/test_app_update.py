# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from kira import _apply_update as helper
from kira import app_update, release_info
from kira.updater import ReleaseAsset

INFO = {
    "python": "3.12.10",
    "installer": "abc",
    "requires": {"numpy": "2.4.4"},
}


def _wheel_bytes(info=INFO) -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("kira/__init__.py", "")
        if info is not None:
            zf.writestr("kira/release.json", json.dumps(info))
    return buf.getvalue()


def _asset(data: bytes, digest: str | None = None) -> ReleaseAsset:
    return ReleaseAsset(
        name="kira-0.5.5-py3-none-any.whl", url="https://example.invalid/kira.whl", size=len(data),
        sha256=digest if digest is not None else hashlib.sha256(data).hexdigest(),
    )


def _fetch(data: bytes):
    def fetch(url, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target
    return fetch


@pytest.fixture
def same_base(monkeypatch):
    monkeypatch.setattr(release_info, "patch_blockers", lambda new, base: [] if base and new.installer == base.installer else ["anders"])
    return release_info.parse(INFO)


def test_matching_package_is_ready(tmp_path, same_base):
    data = _wheel_bytes()
    check = app_update.check_patch(_asset(data), tmp_path, root=tmp_path, fetch=_fetch(data), installed=same_base)
    assert check.ready
    assert check.wheel == tmp_path / "kira-0.5.5-py3-none-any.whl"


def test_wrong_checksum_deletes_the_download(tmp_path, same_base):
    data = _wheel_bytes()
    check = app_update.check_patch(_asset(data, "00" * 32), tmp_path, root=tmp_path, fetch=_fetch(data),
                                   installed=same_base)
    assert not check.ready
    assert "Prüfsumme" in check.reasons[0]
    assert not (tmp_path / "kira-0.5.5-py3-none-any.whl").exists()


def test_package_without_release_file_falls_back(tmp_path, same_base):
    data = _wheel_bytes(None)
    check = app_update.check_patch(_asset(data), tmp_path, root=tmp_path, fetch=_fetch(data), installed=same_base)
    assert not check.ready
    assert "Grundlage" in check.reasons[0]


def test_failed_download_falls_back(tmp_path, same_base):
    def broken(url, target):
        raise OSError("Netz weg")
    check = app_update.check_patch(_asset(b"x"), tmp_path, root=tmp_path, fetch=broken, installed=same_base)
    assert not check.ready
    assert "Netz weg" in check.reasons[0]


def test_unmanaged_install_never_patches(tmp_path):
    called = []
    check = app_update.check_patch(_asset(b"x"), tmp_path, root=None, fetch=lambda *a: called.append(a))
    assert not check.ready and called == []


def test_install_root_needs_launcher_and_pythonw(tmp_path, monkeypatch):
    monkeypatch.setattr(release_info, "editable_install", lambda: False)
    assert app_update.install_root(tmp_path) is None
    (tmp_path / "Scripts").mkdir()
    (tmp_path / "Scripts" / "kira.exe").write_bytes(b"")
    (tmp_path / "pythonw.exe").write_bytes(b"")
    assert app_update.install_root(tmp_path) == tmp_path
    monkeypatch.setattr(release_info, "editable_install", lambda: True)
    assert app_update.install_root(tmp_path) is None


def test_launch_patch_takes_the_version_from_the_package_name(tmp_path):
    wheel = tmp_path / "update" / "kira-0.6.0-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"w")
    calls = []
    app_update.launch_patch(wheel, "0.6", sha256="cd" * 32, root=tmp_path / "python", pids=[],
                            popen=lambda cmd, **kw: calls.append(cmd))
    cmd = calls[0]
    assert cmd[cmd.index("--version") + 1] == "0.6.0"
    from kira import __version__
    assert cmd[cmd.index("--current") + 1] == __version__


def test_wrong_download_leaves_neither_package_nor_part_file(tmp_path, same_base):
    data = _wheel_bytes()
    app_update.check_patch(_asset(data, "00" * 32), tmp_path, root=tmp_path, fetch=_fetch(data), installed=same_base)
    assert list(tmp_path.iterdir()) == []


def test_launch_patch_copies_the_helper_and_hands_over_pids(tmp_path):
    wheel = tmp_path / "update" / "kira-0.5.5-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"w")
    root = tmp_path / "python"
    calls = []
    log_path = app_update.launch_patch(wheel, "0.5.5", sha256="cd" * 32, root=root, pids=[11, 22],
                                       popen=lambda cmd, **kw: calls.append((cmd, kw)))
    script = wheel.parent / "apply_update.py"
    assert script.read_text(encoding="utf-8") == app_update.HELPER.read_text(encoding="utf-8")
    cmd, kw = calls[0]
    assert cmd[:3] == [str(root / "pythonw.exe"), "-I", str(script)]
    assert cmd[cmd.index("--wheel") + 1] == str(wheel)
    assert cmd[cmd.index("--version") + 1] == "0.5.5"
    assert cmd[cmd.index("--sha256") + 1] == "cd" * 32
    assert [cmd[i + 1] for i, a in enumerate(cmd) if a == "--pid"] == ["11", "22"]
    assert log_path == wheel.parent / "apply_update.log"
    assert kw["cwd"] == str(tmp_path)


def _install_dir(tmp_path):
    prefix = tmp_path / "python"
    site = prefix / "Lib" / "site-packages"
    (site / "kira").mkdir(parents=True)
    (site / "kira" / "__init__.py").write_text("alt", encoding="utf-8")
    (site / "kira-0.5.5.dist-info").mkdir()
    (prefix / "Scripts").mkdir()
    (prefix / "Scripts" / "kira.exe").write_bytes(b"alt")
    wheel = tmp_path / "update" / "kira-0.5.6-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"neu")
    return prefix, wheel, hashlib.sha256(b"neu").hexdigest()


def _args(wheel, sha, *pids):
    out = []
    for pid in pids:
        out += ["--pid", str(pid)]
    return out + ["--wheel", str(wheel), "--sha256", sha, "--version", "0.5.6", "--log", str(wheel.parent / "u.log")]


def test_helper_waits_installs_verifies_registers_and_restarts(tmp_path):
    prefix, wheel, sha = _install_dir(tmp_path)
    seen = []
    code = helper.main(
        _args(wheel, sha, 5, 6), prefix=prefix,
        wait=lambda pid, timeout: seen.append(("wait", pid)) or True,
        installer=lambda python, w, log: seen.append(("pip", python, w)) or True,
        verify=lambda python, log: seen.append("verify") or "0.5.6",
        register=lambda version, app_dir, log: seen.append(("reg", version, app_dir)),
        notify=lambda text: seen.append(("msg", text)),
        start=lambda exe: seen.append(("start", exe)),
    )
    assert code == 0
    assert seen == [
        ("wait", 5), ("wait", 6),
        ("pip", prefix / "python.exe", wheel),
        "verify",
        ("reg", "0.5.6", tmp_path),
        ("start", prefix / "Scripts" / "kira.exe"),
    ]
    assert "fertig" in (wheel.parent / "u.log").read_text(encoding="utf-8")


def _broken_install(prefix):
    def installer(python, wheel, log):
        site = prefix / "Lib" / "site-packages"
        (site / "kira" / "__init__.py").write_text("halb", encoding="utf-8")
        (site / "kira-0.5.6.dist-info").mkdir()
        (prefix / "Scripts" / "kira.exe").write_bytes(b"halb")
        return False
    return installer


@pytest.mark.parametrize("pip_ok,version", [(False, ""), (True, "0.5.5"), (True, "")])
def test_helper_restores_the_old_package_when_install_or_check_fails(tmp_path, pip_ok, version):
    prefix, wheel, sha = _install_dir(tmp_path)
    broken = _broken_install(prefix)
    seen = []
    code = helper.main(
        _args(wheel, sha), prefix=prefix, wait=lambda *a: True,
        installer=lambda python, w, log: broken(python, w, log) or pip_ok,
        verify=lambda python, log: version,
        register=lambda *a: seen.append("reg"), notify=lambda text: seen.append(text),
        start=lambda exe: seen.append("start"),
    )
    site = prefix / "Lib" / "site-packages"
    assert code == 1
    assert "reg" not in seen
    assert (site / "kira" / "__init__.py").read_text(encoding="utf-8") == "alt"
    assert sorted(p.name for p in site.glob("kira-*.dist-info")) == ["kira-0.5.5.dist-info"]
    assert (prefix / "Scripts" / "kira.exe").read_bytes() == b"alt"
    assert any("nicht geklappt" in s for s in seen if isinstance(s, str))
    assert seen[-1] == "start"


def test_helper_refuses_a_package_that_changed_after_the_check(tmp_path):
    prefix, wheel, sha = _install_dir(tmp_path)
    wheel.write_bytes(b"getauscht")
    seen = []
    code = helper.main(
        _args(wheel, sha), prefix=prefix, wait=lambda *a: True,
        installer=lambda *a: seen.append("pip"), verify=lambda *a: "0.5.6",
        notify=lambda text: seen.append("msg"), start=lambda exe: seen.append("start"),
    )
    assert code == 3
    assert seen == ["msg", "start"]


def test_helper_gives_up_when_the_app_keeps_running(tmp_path):
    prefix, wheel, sha = _install_dir(tmp_path)
    seen = []
    code = helper.main(
        _args(wheel, sha, 5), prefix=prefix, wait=lambda *a: False, installer=lambda *a: seen.append("pip"),
        notify=lambda text: seen.append("msg"), start=lambda exe: seen.append("start"),
    )
    assert code == 2
    assert seen == ["msg"]


def test_installed_version_needs_both_sources_to_agree(tmp_path):
    def run(stdout, code=0):
        return lambda cmd, **kw: SimpleNamespace(returncode=code, stdout=stdout, stderr="")
    assert helper.installed_version(Path("py.exe"), lambda t: None, run=run("0.5.6 0.5.6\n")) == "0.5.6"
    assert helper.installed_version(Path("py.exe"), lambda t: None, run=run("0.5.6 0.5.5\n")) == ""
    assert helper.installed_version(Path("py.exe"), lambda t: None, run=run("", 1)) == ""


def test_wait_for_exit_sees_a_finished_process():
    import os
    import sys as _sys
    if _sys.platform != "win32":
        pytest.skip("Windows-API")
    proc = subprocess.Popen([_sys.executable, "-c", "pass"])
    proc.wait()
    assert helper.wait_for_exit(proc.pid, 2.0)
    assert not helper.wait_for_exit(os.getpid(), 0.1)


def test_pip_is_called_without_index_and_dependencies_and_retried(tmp_path):
    runs = []

    def run(cmd, **kw):
        runs.append(cmd)
        return SimpleNamespace(returncode=1 if len(runs) < 3 else 0, stdout="", stderr="gesperrt")

    assert helper.install(Path("py.exe"), Path("k.whl"), lambda text: None, run=run, sleep=lambda s: None)
    assert len(runs) == 3
    assert runs[0][1:5] == ["-m", "pip", "--isolated", "install"]
    assert {"--no-index", "--no-deps", "--force-reinstall"} <= set(runs[0])


def test_pip_gives_up_after_three_tries(tmp_path):
    def run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    assert not helper.install(Path("py.exe"), Path("k.whl"), lambda text: None, run=run, sleep=lambda s: None)


class _Reg:
    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ, KEY_SET_VALUE, REG_SZ = "HKCU", "HKLM", 1, 2, 1

    def __init__(self, entries):
        self.entries = entries
        self.written = {}

    def OpenKey(self, root, path, reserved, access):  # noqa: N802
        if root not in self.entries:
            raise OSError("fehlt")

        class _Key:
            def __enter__(self):
                return root

            def __exit__(self, *a):
                return False
        assert path == helper.UNINSTALL_KEY
        return _Key()

    def QueryValueEx(self, key, name):  # noqa: N802
        return self.entries[key], 1

    def SetValueEx(self, key, name, reserved, kind, value):  # noqa: N802
        self.written[(key, name)] = value


def test_uninstall_entry_follows_the_new_version(tmp_path):
    import sys as _sys
    if _sys.platform != "win32":
        pytest.skip("Windows-Pfade")
    reg = _Reg({"HKCU": str(tmp_path) + "\\"})
    assert helper.update_uninstall_entry("0.5.5", tmp_path, lambda t: None, reg=reg)
    assert reg.written == {("HKCU", "DisplayVersion"): "0.5.5", ("HKCU", "DisplayName"): "Speech2Anywhere 0.5.5"}


def test_uninstall_entry_of_another_installation_stays(tmp_path):
    reg = _Reg({"HKCU": str(tmp_path / "anders")})
    assert not helper.update_uninstall_entry("0.5.5", tmp_path, lambda t: None, reg=reg)
    assert reg.written == {}


def test_helper_uses_only_the_standard_library():
    import ast
    tree = ast.parse(app_update.HELPER.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert names <= {"__future__", "argparse", "datetime", "hashlib", "shutil", "subprocess", "sys", "time", "traceback", "pathlib",
                     "ctypes", "winreg"}


def test_helper_keeps_an_intact_old_version_instead_of_restoring(tmp_path, monkeypatch):
    prefix, wheel, sha = _install_dir(tmp_path)
    restored = []
    monkeypatch.setattr(helper, "restore", lambda *a: restored.append(a))
    code = helper.main(
        _args(wheel, sha) + ["--current", "0.5.5"], prefix=prefix, wait=lambda *a: True,
        installer=lambda *a: False, verify=lambda *a: "0.5.5",
        register=lambda *a: None, notify=lambda text: None, start=lambda exe: None,
    )
    assert code == 1
    assert restored == []
    assert "unverändert intakt" in (wheel.parent / "u.log").read_text(encoding="utf-8")


def test_helper_reports_and_restarts_when_the_backup_fails(tmp_path, monkeypatch):
    prefix, wheel, sha = _install_dir(tmp_path)

    def broken(*a):
        raise OSError("Platte voll")

    monkeypatch.setattr(helper, "backup", broken)
    seen = []
    code = helper.main(
        _args(wheel, sha), prefix=prefix, wait=lambda *a: True, installer=lambda *a: seen.append("pip"),
        notify=lambda text: seen.append("msg"), start=lambda exe: seen.append("start"),
    )
    assert code == 4
    assert seen == ["msg", "start"]
    assert "Platte voll" in (wheel.parent / "u.log").read_text(encoding="utf-8")


def test_restore_merges_into_a_folder_that_could_not_be_removed(tmp_path, monkeypatch):
    prefix, wheel, sha = _install_dir(tmp_path)
    site, scripts = prefix / "Lib" / "site-packages", prefix / "Scripts"
    snapshot = helper.backup(site, scripts, tmp_path / "vorher")
    (site / "kira" / "__init__.py").write_text("halb", encoding="utf-8")
    monkeypatch.setattr(helper.shutil, "rmtree", lambda *a, **k: None)
    helper.restore(snapshot, site, scripts)
    assert (site / "kira" / "__init__.py").read_text(encoding="utf-8") == "alt"


def test_wait_for_exit_treats_an_unknown_process_as_gone():
    import gc
    import sys as _sys
    if _sys.platform != "win32":
        pytest.skip("Windows-API")
    proc = subprocess.Popen([_sys.executable, "-c", "pass"])
    proc.wait()
    pid = proc.pid
    del proc
    gc.collect()
    assert helper.wait_for_exit(pid, 1.0)
