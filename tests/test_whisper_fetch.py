# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import json

import pytest

from kira import _whisper_fetch as fetch_module


@pytest.fixture(autouse=True)
def _no_real_download(monkeypatch):
    reached = []

    def refuse(*args, **kwargs):
        reached.append(args)
        raise AssertionError("Test erreicht einen echten Dienst")

    monkeypatch.setattr(fetch_module, "snapshot_download", refuse)
    monkeypatch.setattr(fetch_module.constants, "DOWNLOAD_CHUNK_SIZE", 10 * 1024 * 1024)
    yield
    assert reached == [], "Test erreicht einen echten Dienst"


def _lines(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_fetch_downloads_the_whitelist_into_the_target_and_names_the_path(monkeypatch, capsys, tmp_path):
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return str(tmp_path)

    monkeypatch.setattr(fetch_module, "snapshot_download", fake_download)

    assert fetch_module.fetch("Systran/faster-whisper-large-v3", str(tmp_path), ["model.bin", "*.txt"]) == 0

    assert calls[0]["repo_id"] == "Systran/faster-whisper-large-v3"
    assert calls[0]["local_dir"] == str(tmp_path)
    assert calls[0]["allow_patterns"] == ["model.bin", "*.txt"]
    assert _lines(capsys) == [{"path": str(tmp_path)}]


def test_fetch_reports_the_bytes_as_lines(monkeypatch, capsys, tmp_path):
    def fake_download(**kwargs):
        bar = kwargs["tqdm_class"](desc="Downloading", total=0, initial=0, unit="B", unit_scale=True)
        bar.total += 3_000
        bar.refresh()
        for _ in range(3):
            bar.update(1_000)
        return str(tmp_path)

    monkeypatch.setattr(fetch_module, "snapshot_download", fake_download)

    fetch_module.fetch("Systran/faster-whisper-large-v3", str(tmp_path), ["model.bin"])

    assert _lines(capsys) == [
        {"done": 0, "total": 3_000},
        {"done": 3_000, "total": 3_000},
        {"path": str(tmp_path)},
    ]


def test_fetch_over_http_reports_at_least_every_megabyte(monkeypatch, capsys, tmp_path):
    chunk_sizes = []

    def fake_download(**kwargs):
        chunk_sizes.append(fetch_module.constants.DOWNLOAD_CHUNK_SIZE)
        return str(tmp_path)

    monkeypatch.setattr(fetch_module, "snapshot_download", fake_download)

    fetch_module.fetch("Systran/faster-whisper-large-v3", str(tmp_path), ["model.bin"])

    assert chunk_sizes and chunk_sizes[0] <= 1024 * 1024


def test_fetch_names_the_error_and_ends_with_one(monkeypatch, capsys, tmp_path):
    def fake_download(**kwargs):
        raise ConnectionError("DNS resolution failed")

    monkeypatch.setattr(fetch_module, "snapshot_download", fake_download)

    assert fetch_module.fetch("Systran/faster-whisper-large-v3", str(tmp_path), ["model.bin"]) == 1

    [line] = _lines(capsys)
    assert line["error"] == "ConnectionError: DNS resolution failed"
    assert "ConnectionError" in line["trace"]


def test_main_takes_repo_target_and_patterns_from_the_command_line(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(fetch_module, "_end_with_parent", lambda: None)
    monkeypatch.setattr(fetch_module, "fetch", lambda *args: calls.append(args) or 0)

    assert fetch_module.main(["Systran/faster-whisper-large-v3", str(tmp_path), "model.bin", "*.txt"]) == 0

    assert calls == [("Systran/faster-whisper-large-v3", str(tmp_path), ["model.bin", "*.txt"])]


def test_the_fetch_ends_when_the_starting_process_goes_away(monkeypatch):
    ends = []
    monkeypatch.setattr(fetch_module.os, "read", lambda fd, size: b"")
    monkeypatch.setattr(fetch_module.os, "_exit", ends.append)

    fetch_module._end_with_parent()

    assert ends == [1]
