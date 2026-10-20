# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import json
import re
import zipfile
from importlib import metadata

import pytest

from kira import release_info as ri

SAMPLE = {
    "_copyright": "x",
    "python": "3.12.10",
    "installer": "abc",
    "requires": {"numpy": "2.4.4", "certifi": "2026.4.22"},
    "ollama": {"version": "0.40.5", "url": "https://example.invalid/OllamaSetup.exe", "sha256": "AB" * 32, "size": 7},
    "models": {"gemma4:e4b": "C6EB"},
}


def _versions(**known):
    def version_of(name):
        if name not in known:
            raise metadata.PackageNotFoundError(name)
        return known[name]
    return version_of


def test_parse_reads_all_fields_and_lowercases_hashes():
    info = ri.parse(SAMPLE)
    assert info.python == "3.12.10"
    assert info.installer == "abc"
    assert info.requires == {"numpy": "2.4.4", "certifi": "2026.4.22"}
    assert info.ollama == ri.OllamaPin("0.40.5", "https://example.invalid/OllamaSetup.exe", "ab" * 32, 7)
    assert info.models == {"gemma4:e4b": "c6eb"}


@pytest.mark.parametrize("raw", [None, [], "text", 3])
def test_parse_rejects_non_objects(raw):
    assert ri.parse(raw) is None


def test_parse_tolerates_missing_parts():
    info = ri.parse({"python": "3.12.10"})
    assert info.ollama is None
    assert info.requires == {} and info.models == {}


def test_load_installed_reads_the_package_file(tmp_path):
    (tmp_path / "release.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    assert ri.load_installed(tmp_path).installer == "abc"
    assert ri.load_installed(tmp_path / "fehlt") is None


def test_load_installed_survives_broken_json(tmp_path):
    (tmp_path / "release.json").write_text("{kaputt", encoding="utf-8")
    assert ri.load_installed(tmp_path) is None


def test_read_from_wheel_finds_the_member(tmp_path):
    wheel = tmp_path / "kira-0.5.5-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr("kira/release.json", json.dumps(SAMPLE))
    assert ri.read_from_wheel(wheel).python == "3.12.10"


def test_read_from_wheel_without_member_or_zip_returns_none(tmp_path):
    empty = tmp_path / "leer.whl"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("kira/__init__.py", "")
    assert ri.read_from_wheel(empty) is None
    junk = tmp_path / "kein.whl"
    junk.write_bytes(b"nope")
    assert ri.read_from_wheel(junk) is None


def test_matching_base_needs_no_full_installer():
    new = ri.parse(SAMPLE)
    reasons = ri.patch_blockers(new, new, python_version="3.12.10",
                                version_of=_versions(numpy="2.4.4", certifi="2026.04.22"))
    assert reasons == []


def test_every_difference_is_named():
    new = ri.parse(SAMPLE)
    old = ri.parse({**SAMPLE, "installer": "alt"})
    reasons = ri.patch_blockers(new, old, python_version="3.12.9", version_of=_versions(numpy="2.3.0"))
    assert "Das Setup selbst hat sich geändert." in reasons
    assert "Python 3.12.10 statt 3.12.9." in reasons
    assert "numpy 2.3.0 wird zu 2.4.4." in reasons
    assert "certifi 2026.4.22 ist neu." in reasons


def test_install_without_release_file_needs_the_full_installer():
    new = ri.parse(SAMPLE)
    reasons = ri.patch_blockers(new, None, python_version="3.12.10",
                                version_of=_versions(numpy="2.4.4", certifi="2026.4.22"))
    assert len(reasons) == 1


def test_package_without_requirements_is_never_patched():
    new = ri.parse({**SAMPLE, "requires": {}})
    assert ri.patch_blockers(new, new, python_version="3.12.10", version_of=_versions())


class _Dist:
    def __init__(self, text):
        self._text = text

    def read_text(self, name):
        return self._text if name == "direct_url.json" else None


@pytest.mark.parametrize("text,expected", [
    (json.dumps({"url": "file:///C:/dev/kira", "dir_info": {"editable": True}}), True),
    (json.dumps({"url": "file:///C:/x/kira.whl", "archive_info": {}}), False),
    (None, False),
    ("kaputt", False),
])
def test_editable_install_reads_direct_url(monkeypatch, text, expected):
    monkeypatch.setattr(ri.metadata, "distribution", lambda name: _Dist(text))
    assert ri.editable_install() is expected


def test_missing_distribution_counts_as_not_patchable(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)
    monkeypatch.setattr(ri.metadata, "distribution", missing)
    assert ri.editable_install() is True


def test_shipped_release_file_is_complete():
    info = ri.load_installed()
    assert info is not None
    assert re.fullmatch(r"3\.12\.\d+", info.python)
    assert re.fullmatch(r"[0-9a-f]{64}", info.installer)
    assert {"numpy", "pyqt6", "faster-whisper", "ollama"} <= set(info.requires)
    assert "kira" not in info.requires
    assert info.ollama is not None
    assert info.ollama.url == f"https://github.com/ollama/ollama/releases/download/v{info.ollama.version}/OllamaSetup.exe"
    assert re.fullmatch(r"[0-9a-f]{64}", info.ollama.sha256)
    assert info.ollama.size > 100_000_000
    assert info.models and all(re.fullmatch(r"[0-9a-f]{64}", d) for d in info.models.values())
