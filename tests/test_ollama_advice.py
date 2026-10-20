# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import threading

import pytest

from kira import ollama_advice as oa
from kira.release_info import ReleaseInfo, OllamaPin
from kira.update_watch import run_periodically

INFO = ReleaseInfo(
    python="3.12.10",
    ollama=OllamaPin("0.40.5", "https://github.com/ollama/ollama/releases/download/v0.40.5/OllamaSetup.exe",
                        "ea" * 32, 1_584_489_392),
    models={"gemma4:26b-a4b-it-qat": "2dd7" * 16, "gemma4": "ab" * 32},
)


@pytest.mark.parametrize("env,expected", [
    ({}, "http://127.0.0.1:11434"),
    ({"OLLAMA_HOST": "0.0.0.0:11434"}, "http://127.0.0.1:11434"),
    ({"OLLAMA_HOST": "192.0.2.7:11500"}, "http://192.0.2.7:11500"),
    ({"OLLAMA_HOST": "https://ollama.example.invalid"}, "https://ollama.example.invalid:443"),
    ({"OLLAMA_HOST": "http://192.0.2.7"}, "http://192.0.2.7:80"),
    ({"OLLAMA_HOST": "[::1]:11434"}, "http://[::1]:11434"),
])
def test_server_url_follows_ollama_host(env, expected):
    assert oa.server_url(env) == expected


def test_only_loopback_counts_as_local():
    assert oa.is_local("http://127.0.0.1:11434")
    assert oa.is_local("http://localhost:11434")
    assert oa.is_local("http://[::1]:11434")
    assert not oa.is_local("http://192.0.2.7:11434")


def test_windows_ollama_is_found_under_localappdata(tmp_path):
    assert oa.windows_ollama_exe({"LOCALAPPDATA": str(tmp_path)}) is None
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert oa.windows_ollama_exe({"LOCALAPPDATA": str(tmp_path)}) == exe
    assert oa.windows_ollama_exe({}) is None


@pytest.mark.parametrize("stdout,stderr,expected", [
    ("ollama version is 0.40.5\n", "", "0.40.5"),
    ("ollama version is 0.35.0\n", "Warning: client version is 0.40.5\n", "0.40.5"),
    ("", "Warning: could not connect to a running Ollama instance\nWarning: client version is 0.32.15\n", "0.32.15"),
    ("kaputt", "", None),
])
def test_windows_ollama_version_reads_the_installed_client(stdout, stderr, expected):
    from types import SimpleNamespace
    run = lambda cmd, **kw: SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)
    assert oa.windows_ollama_version(oa.Path("ollama.exe"), run=run) == expected


@pytest.mark.parametrize("base,server,windows,expected", [
    ("http://127.0.0.1:11434", "0.35.0", "0.35.0", oa.WINDOWS),
    ("http://127.0.0.1:11434", "0.35.0", "0.40.5", oa.PORT),
    ("http://127.0.0.1:11434", "0.35.0", None, oa.ELSEWHERE),
    ("http://192.0.2.7:11434", "0.35.0", "0.35.0", oa.REMOTE),
])
def test_placement_tells_whose_ollama_answers(base, server, windows, expected):
    assert oa.placement(base, server, windows) == expected


def test_check_uses_the_installed_windows_version_for_the_button(tmp_path):
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    env = {"LOCALAPPDATA": str(tmp_path)}
    windows = lambda base: "win-ollama"
    advice = oa.check("x", INFO, env=env, fetch=lambda base: ("0.35.0", {}), version_of=lambda path: "0.35.0",
                      owner=windows)
    assert [(a.kind, a.where) for a in advice] == [("ollama", oa.WINDOWS)]
    advice = oa.check("x", INFO, env=env, fetch=lambda base: ("0.35.0", {}), version_of=lambda path: "0.41.0",
                      owner=windows)
    assert [(a.kind, a.where) for a in advice] == [("ollama", oa.PORT)]
    assert oa.check("x", INFO, env=env, fetch=lambda base: ("0.41.0", {}), version_of=lambda path: "0.41.0",
                    owner=windows) == []


def test_fetch_state_reads_version_and_digests():
    answers = {
        "http://h/api/version": {"version": "0.35.0"},
        "http://h/api/tags": {"models": [{"name": "gemma4:26b-a4b-it-qat", "digest": "AB" * 32},
                                         {"model": "gemma4", "digest": "cd" * 32},
                                         {"name": "boese", "digest": "ab\nFAKE LOG LINE"}, 7]},
    }
    version, digests = oa.fetch_state("http://h", get=answers.__getitem__)
    assert version == "0.35.0"
    assert digests == {"gemma4:26b-a4b-it-qat": "ab" * 32, "gemma4:latest": "cd" * 32}


def test_fetch_state_without_server_reports_nothing():
    def down(url):
        raise OSError("verweigert")
    assert oa.fetch_state("http://h", get=down) == (None, {})


def test_older_ollama_gets_advice_with_download_data():
    advice = oa.evaluate(INFO, "0.35.0", {}, "gemma4:26b-a4b-it-qat")
    assert advice == [oa.Advice(
        kind="ollama", installed="0.35.0", tested="0.40.5", url=INFO.ollama.url,
        sha256=INFO.ollama.sha256, size=INFO.ollama.size, where=oa.WINDOWS,
    )]
    assert advice[0].key == "ollama||0.40.5"


@pytest.mark.parametrize("version", ["0.40.5", "0.41.0", "kaputt"])
def test_same_newer_or_unreadable_ollama_stays_quiet(version):
    assert oa.evaluate(INFO, version, {}, "gemma4:26b-a4b-it-qat") == []


def test_other_build_of_the_tested_model_gets_advice():
    advice = oa.evaluate(INFO, "0.40.5", {"gemma4:26b-a4b-it-qat": "00" * 32}, "gemma4:26b-a4b-it-qat")
    assert [a.kind for a in advice] == ["model"]
    assert advice[0].model == "gemma4:26b-a4b-it-qat"
    assert advice[0].tested == "2dd7" * 16


def test_untagged_model_names_match_latest():
    advice = oa.evaluate(INFO, "0.40.5", {"gemma4:latest": "00" * 32}, "gemma4")
    assert advice[0].model == "gemma4:latest"


@pytest.mark.parametrize("digests,model", [
    ({"gemma4:26b-a4b-it-qat": "2dd7" * 16}, "gemma4:26b-a4b-it-qat"),
    ({"qwen3:8b": "00" * 32}, "qwen3:8b"),
    ({}, "gemma4:26b-a4b-it-qat"),
])
def test_matching_unmeasured_or_missing_model_stays_quiet(digests, model):
    assert oa.evaluate(INFO, "0.40.5", digests, model) == []


def test_remote_server_is_marked_for_the_dialog():
    advice = oa.evaluate(INFO, "0.35.0", {}, "x", where=oa.REMOTE)[0]
    assert advice.where == oa.REMOTE and advice.local is False


def test_without_release_file_nothing_is_reported():
    assert oa.evaluate(None, "0.1.0", {}, "x") == []


def test_watch_skips_declined_and_notifies_once_per_session():
    item = oa.Advice("ollama", "0.35.0", "0.40.5")
    other = oa.Advice("model", "aa", "bb", model="m:latest")
    shown, notified, declined = [], [], {other.key}
    watch = oa.AdviceWatch(check=lambda: [item, other], is_declined=declined.__contains__,
                           set_advice=shown.append, notify=notified.append)
    assert watch.run_once() == [item]
    assert watch.run_once() == [item]
    assert shown == [[item], [item]]
    assert notified == [item]


def test_first_check_runs_after_the_start_delay():
    runs = []

    class _Watch:
        def run_once(self):
            runs.append(1)
            stop.set()

    stop = threading.Event()
    run_periodically(_Watch(), 3600.0, stop, first_s=0.0)
    assert runs == [1]


def test_check_keeps_the_button_away_from_a_wsl_or_docker_ollama(tmp_path):
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    env = {"LOCALAPPDATA": str(tmp_path)}
    advice = oa.check("x", INFO, env=env, fetch=lambda base: ("0.35.0", {}), version_of=lambda path: "0.35.0",
                      owner=lambda base: "wsl")
    assert [a.where for a in advice] == [oa.PORT]


def test_watch_notifies_once_across_restarts():
    item = oa.Advice("ollama", "0.35.0", "0.40.5")
    stored, notified = set(), []
    for _ in range(3):
        watch = oa.AdviceWatch(check=lambda: [item], is_declined=lambda key: False, set_advice=lambda a: None,
                               notify=notified.append, is_notified=stored.__contains__, mark_notified=stored.add)
        watch.run_once()
    assert notified == [item]
