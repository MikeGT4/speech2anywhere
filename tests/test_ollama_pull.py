# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import io
import json
import logging
import threading
import time
import urllib.error

import pytest

from kira import ollama_pull
from kira.ollama_pull import ModelPull

REAL_CONNECT = ollama_pull.connect
REAL_REGISTRY_SIZE = ollama_pull.registry_size

GEMMA_MANIFEST = {
    "schemaVersion": 2,
    "config": {"digest": "sha256:e5ca", "size": 242},
    "layers": [
        {"mediaType": "application/vnd.ollama.image.projector", "size": 175_115_616},
        {"mediaType": "application/vnd.ollama.image.model", "size": 7_381_383_680},
        {"mediaType": "application/vnd.ollama.image.draft", "size": 465_109_152},
        {"mediaType": "application/vnd.ollama.image.template", "size": 13},
        {"mediaType": "application/vnd.ollama.image.license", "size": 10_174},
        {"mediaType": "application/vnd.ollama.image.params", "size": 64},
    ],
}


@pytest.fixture(autouse=True)
def _no_live_services(monkeypatch):
    reached = []

    def refuse(*args, **kwargs):
        reached.append(args)
        raise AssertionError("Test erreicht einen echten Dienst")

    monkeypatch.setattr("kira.ollama_pull.connect", refuse)
    monkeypatch.setattr("kira.ollama_pull.registry_size", refuse)
    monkeypatch.setattr("urllib.request.urlopen", refuse)
    yield
    assert reached == [], "Test erreicht einen echten Dienst"


class FakeClient:
    def __init__(self, events=(), error=None, hold=False):
        self.events = list(events)
        self.error = error
        self.hold = hold
        self.calls = []
        self.shut = threading.Event()

    def pull(self, model, stream=False):
        self.calls.append((model, stream))
        if self.error is not None:
            raise self.error
        return self._stream()

    def _stream(self):
        yield from self.events
        if self.hold and self.shut.wait(3):
            raise ConnectionError("Verbindung vom Client geschlossen")

    def close(self):
        self.shut.set()


def _use(monkeypatch, client, size=0):
    monkeypatch.setattr("kira.ollama_pull.connect", lambda: client)
    monkeypatch.setattr("kira.ollama_pull.registry_size", lambda model, timeout=None: size)


def _run_in_thread(pull, emit):
    outcome = []

    def work():
        try:
            outcome.append(pull.run(emit))
        except Exception as exc:
            outcome.append(exc)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return thread, outcome


def test_cancel_closes_the_client_while_ollama_is_silent(monkeypatch):
    client = FakeClient([{"status": "pulling manifest"}], hold=True)
    _use(monkeypatch, client)
    pull = ModelPull("gemma4:12b")
    seen = threading.Event()
    thread, outcome = _run_in_thread(pull, lambda *args: seen.set())
    assert seen.wait(2)
    started = time.monotonic()
    pull.cancel()
    thread.join(2)
    assert not thread.is_alive()
    assert time.monotonic() - started < 1
    assert client.shut.is_set()
    assert outcome == [False]


def test_cancel_during_the_size_lookup_ends_without_a_connection(monkeypatch):
    lookup = threading.Event()
    release = threading.Event()
    opened = []

    def slow_size(model, timeout=None):
        lookup.set()
        release.wait(3)
        return 8_000

    monkeypatch.setattr("kira.ollama_pull.registry_size", slow_size)
    monkeypatch.setattr("kira.ollama_pull.connect", lambda: opened.append(1))
    pull = ModelPull("gemma4:12b")
    thread, outcome = _run_in_thread(pull, lambda *args: None)
    assert lookup.wait(2)
    started = time.monotonic()
    pull.cancel()
    thread.join(2)
    release.set()
    assert not thread.is_alive()
    assert time.monotonic() - started < 1
    assert outcome == [False]
    assert opened == []


def test_pull_closes_the_client_after_success(monkeypatch):
    client = FakeClient([
        {"status": "pulling aaa", "digest": "sha256:aaa", "total": 10, "completed": 10},
        {"status": "success"},
    ])
    _use(monkeypatch, client)
    assert ModelPull("gemma4:12b").run(lambda *args: None) is True
    assert client.shut.is_set()
    assert client.calls == [("gemma4:12b", True)]


def test_pull_closes_the_client_after_an_error(monkeypatch):
    client = FakeClient(error=ConnectionError("weg"))
    _use(monkeypatch, client)
    with pytest.raises(ConnectionError):
        ModelPull("gemma4:12b").run(lambda *args: None)
    assert client.shut.is_set()


def test_stream_end_without_success_is_an_error(monkeypatch):
    client = FakeClient([
        {"status": "pulling aaa", "digest": "sha256:aaa", "total": 10, "completed": 4},
    ])
    _use(monkeypatch, client)
    with pytest.raises(ollama_pull.PullFailed) as caught:
        ModelPull("gemma4:12b").run(lambda *args: None)
    assert str(caught.value) == ollama_pull.INCOMPLETE


def test_layers_count_complete_once_ollama_checks_the_download(monkeypatch):
    client = FakeClient([
        {"status": "pulling aaa", "digest": "sha256:aaa", "total": 91_727_296, "completed": 90_717_875},
        {"status": "pulling bbb", "digest": "sha256:bbb", "total": 182, "completed": 0},
        {"status": "pulling ccc", "digest": "sha256:ccc", "total": 488, "completed": 488},
        {"status": "verifying sha256 digest"},
        {"status": "writing manifest"},
        {"status": "success"},
    ])
    _use(monkeypatch, client)
    seen = []
    ModelPull("smollm:135m").run(lambda *args: seen.append(args))
    total = 91_727_296 + 182 + 488
    assert seen[-3:] == [
        ("verifying sha256 digest", total, total),
        ("writing manifest", total, total),
        ("success", total, total),
    ]


def test_size_from_the_library_counts_until_the_layers_add_up(monkeypatch):
    client = FakeClient([
        {"status": "pulling manifest"},
        {"status": "pulling proj", "digest": "sha256:proj", "total": 175, "completed": 100},
        {"status": "pulling proj", "digest": "sha256:proj", "total": 175, "completed": 175},
        {"status": "pulling model", "digest": "sha256:model", "total": 7_381, "completed": 0},
        {"status": "pulling draft", "digest": "sha256:draft", "total": 900, "completed": 900},
        {"status": "success"},
    ])
    _use(monkeypatch, client, size=8_021)
    seen = []
    ModelPull("gemma4:12b").run(lambda *args: seen.append(args))
    assert seen[0] == ("pulling manifest", 0, 0)
    assert ("pulling proj", 100, 8_021) in seen
    assert ("pulling model", 175, 8_021) in seen
    assert ("pulling draft", 1_075, 8_456) in seen


def test_without_a_size_from_the_library_the_layers_count_as_before(monkeypatch):
    client = FakeClient([
        {"status": "pulling proj", "digest": "sha256:proj", "total": 175, "completed": 175},
        {"status": "success"},
    ])
    _use(monkeypatch, client, size=0)
    seen = []
    ModelPull("gemma4:12b").run(lambda *args: seen.append(args))
    assert seen[0] == ("pulling proj", 175, 175)


@pytest.mark.parametrize("model,url", [
    ("gemma4:12b", "https://registry.ollama.ai/v2/library/gemma4/manifests/12b"),
    ("gemma4", "https://registry.ollama.ai/v2/library/gemma4/manifests/latest"),
    ("huihui_ai/Qwen3.6-abliterated:27b",
     "https://registry.ollama.ai/v2/huihui_ai/Qwen3.6-abliterated/manifests/27b"),
    ("registry.ollama.ai/library/gemma4:12b", "https://registry.ollama.ai/v2/library/gemma4/manifests/12b"),
    ("hf.co/someone/model:Q4_K_M", None),
    ("localhost:5000/team/model:v1", None),
    ("gemma4:12b@sha256:abc", None),
    ("../gemma4:12b", None),
    ("", None),
])
def test_manifest_url_only_for_the_ollama_library(model, url):
    assert ollama_pull.manifest_url(model) == url


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_registry_size_sums_config_and_layers_with_a_time_limit(monkeypatch):
    asked = []

    def urlopen(request, timeout=None):
        asked.append((request.full_url, request.get_header("Accept"), timeout))
        return _Answer(json.dumps(GEMMA_MANIFEST).encode())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert REAL_REGISTRY_SIZE("gemma4:12b") == 8_021_618_941
    assert asked == [(
        "https://registry.ollama.ai/v2/library/gemma4/manifests/12b",
        "application/vnd.docker.distribution.manifest.v2+json",
        ollama_pull.MANIFEST_TIMEOUT_S,
    )]


@pytest.mark.parametrize("answer", [
    urllib.error.HTTPError("https://registry.ollama.ai/v2/library/x/manifests/y", 404, "Not Found", {}, None),
    urllib.error.URLError("keine Verbindung"),
    TimeoutError("timed out"),
    b"kein json",
    json.dumps({"layers": []}).encode(),
])
def test_registry_size_logs_failures_and_falls_back(monkeypatch, caplog, answer):
    def urlopen(request, timeout=None):
        if isinstance(answer, Exception):
            raise answer
        return _Answer(answer)

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    with caplog.at_level(logging.INFO, logger="kira.ollama_pull"):
        assert REAL_REGISTRY_SIZE("gemma4:12b") == 0
    assert any("gemma4:12b" in record.getMessage() for record in caplog.records)


def test_connect_limits_only_the_connection_setup(monkeypatch):
    import ollama

    made = []

    class Recorder:
        def __init__(self, host=None, **kwargs):
            made.append((host, kwargs))

    monkeypatch.setattr(ollama, "Client", Recorder)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert isinstance(REAL_CONNECT(), Recorder)
    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    REAL_CONNECT()
    assert [host for host, _ in made] == [None, "http://127.0.0.1:11434"]
    timeout = made[0][1]["timeout"]
    assert timeout.connect == ollama_pull.CONNECT_TIMEOUT_S == 10.0
    assert timeout.read is None


def test_unknown_model_reads_german_without_the_status_code():
    from ollama import ResponseError

    error = ResponseError("pull model manifest: file does not exist")
    assert "status code" in str(error)
    assert ollama_pull.missing_text("gemma4:12b", error) == "Modell gemma4:12b gibt es bei Ollama nicht."
    assert ollama_pull.missing_text("gemma4:12b", ConnectionError("weg")) is None


class _Transport:
    def __init__(self):
        self.closed = threading.Event()

    def close(self):
        self.closed.set()


class ClientWithoutClose:
    def __init__(self, events=(), hold=False):
        self._client = _Transport()
        self.events = list(events)
        self.hold = hold

    def pull(self, model, stream=False):
        return self._stream()

    def _stream(self):
        yield from self.events
        if self.hold and self._client.closed.wait(3):
            raise ConnectionError("Verbindung vom Client geschlossen")


def test_a_client_without_close_shuts_its_connection_after_success(monkeypatch):
    client = ClientWithoutClose([{"status": "success"}])
    _use(monkeypatch, client)
    assert ModelPull("gemma4:12b").run(lambda *args: None) is True
    assert client._client.closed.is_set()


def test_cancel_reaches_a_client_without_close(monkeypatch):
    client = ClientWithoutClose([{"status": "pulling manifest"}], hold=True)
    _use(monkeypatch, client)
    pull = ModelPull("gemma4:12b")
    seen = threading.Event()
    thread, outcome = _run_in_thread(pull, lambda *args: seen.set())
    assert seen.wait(2)
    pull.cancel()
    thread.join(1)
    assert not thread.is_alive()
    assert outcome == [False]
