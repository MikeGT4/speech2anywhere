# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import argparse
import datetime
import hashlib
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{8A2C6A14-3B3D-4E2C-8A0E-7C9D1A0B2E33}_is1"
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
ERROR_INVALID_PARAMETER = 87
CREATE_NO_WINDOW = 0x08000000
DETACHED = 0x00000008 | 0x00000200
EXIT_WAIT_S = 600.0
PIP_TRIES = 3
PIP_TIMEOUT_S = 600
LAUNCHERS = ("kira.exe", "kira-once.exe")


class Log:
    def __init__(self, path: Path) -> None:
        self._path = path

    def __call__(self, text: str) -> None:
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(f"{stamp} {text}\n")
        except OSError:
            pass


def wait_for_exit(pid: int, timeout_s: float) -> bool:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return ctypes.get_last_error() == ERROR_INVALID_PARAMETER
    try:
        return kernel32.WaitForSingleObject(handle, int(timeout_s * 1000)) == WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_items(site: Path) -> list[Path]:
    return [item for item in (site / "kira", *sorted(site.glob("kira-*.dist-info"))) if item.is_dir()]


def backup(site: Path, scripts: Path, dest: Path) -> Path:
    shutil.rmtree(dest, ignore_errors=True)
    (dest / "site").mkdir(parents=True)
    (dest / "scripts").mkdir()
    for item in _package_items(site):
        shutil.copytree(item, dest / "site" / item.name)
    for name in LAUNCHERS:
        if (scripts / name).is_file():
            shutil.copy2(scripts / name, dest / "scripts" / name)
    return dest


def restore(snapshot: Path, site: Path, scripts: Path) -> None:
    for item in _package_items(site):
        shutil.rmtree(item, ignore_errors=True)
    for item in (snapshot / "site").iterdir():
        shutil.copytree(item, site / item.name, dirs_exist_ok=True)
    for item in (snapshot / "scripts").iterdir():
        shutil.copy2(item, scripts / item.name)


def install(python: Path, wheel: Path, log, run=subprocess.run, sleep=time.sleep) -> bool:
    cmd = [str(python), "-m", "pip", "--isolated", "install", "--no-index", "--no-deps", "--force-reinstall",
           "--disable-pip-version-check", "--no-warn-script-location", str(wheel)]
    for attempt in range(1, PIP_TRIES + 1):
        try:
            result = run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
                         timeout=PIP_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as exc:
            log(f"pip Versuch {attempt}: {exc}")
        else:
            log(f"pip Versuch {attempt}: Exit {result.returncode}")
            for line in ((result.stdout or "") + (result.stderr or "")).splitlines()[-20:]:
                log("  " + line)
            if result.returncode == 0:
                return True
        if attempt < PIP_TRIES:
            sleep(2.0)
    return False


def installed_version(python: Path, log, run=subprocess.run) -> str:
    probe = "import importlib.metadata as m, kira; print(m.version('kira'), kira.__version__)"
    try:
        result = run([str(python), "-I", "-c", probe], capture_output=True, text=True,
                     creationflags=CREATE_NO_WINDOW, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"Versionsprüfung nicht möglich: {exc}")
        return ""
    parts = (result.stdout or "").split()
    if result.returncode != 0 or len(parts) != 2 or parts[0] != parts[1]:
        log(f"Versionsprüfung: Exit {result.returncode}, Ausgabe {result.stdout!r} {result.stderr[-300:]!r}")
        return ""
    return parts[0]


def update_uninstall_entry(version: str, app_dir: Path, log, reg=None) -> bool:
    if reg is None:
        import winreg as reg
    for root in (reg.HKEY_CURRENT_USER, reg.HKEY_LOCAL_MACHINE):
        try:
            with reg.OpenKey(root, UNINSTALL_KEY, 0, reg.KEY_READ | reg.KEY_SET_VALUE) as key:
                location, _kind = reg.QueryValueEx(key, "InstallLocation")
                if Path(str(location)).resolve() != app_dir.resolve():
                    continue
                reg.SetValueEx(key, "DisplayVersion", 0, reg.REG_SZ, version)
                reg.SetValueEx(key, "DisplayName", 0, reg.REG_SZ, f"Speech2Anywhere {version}")
                log(f"Eintrag unter Apps auf {version} gesetzt")
                return True
        except OSError:
            continue
    log("Eintrag unter Apps nicht gefunden, bleibt unverändert")
    return False


def message(text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "Speech2Anywhere", 0x40 | 0x10000)
    except Exception:
        pass


def launch(exe: Path, popen=subprocess.Popen) -> None:
    popen([str(exe)], creationflags=DETACHED, close_fds=True, cwd=str(exe.parent.parent.parent))


def main(argv: list[str] | None = None, *, prefix: Path | None = None, wait=wait_for_exit,
         installer=install, verify=installed_version, register=update_uninstall_entry, notify=message,
         start=launch) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, action="append", default=[])
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--current", default="")
    parser.add_argument("--log", required=True)
    args = parser.parse_args(argv)
    log = Log(Path(args.log))
    prefix = prefix or Path(sys.executable).resolve().parent
    kira_exe = prefix / "Scripts" / "kira.exe"
    try:
        return _run(args, log, prefix, wait, installer, verify, register, notify, start)
    except Exception:
        log("Unerwarteter Fehler:\n" + traceback.format_exc())
        notify(
            f"Beim Update auf {args.version} ist ein Fehler aufgetreten. Startet Speech2Anywhere danach nicht, "
            f"hilft das Setup von github.com/MikeGT4/speech2anywhere/releases.\n\nProtokoll: {args.log}"
        )
        if kira_exe.exists():
            start(kira_exe)
        return 4


def _run(args, log, prefix: Path, wait, installer, verify, register, notify, start) -> int:
    python = prefix / "python.exe"
    site, scripts = prefix / "Lib" / "site-packages", prefix / "Scripts"
    kira_exe = scripts / "kira.exe"
    wheel = Path(args.wheel)
    log(f"Programm-Update auf {args.version}: {wheel}")
    for pid in args.pid:
        if not wait(pid, EXIT_WAIT_S):
            log(f"Prozess {pid} läuft weiter, Update nicht eingespielt")
            notify("Speech2Anywhere hat sich nicht beendet. Das Update wurde nicht eingespielt.")
            return 2
    try:
        intact = wheel.is_file() and file_sha256(wheel) == args.sha256.strip().lower()
    except OSError:
        intact = False
    if not intact:
        log("Prüfsumme des Pakets passt nicht mehr, Update nicht eingespielt")
        notify(f"Das Update auf {args.version} wurde nicht eingespielt, das Paket hat sich verändert.")
        if kira_exe.exists():
            start(kira_exe)
        return 3
    snapshot = backup(site, scripts, wheel.parent / "vorher")
    installed = installer(python, wheel, log)
    now = verify(python, log)
    ok = installed and now == args.version
    if ok:
        register(args.version, prefix.parent, log)
        log("fertig")
    else:
        if args.current and now == args.current:
            log(f"Fassung {now} ist unverändert intakt, kein Rückspielen nötig")
        else:
            restore(snapshot, site, scripts)
            log(f"alter Stand wiederhergestellt, jetzt {verify(python, log) or 'unbekannt'}")
        notify(
            f"Das Update auf {args.version} hat nicht geklappt. Speech2Anywhere startet in der "
            f"bisherigen Fassung.\n\nProtokoll: {args.log}"
        )
    if kira_exe.exists():
        start(kira_exe)
    else:
        log(f"{kira_exe} fehlt, kein Neustart")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
