# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import asyncio
import numpy as np
from kira.app import KiraApp, State, TranscriptionResult, _StubInjector, _StubTranscriber
from kira.config import Config
from kira.recorder import Recorder


class FakeLearning:
    def __init__(self, glossary=None, fail=False):
        self.glossary = glossary or []
        self.fail = fail
        self.records = []
        self.glossary_calls = []

    def glossary_for(self, text):
        self.glossary_calls.append(text)
        if self.fail:
            raise RuntimeError("kaputt")
        return self.glossary

    def after_inject(self, *, mode, transcription, text, duration_s):
        if self.fail:
            raise RuntimeError("kaputt")
        self.records.append((mode, transcription.text, text, duration_s))


class RecordingStyler:
    def __init__(self):
        self.calls = []
        self.edits = []

    async def polish(self, text, mode, glossary=None):
        self.calls.append((text, mode, glossary))
        return text.upper()

    async def edit_command(self, selection, command):
        self.edits.append((selection, command))
        return selection.upper()


class KeywordStyler:
    def __init__(self):
        self.kwargs = []

    async def polish(self, text, mode, **kwargs):
        self.kwargs.append(kwargs)
        return text


def _app(learning, styler):
    return KiraApp(config=Config(), recorder=Recorder(), transcriber=_StubTranscriber(),
                   styler=styler, injector=_StubInjector(), learning=learning)


def test_glossary_reaches_styler_and_dictation_is_recorded(monkeypatch):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "terminal")
    learning = FakeLearning(glossary=["Zettelkasten"])
    styler = RecordingStyler()
    app = _app(learning, styler)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert styler.calls == [("stub", "terminal", ["Zettelkasten"])]
    assert learning.records == [("terminal", "stub", "STUB", 1.0)]
    assert app._injector.last == "STUB"
    assert app.state == State.IDLE


def test_failing_learning_never_breaks_dictation(monkeypatch):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    styler = RecordingStyler()
    app = _app(FakeLearning(fail=True), styler)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert styler.calls == [("stub", "plain", None)]
    assert app._injector.last == "STUB"
    assert app.state == State.IDLE


def test_without_learning_polish_gets_no_glossary(monkeypatch):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    styler = RecordingStyler()
    app = _app(None, styler)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert styler.calls == [("stub", "plain", None)]


def test_edit_path_skips_glossary_and_history(monkeypatch):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    learning = FakeLearning(glossary=["Zettelkasten"])
    styler = RecordingStyler()
    app = _app(learning, styler)
    app._edit_mode = True
    app._captured_selection = "markierter Text"
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert styler.edits == [("markierter Text", "stub")]
    assert styler.calls == []
    assert learning.glossary_calls == []
    assert learning.records == []
    assert app._injector.last == "MARKIERTER TEXT"


def test_empty_glossary_reaches_polish_without_the_parameter(monkeypatch):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    learning = FakeLearning(glossary=[])
    styler = KeywordStyler()
    app = _app(learning, styler)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert learning.glossary_calls == ["stub"]
    assert styler.kwargs == [{}]


class _TranscriberIn:
    def __init__(self, language, probability=None):
        self.language = language
        self.probability = probability

    def transcribe(self, audio):
        return TranscriptionResult(text="stub", language=self.language, language_probability=self.probability)


def _polish_kwargs(monkeypatch, language, probability=None):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    styler = KeywordStyler()
    app = KiraApp(config=Config(), recorder=Recorder(), transcriber=_TranscriberIn(language, probability),
                  styler=styler, injector=_StubInjector(), learning=None)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    return styler.kwargs


def test_confidently_detected_foreign_language_reaches_polish(monkeypatch):
    assert _polish_kwargs(monkeypatch, "nl", 0.97) == [{"language": "nl"}]
    assert _polish_kwargs(monkeypatch, "nl", 1.0) == [{"language": "nl"}]


def test_uncertain_foreign_language_reaches_polish_without_the_parameter(monkeypatch):
    assert _polish_kwargs(monkeypatch, "nl", 0.62) == [{}]
    assert _polish_kwargs(monkeypatch, "nl", None) == [{}]


def test_german_and_undetected_language_reach_polish_without_the_parameter(monkeypatch):
    assert _polish_kwargs(monkeypatch, "de") == [{}]
    assert _polish_kwargs(monkeypatch, "") == [{}]
