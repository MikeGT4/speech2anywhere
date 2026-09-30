from __future__ import annotations
import sys
import numpy as np
import pytest

if sys.platform != "win32":
    pytest.skip("windows-only tests", allow_module_level=True)


@pytest.fixture
def fake_config():
    from kira.config import Config, WhisperConfig
    cfg = Config()
    cfg.whisper = WhisperConfig(model="large-v3", language="auto")
    return cfg


def test_transcriber_fw_init_lazy(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber
    called = {"n": 0}

    class FakeWhisperModel:
        def __init__(self, *a, **kw):
            called["n"] += 1

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    assert called["n"] == 0, "model should not load on init"


def test_transcribe_empty_audio_returns_empty(fake_config):
    from kira.transcriber_fw import Transcriber
    t = Transcriber(fake_config)
    result = t.transcribe(np.zeros(0, dtype=np.float32))
    assert result.text == ""
    assert result.language == ""


def test_transcribe_calls_model_and_joins_segments(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber, TranscriptionResult

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment("Hallo "), FakeSegment("Welt")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    audio = np.ones(16000, dtype=np.float32) * 0.1
    result = t.transcribe(audio)
    assert result.text == "Hallo Welt"
    assert result.language == "de"


def test_transcribe_respects_explicit_language(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    seen_lang = {"val": None}

    class FakeInfo:
        language = "en"

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            seen_lang["val"] = kw.get("language")
            return iter([]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    fake_config.whisper.language = "en"
    t = Transcriber(fake_config)
    audio = np.ones(1600, dtype=np.float32)
    t.transcribe(audio)
    assert seen_lang["val"] == "en"


def test_transcribe_auto_language_passes_none(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    seen_lang = {"val": "SENTINEL"}

    class FakeInfo:
        language = "de"

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            seen_lang["val"] = kw.get("language", "SENTINEL")
            return iter([]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    fake_config.whisper.language = "auto"
    t = Transcriber(fake_config)
    audio = np.ones(1600, dtype=np.float32)
    t.transcribe(audio)
    assert seen_lang["val"] is None


def test_mlx_model_name_translated_to_faster_whisper(fake_config):
    from kira.config import WhisperConfig
    from kira.transcriber_fw import Transcriber
    fake_config.whisper = WhisperConfig(model="mlx-community/whisper-large-v3-turbo", language="auto")
    t = Transcriber(fake_config)
    assert t._model_name == "large-v3-turbo"


def test_non_mlx_model_name_unchanged(fake_config):
    from kira.transcriber_fw import Transcriber
    t = Transcriber(fake_config)
    assert t._model_name == "large-v3"


def test_transcribe_passes_whisper_tuning_kwargs(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    seen: dict = {}

    class FakeInfo:
        language = "de"

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            seen.update(kw)
            return iter([]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    fake_config.whisper.condition_on_previous_text = False
    fake_config.whisper.initial_prompt = "Ollama Whisper Python"
    t = Transcriber(fake_config)
    t.transcribe(np.ones(1600, dtype=np.float32))

    assert seen["beam_size"] == 5
    assert seen["vad_filter"] is False
    assert "vad_parameters" not in seen
    assert seen["no_speech_threshold"] == 0.9
    assert seen["compression_ratio_threshold"] == 2.0
    assert seen["temperature"] == 0.0
    assert seen["condition_on_previous_text"] is False
    assert seen["initial_prompt"] == "Ollama Whisper Python"


def test_known_hallucination_returns_empty_text(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment("Vielen Dank.")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    result = t.transcribe(np.ones(16000, dtype=np.float32))
    assert result.text == ""
    assert result.language == "de"


def test_legitimate_speech_containing_thanks_passes_through(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment("Vielen Dank für deine schnelle Hilfe.")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    result = t.transcribe(np.ones(16000, dtype=np.float32))
    assert "Vielen Dank für deine schnelle Hilfe" in result.text


def test_hallucination_match_is_case_insensitive(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment("VIELEN DANK.")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    result = t.transcribe(np.ones(16000, dtype=np.float32))
    assert result.text == ""


def test_warmup_loads_model_eagerly(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    load_count = {"n": 0}

    class FakeWhisperModel:
        def __init__(self, *a, **kw):
            load_count["n"] += 1

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    assert load_count["n"] == 0, "construction must stay lazy"
    t.warmup()
    assert load_count["n"] == 1, "warmup must trigger model load"
    t.warmup()
    assert load_count["n"] == 1, "second warmup must reuse cached model"


def test_warmup_swallows_exceptions(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    class FailingWhisperModel:
        def __init__(self, *a, **kw):
            raise RuntimeError("simulated CUDA OOM during boot")

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FailingWhisperModel)
    t = Transcriber(fake_config)
    t.warmup()


def test_transcribe_file_uses_quality_settings(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    seen: dict = {}
    seen_path = {"val": None}

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            seen_path["val"] = audio
            seen.update(kw)
            return iter([FakeSegment("Hallo Welt")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    result = t.transcribe_file("C:\\Users\\user\\test.mp4")

    assert result.text == "Hallo Welt"
    assert result.language == "de"
    assert seen_path["val"] == "C:\\Users\\user\\test.mp4"
    assert seen["beam_size"] == 5, "File-Mode soll beam_size=5 nutzen"
    assert seen["vad_filter"] is True, "File-Mode soll Silero-VAD nutzen"


def test_transcribe_file_respects_condition_on_previous_text(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    seen: dict = {}

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            seen.update(kw)
            return iter([FakeSegment("Hallo Welt")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)

    fake_config.whisper.condition_on_previous_text = True
    t.transcribe_file("/tmp/a.wav")
    assert seen["condition_on_previous_text"] is True

    fake_config.whisper.condition_on_previous_text = False
    t.transcribe_file("/tmp/b.wav")
    assert seen["condition_on_previous_text"] is False


def test_transcribe_file_applies_replacements(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment("Deployment auf kuh bernetes gestartet")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    fake_config.whisper.replacements = {"kuh bernetes": "Kubernetes"}
    t = Transcriber(fake_config)
    result = t.transcribe_file("/tmp/test.wav")
    assert "Kubernetes" in result.text
    assert "kuh bernetes" not in result.text


def test_transcribe_file_propagates_exceptions(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            raise RuntimeError("ffmpeg: invalid data found")

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    with pytest.raises(RuntimeError, match="invalid data"):
        t.transcribe_file("/tmp/broken.mp4")


def test_ensure_model_is_thread_safe(monkeypatch, fake_config):
    import threading
    from kira.transcriber_fw import Transcriber

    call_count = {"n": 0}
    barrier = threading.Barrier(3)

    class FakeInfo:
        language = "de"

    class SlowFakeWhisperModel:
        def __init__(self, *a, **kw):
            import time
            time.sleep(0.05)
            call_count["n"] += 1

        def transcribe(self, audio, **kw):
            return iter([]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", SlowFakeWhisperModel)
    t = Transcriber(fake_config)
    audio = np.ones(1600, dtype=np.float32)

    def worker():
        barrier.wait(timeout=5)
        t.transcribe(audio)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=10)

    assert call_count["n"] == 1, f"WhisperModel constructed {call_count['n']} times, expected 1"


def test_transcribe_file_passes_vad_threshold(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    seen: dict = {}

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self, text): self.text = text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            seen.update(kw)
            return iter([FakeSegment("Hallo Welt")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)

    fake_config.whisper.vad_threshold = 0.15
    t.transcribe_file("/tmp/a.wav")
    assert seen["vad_parameters"] == {"threshold": 0.15}

    fake_config.whisper.vad_threshold = 0.4
    t.transcribe_file("/tmp/b.wav")
    assert seen["vad_parameters"] == {"threshold": 0.4}


class _FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        class _Encoding:
            pass
        enc = _Encoding()
        enc.ids = text.split()
        return enc


class _FakeLexicon:
    def __init__(self, terms, replacements, version=1):
        self._terms = terms
        self._replacements = replacements
        self.version = version
        self.term_calls = 0

    def vocabulary_terms(self):
        self.term_calls += 1
        return list(self._terms)

    def active_replacements(self):
        return dict(self._replacements)


def _model_capturing(seen, segments=()):
    class FakeInfo:
        language = "de"

    class FakeWhisperModel:
        def __init__(self, *a, **kw):
            self.hf_tokenizer = _FakeTokenizer()

        def transcribe(self, audio, **kw):
            seen.update(kw)
            return iter(list(segments)), FakeInfo()

    return FakeWhisperModel


def test_learned_terms_extend_initial_prompt(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber
    seen: dict = {}
    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", _model_capturing(seen))
    fake_config.whisper.initial_prompt = "Linux Kira Ollama"
    t = Transcriber(fake_config)
    t.set_lexicon(_FakeLexicon(["Zettelkasten"], {}))
    t.transcribe(np.ones(1600, dtype=np.float32))
    assert seen["initial_prompt"] == "Linux Kira Ollama, Zettelkasten."


def test_prompt_is_rebuilt_only_when_lexicon_changes(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber
    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", _model_capturing({}))
    lexicon = _FakeLexicon(["Zettelkasten"], {})
    t = Transcriber(fake_config)
    t.set_lexicon(lexicon)
    t.transcribe(np.ones(1600, dtype=np.float32))
    t.transcribe(np.ones(1600, dtype=np.float32))
    assert lexicon.term_calls == 1
    lexicon.version = 2
    t.transcribe(np.ones(1600, dtype=np.float32))
    assert lexicon.term_calls == 2


def test_learned_replacements_apply_and_manual_entries_win(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    class FakeSegment:
        def __init__(self, text):
            self.text = text
            self.avg_logprob = -0.4
            self.no_speech_prob = 0.1

    seen: dict = {}
    monkeypatch.setattr(
        "kira.transcriber_fw.WhisperModel",
        _model_capturing(seen, [FakeSegment("start auf kuh bernetes mit doku")]),
    )
    fake_config.whisper.replacements = {"doku": "Docker"}
    t = Transcriber(fake_config)
    t.set_lexicon(_FakeLexicon([], {"kuh bernetes": "Kubernetes", "doku": "Dokumentation"}))
    result = t.transcribe(np.ones(1600, dtype=np.float32))
    assert result.text == "start auf Kubernetes mit Docker"
    assert result.raw_text == "start auf kuh bernetes mit doku"
    assert result.avg_logprob == -0.4


def test_each_applied_replacement_is_logged(monkeypatch, fake_config, caplog):
    import logging
    from kira.transcriber_fw import Transcriber

    class FakeSegment:
        def __init__(self, text):
            self.text = text

    monkeypatch.setattr(
        "kira.transcriber_fw.WhisperModel",
        _model_capturing({}, [FakeSegment("start auf kuh bernetes")]),
    )
    fake_config.whisper.replacements = {"kuh bernetes": "Kubernetes"}
    t = Transcriber(fake_config)
    with caplog.at_level(logging.INFO, logger="kira.transcriber_fw"):
        t.transcribe(np.ones(1600, dtype=np.float32))
    assert "Ersetzung: 'kuh bernetes' -> 'Kubernetes'" in caplog.text


class _BrokenLexicon:
    version = 1

    def vocabulary_terms(self):
        raise TypeError("bad operand type for unary -: 'str'")

    def active_replacements(self):
        raise AttributeError("'NoneType' object has no attribute 'casefold'")


def test_broken_lexicon_falls_back_to_config(monkeypatch, fake_config, caplog):
    import logging
    from kira.transcriber_fw import Transcriber

    class FakeSegment:
        def __init__(self, text):
            self.text = text

    seen: dict = {}
    monkeypatch.setattr(
        "kira.transcriber_fw.WhisperModel",
        _model_capturing(seen, [FakeSegment("start auf kuh bernetes")]),
    )
    fake_config.whisper.initial_prompt = "Kira Ollama"
    fake_config.whisper.replacements = {"kuh bernetes": "Kubernetes"}
    t = Transcriber(fake_config)
    t.set_lexicon(_BrokenLexicon())
    with caplog.at_level(logging.WARNING, logger="kira.transcriber_fw"):
        results = [t.transcribe(np.ones(1600, dtype=np.float32)) for _ in range(2)]
    assert seen["initial_prompt"] == "Kira Ollama"
    assert [r.text for r in results] == ["start auf Kubernetes"] * 2
    warnings = [r.getMessage() for r in caplog.records
                if "gelernte Begriffe nicht nutzbar" in r.getMessage()]
    assert len(warnings) == 2
    assert "TypeError" in warnings[0] and "AttributeError" in warnings[1]


@pytest.mark.parametrize(("text", "expected"), [
    ("Vielen Dank für's Zuschauen", True),
    ("Vielen Dank fürs Zuschauen!", True),
    ("  VIELEN DANK FÜR’S ZUSCHAUEN.  ", True),
    ("Untertitel im Auftrag des ZDF für Funk 2017", True),
    ("Vielen Dank für deine Hilfe.", False),
    ("Vielen Dank fürs Zuschauen, und jetzt zum Thema", False),
    ("", False),
])
def test_hallucination_match_ignores_apostrophes_and_punctuation(text, expected):
    from kira.transcriber_fw import _is_hallucination
    assert _is_hallucination(text) is expected
