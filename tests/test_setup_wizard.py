from __future__ import annotations
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

if sys.platform != "win32":
    pytest.skip("setup_wizard module is Windows-only", allow_module_level=True)

from kira.setup_wizard import (
    DEFAULT_GEMMA_TAG,
    DEFAULT_WHISPER_REPO,
    OLLAMA_API_URL,
    WHISPER_ALLOWED_FILES,
    GemmaPullWorker,
    OllamaSetupWorker,
    WhisperDownloadWorker,
    _has_model_tag,
    is_ollama_installed,
    is_ollama_reachable,
)


@pytest.fixture(autouse=True)
def _no_live_services(monkeypatch):
    reached = []

    def refuse(*args, **kwargs):
        reached.append(args)
        raise AssertionError("Test erreicht einen echten Dienst")

    monkeypatch.setattr("kira.ollama_pull.connect", refuse)
    monkeypatch.setattr("kira.ollama_pull.registry_size", refuse)
    monkeypatch.setattr("kira.setup_wizard.snapshot_download", refuse)
    monkeypatch.setattr("urllib.request.urlopen", refuse)
    yield
    assert reached == [], "Test erreicht einen echten Dienst"


class _FakeClient:
    def __init__(self, events=(), error=None, hold=False):
        self.events = list(events)
        self.error = error
        self.hold = hold
        self.calls = []
        self.closed = False
        self.shut = threading.Event()

    def pull(self, model, stream=False):
        self.calls.append((model, stream))
        if self.error is not None:
            raise self.error

        def generate():
            try:
                yield from self.events
                if self.hold and self.shut.wait(3):
                    raise ConnectionError("Verbindung vom Client geschlossen")
            finally:
                self.closed = True

        return generate()

    def close(self):
        self.shut.set()


def _pull_with(mocker, client, size=0):
    mocker.patch("kira.ollama_pull.connect", return_value=client)
    mocker.patch("kira.ollama_pull.registry_size", return_value=size)


def test_ollama_api_url_uses_ipv4_loopback():
    assert OLLAMA_API_URL == "http://127.0.0.1:11434/api/tags"
    assert "localhost" not in OLLAMA_API_URL


def test_default_whisper_repo_is_large_v3_no_turbo():
    assert DEFAULT_WHISPER_REPO == "Systran/faster-whisper-large-v3"


def test_default_gemma_tag():
    assert DEFAULT_GEMMA_TAG == "gemma4:12b"


def test_is_ollama_installed_true_when_which_returns_path(mocker):
    mocker.patch(
        "kira.setup_wizard.shutil.which",
        return_value="C:\\Users\\user\\AppData\\Local\\Programs\\Ollama\\ollama.exe",
    )
    assert is_ollama_installed() is True


def test_is_ollama_installed_false_when_which_returns_none(mocker, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("PROGRAMFILES", raising=False)
    mocker.patch("kira.setup_wizard.shutil.which", return_value=None)
    assert is_ollama_installed() is False


def test_is_ollama_reachable_true_on_http_200(mocker):
    fake_response = MagicMock()
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)
    fake_response.status = 200
    mocker.patch("kira.setup_wizard.urllib.request.urlopen", return_value=fake_response)
    assert is_ollama_reachable() is True


def test_is_ollama_reachable_false_on_timeout(mocker):
    import socket
    mocker.patch("kira.setup_wizard.urllib.request.urlopen",
                 side_effect=socket.timeout("timed out"))
    assert is_ollama_reachable(timeout=0.1) is False


def test_is_ollama_reachable_false_on_connection_refused(mocker):
    mocker.patch("kira.setup_wizard.urllib.request.urlopen",
                 side_effect=ConnectionRefusedError())
    assert is_ollama_reachable(timeout=0.1) is False


def test_is_ollama_reachable_false_on_urlerror(mocker):
    import urllib.error
    mocker.patch("kira.setup_wizard.urllib.request.urlopen",
                 side_effect=urllib.error.URLError("boom"))
    assert is_ollama_reachable(timeout=0.1) is False


def test_whisper_worker_calls_snapshot_download_with_resume(qtbot, tmp_path, mocker):
    target = tmp_path / "whisper-model"
    fake_download = mocker.patch(
        "kira.setup_wizard.snapshot_download",
        return_value=str(target),
    )
    worker = WhisperDownloadWorker(target_dir=target)

    finished_payloads: list[Path] = []
    worker.finished.connect(lambda p: finished_payloads.append(p))

    worker.run()

    fake_download.assert_called_once()
    kwargs = fake_download.call_args.kwargs
    assert kwargs["repo_id"] == DEFAULT_WHISPER_REPO
    assert Path(kwargs["local_dir"]) == target

    assert len(finished_payloads) == 1
    assert finished_payloads[0] == target


def test_whisper_worker_emits_error_on_network_failure(qtbot, tmp_path, mocker):
    target = tmp_path / "whisper-model"
    mocker.patch(
        "kira.setup_wizard.snapshot_download",
        side_effect=ConnectionError("DNS resolution failed"),
    )
    worker = WhisperDownloadWorker(target_dir=target)
    errors: list[str] = []
    worker.error.connect(lambda msg: errors.append(msg))

    worker.run()

    assert len(errors) == 1
    assert "DNS resolution failed" in errors[0] or "ConnectionError" in errors[0]


def test_whisper_worker_uses_custom_repo_id(qtbot, tmp_path, mocker):
    target = tmp_path / "whisper-model"
    fake_download = mocker.patch(
        "kira.setup_wizard.snapshot_download",
        return_value=str(target),
    )
    worker = WhisperDownloadWorker(
        target_dir=target,
        repo_id="Systran/faster-whisper-large-v3-turbo",
    )

    worker.run()

    kwargs = fake_download.call_args.kwargs
    assert kwargs["repo_id"] == "Systran/faster-whisper-large-v3-turbo"


def test_ollama_worker_skips_install_when_already_installed_and_reachable(
    qtbot, tmp_path, mocker,
):
    installer = tmp_path / "OllamaSetup.exe"
    installer.touch()
    mocker.patch("kira.setup_wizard.is_ollama_installed", return_value=True)
    mocker.patch("kira.setup_wizard.is_ollama_reachable", return_value=True)
    fake_run = mocker.patch("kira.setup_wizard.subprocess.run")

    worker = OllamaSetupWorker(installer_path=installer)
    finished_calls: list[None] = []
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.run()

    fake_run.assert_not_called()
    assert len(finished_calls) == 1


def test_ollama_worker_runs_installer_when_not_installed(qtbot, tmp_path, mocker):
    installer = tmp_path / "OllamaSetup.exe"
    installer.touch()
    mocker.patch("kira.setup_wizard.is_ollama_installed", return_value=False)
    mocker.patch("kira.setup_wizard.is_ollama_reachable",
                 side_effect=[False, True])
    fake_proc = MagicMock()
    fake_proc.wait.return_value = 0
    fake_proc.poll.return_value = 0
    fake_popen = mocker.patch(
        "kira.setup_wizard.subprocess.Popen",
        return_value=fake_proc,
    )
    mocker.patch("kira.setup_wizard.time.sleep", return_value=None)

    worker = OllamaSetupWorker(installer_path=installer)
    finished_calls: list[None] = []
    errors: list[str] = []
    worker.finished.connect(lambda: finished_calls.append(None))
    worker.error.connect(lambda msg: errors.append(msg))

    worker.run()

    fake_popen.assert_called_once()
    args, kwargs = fake_popen.call_args
    cmd = args[0] if args else kwargs.get("args")
    assert isinstance(cmd, list), "subprocess.Popen muss list-args bekommen, kein Shell-String"
    assert cmd == [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    assert kwargs.get("shell") is not True
    assert errors == []
    assert len(finished_calls) == 1


def test_ollama_worker_emits_error_when_installer_path_missing(qtbot, tmp_path, mocker):
    installer = tmp_path / "missing.exe"
    mocker.patch("kira.setup_wizard.is_ollama_installed", return_value=False)
    mocker.patch("kira.setup_wizard.is_ollama_reachable", return_value=False)
    fake_popen = mocker.patch("kira.setup_wizard.subprocess.Popen")

    worker = OllamaSetupWorker(installer_path=installer)
    errors: list[str] = []
    worker.error.connect(lambda msg: errors.append(msg))

    worker.run()

    fake_popen.assert_not_called()
    assert len(errors) == 1


def test_gemma_worker_skips_pull_when_tag_in_list(qtbot, mocker):
    mocker.patch("kira.setup_wizard.find_ollama_exe", return_value=None)
    fake_run = mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(
            returncode=0,
            stdout="NAME                ID    SIZE   MODIFIED\ngemma3:12b   abc   8.1 GB now\n",
            stderr="",
        ),
    )
    fake_popen = mocker.patch("kira.setup_wizard.subprocess.Popen")

    worker = GemmaPullWorker(model_tag="gemma3:12b")
    finished_calls: list[None] = []
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.run()

    fake_run.assert_called_once()
    list_args = fake_run.call_args.args[0] if fake_run.call_args.args else fake_run.call_args.kwargs.get("args")
    assert list_args == ["ollama", "list"]
    fake_popen.assert_not_called()
    assert len(finished_calls) == 1


def test_gemma_worker_pulls_when_tag_missing(qtbot, mocker):
    mocker.patch("kira.setup_wizard.find_ollama_exe", return_value=None)
    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="NAME ID SIZE\n", stderr=""),
    )
    client = _FakeClient([
        {"status": "pulling manifest"},
        {"status": "pulling aaa", "digest": "sha256:aaa", "total": 1000, "completed": 1000},
        {"status": "pulling bbb", "digest": "sha256:bbb", "total": 3000, "completed": 600},
        {"status": "pulling bbb", "digest": "sha256:bbb", "total": 3000, "completed": 3000},
        {"status": "verifying sha256 digest"},
        {"status": "writing manifest"},
        {"status": "success"},
    ])
    _pull_with(mocker, client)
    fake_popen = mocker.patch("kira.setup_wizard.subprocess.Popen")

    worker = GemmaPullWorker(model_tag="gemma3:12b")
    seen: list[tuple] = []
    finished_calls: list[None] = []
    worker.progress.connect(lambda status, done, total: seen.append((status, done, total)))
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.run()

    fake_popen.assert_not_called()
    assert client.calls == [("gemma3:12b", True)]
    assert ("pulling aaa", 1000, 1000) in seen
    assert ("pulling bbb", 1600, 4000) in seen
    assert seen[-1] == ("success", 4000, 4000)
    assert ("verifying sha256 digest", 4000, 4000) in seen
    assert client.closed
    assert client.shut.is_set()
    assert len(finished_calls) == 1


def test_gemma_worker_names_an_unknown_model_in_german(qtbot, mocker):
    from ollama import ResponseError

    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="NAME\n", stderr=""),
    )
    client = _FakeClient(error=ResponseError("pull model manifest: file does not exist"))
    _pull_with(mocker, client)

    worker = GemmaPullWorker(model_tag="gemma3:99b")
    errors: list[str] = []
    finished_calls: list[None] = []
    worker.error.connect(lambda msg: errors.append(msg))
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.run()

    assert errors == ["Modell gemma3:99b gibt es bei Ollama nicht."]
    assert finished_calls == []


def test_gemma_worker_keeps_kind_and_message_for_other_errors(qtbot, mocker):
    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="NAME\n", stderr=""),
    )
    _pull_with(mocker, _FakeClient(error=ConnectionError("Ollama antwortet nicht")))
    worker = GemmaPullWorker(model_tag="gemma4:12b")
    errors: list[str] = []
    worker.error.connect(errors.append)

    worker.run()

    assert errors == ["`ollama pull gemma4:12b` fehlgeschlagen: ConnectionError: Ollama antwortet nicht"]


def test_gemma_worker_reports_an_error_when_the_stream_ends_without_success(qtbot, mocker):
    from kira import ollama_pull

    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="NAME\n", stderr=""),
    )
    _pull_with(mocker, _FakeClient([
        {"status": "pulling aaa", "digest": "sha256:aaa", "total": 3000, "completed": 1200},
    ]))
    worker = GemmaPullWorker(model_tag="gemma4:12b")
    errors: list[str] = []
    texts: list[str] = []
    finished_calls: list[None] = []
    worker.error.connect(errors.append)
    worker.status.connect(texts.append)
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.run()

    assert errors == [f"`ollama pull gemma4:12b` fehlgeschlagen: {ollama_pull.INCOMPLETE}"]
    assert "bereit" not in texts
    assert finished_calls == []


def test_gemma_cancel_ends_the_thread_while_ollama_is_silent(qtbot, mocker):
    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="NAME\n", stderr=""),
    )
    client = _FakeClient([{"status": "pulling manifest"}], hold=True)
    _pull_with(mocker, client)
    worker = GemmaPullWorker(model_tag="gemma4:12b")
    errors: list[str] = []
    finished_calls: list[None] = []
    worker.error.connect(errors.append)
    worker.finished.connect(lambda: finished_calls.append(None))

    try:
        with qtbot.waitSignal(worker.progress, timeout=3000):
            worker.start()
        worker.cancel()

        assert worker.wait(1000)
        assert client.shut.is_set()
        qtbot.wait(50)
        assert errors == [] and finished_calls == []
    finally:
        client.close()
        worker.wait(5000)


def test_gemma_worker_cancel_stops_the_stream(qtbot, mocker):
    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="NAME\n", stderr=""),
    )
    client = _FakeClient([
        {"status": "pulling aaa", "digest": "sha256:aaa", "total": 1000, "completed": n}
        for n in range(0, 1000, 100)
    ])
    _pull_with(mocker, client)

    worker = GemmaPullWorker(model_tag="gemma3:12b")
    seen: list[tuple] = []
    errors: list[str] = []
    finished_calls: list[None] = []

    def on_progress(*args):
        seen.append(args)
        worker.cancel()

    worker.progress.connect(on_progress)
    worker.error.connect(errors.append)
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.run()

    assert len(seen) == 1
    assert client.closed
    assert errors == [] and finished_calls == []


def test_gemma_worker_emits_error_when_ollama_list_fails(qtbot, mocker):
    import subprocess as real_sub
    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        side_effect=real_sub.CalledProcessError(1, ["ollama", "list"]),
    )
    fake_popen = mocker.patch("kira.setup_wizard.subprocess.Popen")

    worker = GemmaPullWorker(model_tag="gemma3:12b")
    errors: list[str] = []
    worker.error.connect(lambda msg: errors.append(msg))

    worker.run()

    fake_popen.assert_not_called()
    assert len(errors) == 1


def test_setup_wizard_instantiates_with_three_pages(qtbot, tmp_path):
    from kira.setup_wizard import SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)

    assert len(wizard.pageIds()) == 3


def test_setup_wizard_accept_calls_mark_first_run_complete(qtbot, tmp_path, mocker):
    from kira.setup_wizard import SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    fake_mark = mocker.patch("kira.setup_wizard.mark_first_run_complete")

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)

    wizard.accept()

    fake_mark.assert_called_once()


def test_download_page_initially_not_complete(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)
    assert download_page.isComplete() is False


def _make_running_mock_worker():
    worker = MagicMock()
    running_states = iter([True, False])

    def running():
        try:
            return next(running_states)
        except StopIteration:
            return False

    worker.isRunning.side_effect = running
    return worker


def test_cleanup_page_stops_running_workers(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)

    whisper = _make_running_mock_worker()
    ollama = _make_running_mock_worker()
    gemma = MagicMock()
    gemma.isRunning.return_value = True

    download_page._whisper_worker = whisper
    download_page._ollama_worker = ollama
    download_page._gemma_worker = gemma

    download_page.cleanupPage()

    whisper.cancel.assert_called_once()
    whisper.wait.assert_called_with(2000)
    whisper.terminate.assert_not_called()

    ollama.cancel.assert_called_once()
    ollama.wait.assert_called_with(2000)
    ollama.terminate.assert_not_called()

    gemma.cancel.assert_called_once()
    gemma.terminate.assert_called_once()
    wait_calls = [c.args for c in gemma.wait.call_args_list]
    assert (2000,) in wait_calls
    assert (5000,) in wait_calls


def test_whisper_error_aborts_pipeline(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)
    fake_gemma_cls = mocker.patch("kira.setup_wizard.GemmaPullWorker")

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)

    download_page._on_whisper_error("DNS resolution failed")

    assert download_page._pipeline_aborted is True

    download_page._on_ollama_finished()

    fake_gemma_cls.assert_not_called()


def test_ollama_error_aborts_pipeline(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)
    fake_gemma_cls = mocker.patch("kira.setup_wizard.GemmaPullWorker")

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)

    download_page._on_ollama_error("Installer Exit-Code 1")

    assert download_page._pipeline_aborted is True

    download_page._start_gemma()

    fake_gemma_cls.assert_not_called()


def test_setup_wizard_accept_warns_on_marker_failure(qtbot, tmp_path, mocker):
    from kira.setup_wizard import SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch(
        "kira.setup_wizard.mark_first_run_complete",
        side_effect=PermissionError("APPDATA-Ordner ist read-only"),
    )
    fake_warn = mocker.patch("kira.setup_wizard.QMessageBox.warning")

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)

    wizard.accept()

    fake_warn.assert_called_once()
    args = fake_warn.call_args.args
    title_or_body = " ".join(str(a) for a in args)
    assert "Setup-Marker" in title_or_body
    assert "%APPDATA%" in title_or_body or "APPDATA" in title_or_body
    assert wizard.result() == int(SetupWizard.DialogCode.Accepted)


def test_setup_wizard_accept_does_not_swallow_keyboard_interrupt(qtbot, tmp_path, mocker):
    from kira.setup_wizard import SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch(
        "kira.setup_wizard.mark_first_run_complete",
        side_effect=KeyboardInterrupt(),
    )
    fake_warn = mocker.patch("kira.setup_wizard.QMessageBox.warning")

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)

    with pytest.raises(KeyboardInterrupt):
        wizard.accept()

    fake_warn.assert_not_called()


def test_whisper_worker_passes_allow_patterns_whitelist(qtbot, tmp_path, mocker):
    target = tmp_path / "whisper-model"
    fake_download = mocker.patch(
        "kira.setup_wizard.snapshot_download",
        return_value=str(target),
    )
    worker = WhisperDownloadWorker(target_dir=target)

    worker.run()

    fake_download.assert_called_once()
    kwargs = fake_download.call_args.kwargs
    assert "allow_patterns" in kwargs, \
        "snapshot_download muss allow_patterns kriegen (defense gegen rogue files in repo)"
    patterns = kwargs["allow_patterns"]
    assert isinstance(patterns, list), "allow_patterns muss list sein"
    assert len(patterns) > 0
    assert "model.bin" in patterns
    assert "config.json" in patterns
    assert "tokenizer.json" in patterns
    assert "*" not in patterns


def test_whisper_allowed_files_constant_locked():
    assert WHISPER_ALLOWED_FILES == (
        "model.bin",
        "config.json",
        "tokenizer.json",
        "vocabulary.json",
        "preprocessor_config.json",
        "*.txt",
    )


def test_whisper_worker_emits_error_when_mkdir_fails(qtbot, tmp_path, mocker):
    target = tmp_path / "whisper-model"
    fake_download = mocker.patch("kira.setup_wizard.snapshot_download")
    mocker.patch.object(
        Path,
        "mkdir",
        side_effect=PermissionError("ReadOnly Filesystem"),
    )

    worker = WhisperDownloadWorker(target_dir=target)
    errors: list[str] = []
    worker.error.connect(lambda msg: errors.append(msg))

    worker.run()

    fake_download.assert_not_called()
    assert len(errors) == 1
    assert "Whisper-Verzeichnis" in errors[0]
    assert "PermissionError" in errors[0] or "ReadOnly" in errors[0]


def test_has_model_tag_exact_match_only():
    stdout = (
        "NAME                ID    SIZE   MODIFIED\n"
        "gemma3:12b-instruct abc   8.1 GB now\n"
    )
    assert _has_model_tag(stdout, "gemma3:12b") is False
    assert _has_model_tag(stdout, "gemma3:12b-instruct") is True


def test_has_model_tag_finds_exact_tag():
    stdout = (
        "NAME                ID    SIZE   MODIFIED\n"
        "gemma3:12b          abc   8.1 GB now\n"
        "llama3:8b           xyz   4.7 GB last week\n"
    )
    assert _has_model_tag(stdout, "gemma3:12b") is True
    assert _has_model_tag(stdout, "llama3:8b") is True
    assert _has_model_tag(stdout, "phi3:14b") is False


def test_has_model_tag_handles_empty_lines():
    assert _has_model_tag("", "gemma3:12b") is False
    assert _has_model_tag("\n\n\n", "gemma3:12b") is False
    assert _has_model_tag("NAME ID SIZE\n", "gemma3:12b") is False


def test_gemma_worker_does_not_match_substring(qtbot, mocker):
    mocker.patch(
        "kira.setup_wizard.subprocess.run",
        return_value=MagicMock(
            returncode=0,
            stdout=(
                "NAME                ID    SIZE   MODIFIED\n"
                "gemma3:12b-instruct abc   8.1 GB now\n"
            ),
            stderr="",
        ),
    )
    client = _FakeClient([{"status": "success"}])
    _pull_with(mocker, client)

    worker = GemmaPullWorker(model_tag="gemma3:12b")
    worker.run()

    assert client.calls == [("gemma3:12b", True)]


def test_abort_pipeline_idempotent_under_race(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)

    spy_stop = mocker.patch.object(download_page, "_stop_all_workers")

    download_page._abort_pipeline()
    download_page._abort_pipeline()
    download_page._abort_pipeline()

    assert download_page._pipeline_aborted is True
    assert spy_stop.call_count == 1


def test_close_event_cleans_up_running_workers(qtbot, tmp_path, mocker):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QCloseEvent
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)

    spy_cleanup = mocker.patch.object(download_page, "cleanupPage")

    real_event = QCloseEvent()
    wizard.closeEvent(real_event)

    spy_cleanup.assert_called_once()


def test_setup_wizard_accept_handles_runtime_error_too(qtbot, tmp_path, mocker):
    from kira.setup_wizard import SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch(
        "kira.setup_wizard.mark_first_run_complete",
        side_effect=RuntimeError("legacy bug"),
    )
    fake_warn = mocker.patch("kira.setup_wizard.QMessageBox.warning")

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)

    wizard.accept()

    fake_warn.assert_called_once()


def test_append_log_escapes_html(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)

    download_page._append_log("<script>alert(1)</script>")

    log_text = download_page._log.toPlainText()
    assert "<script>" in log_text or "&lt;script&gt;" in download_page._log.toHtml()


def test_log_buffer_capped_at_500_blocks(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    whisper_target = tmp_path / "whisper"
    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()

    mocker.patch.object(DownloadPage, "initializePage", return_value=None)

    wizard = SetupWizard(
        whisper_target=whisper_target,
        ollama_installer=ollama_setup,
    )
    qtbot.addWidget(wizard)
    download_page = wizard.page(1)

    assert download_page._log.document().maximumBlockCount() == 500


def _page(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()
    mocker.patch.object(DownloadPage, "initializePage", return_value=None)
    wizard = SetupWizard(whisper_target=tmp_path / "whisper", ollama_installer=ollama_setup)
    qtbot.addWidget(wizard)
    return wizard, wizard.page(1)


def _bar_state(bar):
    return bar.minimum(), bar.maximum(), bar.value()


def test_whisper_worker_reports_bytes_through_the_hub_progress(qtbot, tmp_path, mocker):
    target = tmp_path / "whisper-model"

    def fake_download(**kwargs):
        bar = kwargs["tqdm_class"](desc="Downloading", total=0, initial=0, unit="B", unit_scale=True)
        bar.total += 3_000
        bar.refresh()
        for _ in range(3):
            bar.update(1_000)
        return str(target)

    mocker.patch("kira.setup_wizard.snapshot_download", side_effect=fake_download)
    worker = WhisperDownloadWorker(target_dir=target)
    seen: list[tuple[int, int]] = []
    finished: list[Path] = []
    worker.progress.connect(lambda done, total: seen.append((done, total)))
    worker.finished.connect(finished.append)

    worker.run()

    assert seen == [(0, 3_000), (3_000, 3_000)]
    assert finished == [target]


def test_whisper_cancel_stops_the_download_without_an_error(qtbot, tmp_path, mocker):
    worker = WhisperDownloadWorker(target_dir=tmp_path / "whisper-model")

    def fake_download(**kwargs):
        bar = kwargs["tqdm_class"](total=0, unit="B")
        bar.total += 10_000
        bar.update(1_000)
        worker.cancel()
        bar.update(1_000)
        raise AssertionError("Download lief nach dem Abbrechen weiter")

    mocker.patch("kira.setup_wizard.snapshot_download", side_effect=fake_download)
    errors: list[str] = []
    finished: list[Path] = []
    worker.error.connect(errors.append)
    worker.finished.connect(finished.append)

    worker.run()

    assert errors == [] and finished == []


def test_ollama_worker_names_its_phases(qtbot, tmp_path, mocker):
    installer = tmp_path / "OllamaSetup.exe"
    installer.touch()
    mocker.patch("kira.setup_wizard.is_ollama_installed", return_value=False)
    mocker.patch("kira.setup_wizard.is_ollama_reachable", side_effect=[False, True])
    fake_proc = MagicMock()
    fake_proc.wait.return_value = 0
    mocker.patch("kira.setup_wizard.subprocess.Popen", return_value=fake_proc)
    mocker.patch("kira.setup_wizard.time.sleep", return_value=None)
    worker = OllamaSetupWorker(installer_path=installer)
    texts: list[str] = []
    worker.status.connect(texts.append)

    worker.run()

    assert texts == ["wird installiert …", "wartet auf den Ollama-Dienst …", "bereit"]


def test_download_rows_wait_with_an_empty_bar(qtbot, tmp_path, mocker):
    _wizard, page = _page(qtbot, tmp_path, mocker)
    assert "nur, was noch fehlt" in page.subTitle()
    assert "verloren" not in page.subTitle()
    assert page._gemma_status.text() == "Gemma: wartet auf Ollama …"
    assert _bar_state(page._gemma_bar) == (0, 1, 0)
    assert _bar_state(page._whisper_bar) == (0, 1, 0)


def test_whisper_row_shows_bytes_and_percent(qtbot, tmp_path, mocker):
    _wizard, page = _page(qtbot, tmp_path, mocker)
    page._on_whisper_progress(1_200_000_000, 3_090_000_000)
    assert page._whisper_status.text() == "Whisper: 1,2 von 3,1 GB · 38 % · startet …"
    assert _bar_state(page._whisper_bar) == (0, 1000, 388)
    page._on_whisper_finished(tmp_path / "whisper")
    assert page._whisper_status.text() == "Whisper: fertig (whisper)"
    assert _bar_state(page._whisper_bar) == (0, 1, 1)


def test_gemma_row_runs_the_bar_in_phases_without_bytes(qtbot, tmp_path, mocker):
    _wizard, page = _page(qtbot, tmp_path, mocker)
    page._on_gemma_status("Bestand wird geprüft …")
    assert (page._gemma_bar.minimum(), page._gemma_bar.maximum()) == (0, 0)
    page._on_gemma_progress("pulling manifest", 0, 0)
    assert page._gemma_status.text() == "Gemma: startet …"
    page._on_gemma_progress("pulling aaa", 2_000_000_000, 8_000_000_000)
    assert page._gemma_status.text().startswith("Gemma: 2,0 von 8,0 GB · 25 %")
    page._on_gemma_progress("pulling aaa", 8_000_000_000, 8_000_000_000)
    assert (page._gemma_bar.minimum(), page._gemma_bar.maximum()) == (0, 0)
    page._on_gemma_progress("verifying sha256 digest", 0, 0)
    assert page._gemma_status.text() == "Gemma: Prüfsumme wird geprüft …"
    assert (page._gemma_bar.minimum(), page._gemma_bar.maximum()) == (0, 0)
    page._on_gemma_finished()
    assert _bar_state(page._gemma_bar) == (0, 1, 1)
    assert "[Gemma] Prüfsumme wird geprüft …" in page._log.toPlainText()


def test_error_stops_its_row_and_the_others_read_aborted(qtbot, tmp_path, mocker):
    _wizard, page = _page(qtbot, tmp_path, mocker)
    mocker.patch.object(page, "_stop_all_workers")
    page._on_whisper_progress(1_000_000_000, 3_000_000_000)
    page._on_ollama_status("wird installiert …")
    page._on_ollama_error("Installer Exit-Code 1")
    assert page._ollama_status.text() == "Ollama: FEHLER"
    assert _bar_state(page._ollama_bar) == (0, 1, 0)
    assert page._whisper_status.text() == "Whisper: abgebrochen"
    assert _bar_state(page._whisper_bar) == (0, 1, 0)
    assert page._gemma_status.text() == "Gemma: abgebrochen"
    page._on_whisper_progress(2_000_000_000, 3_000_000_000)
    assert page._whisper_status.text() == "Whisper: abgebrochen"


def test_initialize_page_starts_fresh_after_going_back(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()
    mocker.patch("kira.setup_wizard.WhisperDownloadWorker")
    mocker.patch("kira.setup_wizard.OllamaSetupWorker")
    wizard = SetupWizard(whisper_target=tmp_path / "whisper", ollama_installer=ollama_setup)
    qtbot.addWidget(wizard)
    page = wizard.page(1)
    assert isinstance(page, DownloadPage)
    page._pipeline_aborted = True
    page._whisper_done = True

    page.initializePage()

    assert page._pipeline_aborted is False
    assert page._whisper_done is False
    assert page._whisper_status.text() == "Whisper: startet …"
    assert (page._whisper_bar.minimum(), page._whisper_bar.maximum()) == (0, 0)


def test_whisper_row_waits_with_size_and_runtime_until_xet_delivers(qtbot, tmp_path, mocker):
    _wizard, page = _page(qtbot, tmp_path, mocker)
    page._on_whisper_progress(3_550_885, 3_090_835_702)
    assert page._whisper_status.text() == "Whisper: 3,1 GB · läuft seit 0:00"
    assert (page._whisper_bar.minimum(), page._whisper_bar.maximum()) == (0, 0)


def test_gemma_row_names_the_check_when_the_bytes_are_complete(qtbot, tmp_path, mocker):
    _wizard, page = _page(qtbot, tmp_path, mocker)
    page._on_gemma_progress("pulling aaa", 7_900_000_000, 8_021_618_941)
    page._on_gemma_progress("verifying sha256 digest", 8_021_618_941, 8_021_618_941)
    assert page._gemma_status.text() == "Gemma: Prüfsumme wird geprüft …"
    assert (page._gemma_bar.minimum(), page._gemma_bar.maximum()) == (0, 0)
    page._on_gemma_progress("writing manifest", 8_021_618_941, 8_021_618_941)
    assert page._gemma_status.text() == "Gemma: Modell wird eingetragen …"


def test_cleanup_stops_the_running_rows_and_marks_them_aborted(qtbot, tmp_path, mocker):
    _wizard, page = _page(qtbot, tmp_path, mocker)
    page._on_whisper_finished(tmp_path / "whisper")
    page._on_gemma_progress("pulling aaa", 1_000_000, 8_000_000_000)
    assert page._gemma_view._timer.isActive()

    page.cleanupPage()

    assert not page._gemma_view._timer.isActive()
    assert page._gemma_status.text() == "Gemma: abgebrochen"
    assert page._ollama_status.text() == "Ollama: abgebrochen"
    assert page._whisper_status.text() == "Whisper: fertig (whisper)"


def test_going_back_and_on_measures_the_rows_anew(qtbot, tmp_path, mocker):
    from kira.setup_wizard import DownloadPage, SetupWizard

    ollama_setup = tmp_path / "OllamaSetup.exe"
    ollama_setup.touch()
    mocker.patch("kira.setup_wizard.WhisperDownloadWorker")
    mocker.patch("kira.setup_wizard.OllamaSetupWorker")
    wizard = SetupWizard(whisper_target=tmp_path / "whisper", ollama_installer=ollama_setup)
    qtbot.addWidget(wizard)
    page = wizard.page(1)
    assert isinstance(page, DownloadPage)
    page.initializePage()
    page._on_whisper_progress(1_200_000_000, 3_090_000_000)
    first = page._whisper_view._meter

    page.cleanupPage()
    page.initializePage()

    assert page._whisper_view._meter is not first
    assert page._whisper_view._meter.elapsed() == 0.0


def _setup_worker(tmp_path, mocker, proc):
    installer = tmp_path / "OllamaSetup.exe"
    installer.touch()
    mocker.patch("kira.setup_wizard.is_ollama_installed", return_value=False)
    mocker.patch("kira.setup_wizard.is_ollama_reachable", side_effect=[False, True])
    mocker.patch("kira.setup_wizard.time.sleep", return_value=None)
    popen = mocker.patch("kira.setup_wizard.subprocess.Popen", return_value=proc)
    worker = OllamaSetupWorker(installer_path=installer)
    errors: list[str] = []
    finished: list[int] = []
    worker.error.connect(errors.append)
    worker.finished.connect(lambda: finished.append(1))
    return worker, popen, errors, finished


def test_ollama_setup_runs_without_pipes_and_waits_for_the_process(qtbot, tmp_path, mocker):
    import subprocess

    proc = MagicMock()
    proc.wait.return_value = 0
    worker, popen, errors, finished = _setup_worker(tmp_path, mocker, proc)

    worker.run()

    kwargs = popen.call_args.kwargs
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.DEVNULL
    proc.communicate.assert_not_called()
    proc.wait.assert_called_once_with(timeout=300)
    assert errors == [] and finished == [1]


def test_ollama_setup_timeout_kills_the_setup_and_says_so(qtbot, tmp_path, mocker):
    import subprocess

    proc = MagicMock()
    proc.wait.side_effect = subprocess.TimeoutExpired("OllamaSetup.exe", 300)
    worker, _popen, errors, finished = _setup_worker(tmp_path, mocker, proc)

    worker.run()

    proc.kill.assert_called_once()
    assert errors == ["Ollama-Installer Timeout (>300 s)."]
    assert finished == []


def test_ollama_setup_exit_code_is_reported_without_output_parts(qtbot, tmp_path, mocker):
    proc = MagicMock()
    proc.wait.return_value = 2
    worker, _popen, errors, finished = _setup_worker(tmp_path, mocker, proc)

    worker.run()

    assert errors == ["Ollama-Installer Exit-Code 2."]
    assert finished == []


def test_ollama_setup_cancel_stops_the_running_setup(qtbot, tmp_path, mocker):
    entered = threading.Event()
    stopped = threading.Event()
    proc = MagicMock()
    proc.poll.side_effect = lambda: 1 if stopped.is_set() else None
    proc.terminate.side_effect = stopped.set

    def wait(timeout=None):
        entered.set()
        return 1 if stopped.wait(3) else 0

    proc.wait.side_effect = wait
    proc.communicate.side_effect = lambda timeout=None: (wait(timeout), ("", ""))[1]
    worker, _popen, errors, finished = _setup_worker(tmp_path, mocker, proc)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    assert entered.wait(2)

    worker.cancel()
    thread.join(2)

    assert not thread.is_alive()
    proc.terminate.assert_called_once()
    qtbot.wait(50)
    assert errors == [] and finished == []


def test_ollama_setup_cancelled_while_it_starts_is_stopped_right_away(qtbot, tmp_path, mocker):
    proc = MagicMock()
    proc.poll.return_value = None
    proc.wait.return_value = 1
    proc.communicate.return_value = ("", "")
    worker, popen, errors, finished = _setup_worker(tmp_path, mocker, proc)

    def start(*args, **kwargs):
        worker.cancel()
        return proc

    popen.side_effect = start

    worker.run()

    proc.terminate.assert_called_once()
    assert errors == [] and finished == []
