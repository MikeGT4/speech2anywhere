# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "kira" / "release.json"
INSTALLER_FILES = ("installer/kira.iss", "assets/icon-branded.ico")
OLLAMA_URL = "https://github.com/ollama/ollama/releases/download/v{version}/OllamaSetup.exe"
COPYRIGHT = "© 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten."
_NAME = re.compile(r"[-_.]+")


def normalize(name: str) -> str:
    return _NAME.sub("-", name).lower()


def installer_hash(root: Path = ROOT) -> str:
    h = hashlib.sha256()
    for rel in INSTALLER_FILES:
        data = (root / rel).read_bytes()
        if rel.endswith(".iss"):
            data = data.replace(b"\r\n", b"\n")
        h.update(rel.encode("utf-8") + b"\0" + data + b"\0")
    return h.hexdigest()


def requirements(root: Path = ROOT) -> list[str]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return list(project["dependencies"]) + list(project["optional-dependencies"]["windows"])


def resolve(wheels: Path, reqs: list[str]) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet",
             "--no-index", "--find-links", str(wheels), "--report", str(report), *reqs],
            check=True,
        )
        data = json.loads(report.read_text(encoding="utf-8"))
    pins = {}
    for item in data["install"]:
        meta = item["metadata"]
        pins[normalize(meta["name"])] = meta["version"]
    pins.pop("kira", None)
    return dict(sorted(pins.items()))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def measured(host: str, models: list[str]) -> tuple[str, dict[str, str]]:
    with urllib.request.urlopen(f"{host}/api/version", timeout=5) as r:
        version = json.load(r)["version"]
    with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as r:
        tags = {m["name"]: m["digest"] for m in json.load(r)["models"]}
    missing = [m for m in models if m not in tags]
    if missing:
        raise SystemExit(f"Modell fehlt auf diesem Ollama: {', '.join(missing)}")
    return version, {m: tags[m] for m in models}


def computed(wheels: Path) -> dict:
    return {
        "python": platform.python_version(),
        "installer": installer_hash(),
        "requires": resolve(wheels, requirements()),
    }


def load(path: Path = TARGET) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write(args: argparse.Namespace) -> int:
    data = load()
    data["_copyright"] = COPYRIGHT
    data.update(computed(Path(args.wheels)))
    if args.ollama_setup:
        version, digests = measured(args.ollama_host, args.model)
        setup = Path(args.ollama_setup)
        data["ollama"] = {
            "version": version,
            "url": OLLAMA_URL.format(version=version),
            "sha256": file_sha256(setup),
            "size": setup.stat().st_size,
        }
        data["models"] = digests
    ordered = {key: data[key] for key in ("_copyright", "python", "installer", "requires", "ollama", "models")
               if key in data}
    TARGET.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"geschrieben: {TARGET}")
    return 0


def check(args: argparse.Namespace) -> int:
    have = load()
    want = computed(Path(args.wheels))
    stale = [key for key, value in want.items() if have.get(key) != value]
    for key in ("ollama", "models"):
        if not have.get(key):
            stale.append(key)
    if stale:
        print(f"kira/release.json passt nicht zum Bau: {', '.join(stale)}", file=sys.stderr)
        return 1
    print("kira/release.json passt zum Bau")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("write", "check"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--wheels", required=True)
    w = sub.choices["write"]
    w.add_argument("--ollama-setup")
    w.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    w.add_argument("--model", action="append", default=[])
    args = parser.parse_args(argv)
    return write(args) if args.command == "write" else check(args)


if __name__ == "__main__":
    sys.exit(main())
