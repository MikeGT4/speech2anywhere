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


def _transcribe_single_segment(monkeypatch, fake_config, text, no_speech_prob, peak):
    from kira.transcriber_fw import Transcriber

    class FakeInfo:
        language = "de"

    class FakeSegment:
        def __init__(self):
            self.text = text
            self.no_speech_prob = no_speech_prob
            self.avg_logprob = -0.3

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment()]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    audio = np.zeros(16000, dtype=np.float32)
    audio[8000] = peak
    return Transcriber(fake_config).transcribe(audio)


def test_spoken_thanks_with_confident_speech_is_kept(monkeypatch, fake_config):
    result = _transcribe_single_segment(monkeypatch, fake_config, "Danke!", 0.02, 0.6)
    assert result.text == "Danke!"


def test_thanks_on_silence_is_dropped_even_when_whisper_is_sure(monkeypatch, fake_config):
    result = _transcribe_single_segment(monkeypatch, fake_config, "Danke.", 0.02, 0.0002)
    assert result.text == ""


def test_thanks_with_unsure_speech_is_dropped(monkeypatch, fake_config):
    result = _transcribe_single_segment(monkeypatch, fake_config, "Vielen Dank.", 0.38, 0.3)
    assert result.text == ""


@pytest.mark.parametrize(("peak", "no_speech", "expected"), [
    (0.0001, 0.25, True),
    (0.0001, 0.01, True),
    (0.30, 0.38, True),
    (0.60, 0.02, False),
    (0.94, 0.10, False),
    (0.94, 0.11, True),
])
def test_hallucination_needs_silence_or_unsure_speech(peak, no_speech, expected):
    from kira.transcriber_fw import _is_hallucination
    assert _is_hallucination("Vielen Dank.", peak=peak, no_speech=no_speech) is expected


class _PartialSegment:
    def __init__(self, text, no_speech=0.05):
        self.text = text
        self.no_speech_prob = no_speech


def _partial_model(monkeypatch, segments, calls):
    class FakeInfo:
        language = "de"

    class FakeWhisperModel:
        def __init__(self, *a, **kw):
            pass

        def transcribe(self, audio, **kw):
            calls.append(kw)
            return iter(segments), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)


def test_partial_uses_fast_settings_and_returns_text(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber
    calls = []
    _partial_model(monkeypatch, [_PartialSegment(" Hallo "), _PartialSegment("Welt")], calls)
    t = Transcriber(fake_config)
    assert t.transcribe_partial(np.full(16000, 0.3, dtype=np.float32)) == "Hallo Welt"
    kw = calls[0]
    assert kw["beam_size"] == 1
    assert kw["condition_on_previous_text"] is False
    assert kw["without_timestamps"] is True
    assert kw.get("initial_prompt") is None


@pytest.mark.parametrize("segments", [
    [_PartialSegment("Hallo", no_speech=0.8)],
    [_PartialSegment("Vielen Dank.", no_speech=0.3)],
    [],
])
def test_partial_drops_silence_and_hallucinations(monkeypatch, fake_config, segments):
    from kira.transcriber_fw import Transcriber
    _partial_model(monkeypatch, segments, [])
    t = Transcriber(fake_config)
    assert t.transcribe_partial(np.full(16000, 0.3, dtype=np.float32)) == ""


def test_partial_with_empty_audio_skips_the_model(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber
    calls = []
    _partial_model(monkeypatch, [_PartialSegment("Hallo")], calls)
    t = Transcriber(fake_config)
    assert t.transcribe_partial(np.zeros(0, dtype=np.float32)) == ""
    assert calls == []


def test_partial_runs_keep_the_log_quiet_but_final_runs_still_log(monkeypatch, fake_config, caplog):
    import logging
    from kira.transcriber_fw import Transcriber

    class FakeInfo:
        language = "de"

    class FakeWhisperModel:
        def __init__(self, *a, **kw):
            pass

        def transcribe(self, audio, **kw):
            logging.getLogger("faster_whisper").info("Processing audio with duration %.1f", audio.size / 16000)
            return iter([_PartialSegment("Hallo")]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    t = Transcriber(fake_config)
    audio = np.full(16000, 0.3, dtype=np.float32)
    with caplog.at_level(logging.INFO, logger="faster_whisper"):
        t.transcribe_partial(audio)
        assert not [r for r in caplog.records if r.name == "faster_whisper"]
        t.transcribe(audio)
        assert [r for r in caplog.records if r.name == "faster_whisper"]


def _segment_model(ends):
    class FakeInfo:
        language = "de"
        duration = 120.0

    class FakeSegment:
        def __init__(self, end):
            self.text = f"Satz {end:.0f}"
            self.end = end

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass

        def transcribe(self, audio, **kw):
            return iter([FakeSegment(end) for end in ends]), FakeInfo()

    return FakeWhisperModel


def test_transcribe_file_reports_progress_by_audio_time(monkeypatch, fake_config):
    from kira.transcriber_fw import Transcriber

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", _segment_model([30.0, 60.0, 90.0]))
    t = Transcriber(fake_config)
    assert not t.model_loaded
    seen = []
    result = t.transcribe_file("/tmp/a.wav", on_progress=lambda done, total: seen.append((done, total)))
    assert t.model_loaded
    assert seen == [(0.0, 0.0), (0.0, 120.0), (30.0, 120.0), (60.0, 120.0), (90.0, 120.0)]
    assert result.text == "Satz 30 Satz 60 Satz 90"


def test_transcribe_file_stops_between_segments_when_cancelled(monkeypatch, fake_config, caplog):
    from kira.progress import Cancelled
    from kira.transcriber_fw import Transcriber

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", _segment_model([30.0, 60.0, 90.0]))
    t = Transcriber(fake_config)
    seen = []
    with caplog.at_level("INFO"), pytest.raises(Cancelled):
        t.transcribe_file("/tmp/a.wav", on_progress=lambda done, total: seen.append(done),
                          cancelled=lambda: len(seen) >= 3)
    assert seen == [0.0, 0.0, 30.0]
    assert "File transcription cancelled" in caplog.text
    assert "File transcription failed" not in caplog.text


def _language_seen_by_model(monkeypatch, fake_config, language, supported, call=None):
    from kira.transcriber_fw import Transcriber
    seen = {}

    class FakeInfo:
        language = "de"
        duration = 1.0

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            seen["language"] = kw.get("language", "SENTINEL")
            return iter([]), FakeInfo()

    if supported is not None:
        FakeWhisperModel.supported_languages = supported
    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    fake_config.whisper.language = language
    transcriber = Transcriber(fake_config)
    if call is None:
        transcriber.transcribe(np.ones(1600, dtype=np.float32))
    else:
        call(transcriber)
    return seen["language"]


def test_language_the_model_knows_is_passed_on(monkeypatch, fake_config):
    assert _language_seen_by_model(monkeypatch, fake_config, "fr", ["de", "en", "fr"]) == "fr"


def test_language_the_model_lacks_falls_back_to_detection(monkeypatch, fake_config, caplog):
    assert _language_seen_by_model(monkeypatch, fake_config, "xx", ["de", "en"]) is None
    assert "xx" in caplog.text


def test_language_is_passed_on_when_the_model_lists_none(monkeypatch, fake_config):
    assert _language_seen_by_model(monkeypatch, fake_config, "fr", None) == "fr"


def test_file_transcription_uses_the_same_language_fallback(monkeypatch, fake_config):
    seen = _language_seen_by_model(
        monkeypatch, fake_config, "xx", ["de", "en"], call=lambda t: t.transcribe_file("datei.wav"),
    )
    assert seen is None


def test_live_words_use_the_same_language_fallback(monkeypatch, fake_config):
    seen = _language_seen_by_model(
        monkeypatch, fake_config, "xx", ["de", "en"],
        call=lambda t: t.transcribe_partial(np.ones(1600, dtype=np.float32)),
    )
    assert seen is None


def _file_result(monkeypatch, fake_config, segments):
    from kira.transcriber_fw import Transcriber

    class FakeInfo:
        language = "de"
        duration = 9.0

    class FakeSegment:
        def __init__(self, start, end, text):
            self.start, self.end, self.text = start, end, text

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment(*segment) for segment in segments]), FakeInfo()

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    return Transcriber(fake_config).transcribe_file("datei.wav")


def test_file_transcription_keeps_start_end_and_text_of_each_segment(monkeypatch, fake_config):
    result = _file_result(monkeypatch, fake_config, [(0.0, 2.5, " Hallo Welt."), (2.5, 5.0, " Zweiter Satz.")])
    assert result.text == "Hallo Welt. Zweiter Satz."
    assert result.segments == [(0.0, 2.5, "Hallo Welt."), (2.5, 5.0, "Zweiter Satz.")]


def test_file_segments_leave_out_hallucinations_and_carry_replacements(monkeypatch, fake_config):
    fake_config.whisper.replacements = {"kuh bernetes": "Kubernetes"}
    result = _file_result(monkeypatch, fake_config, [
        (0.0, 2.0, " Wir deployen auf kuh bernetes."), (2.0, 4.0, " Vielen Dank."), (4.0, 6.0, " Fertig."),
    ])
    assert result.segments == [(0.0, 2.0, "Wir deployen auf Kubernetes."), (4.0, 6.0, "Fertig.")]


def test_dictation_result_carries_no_segments(monkeypatch, fake_config):
    from kira.transcriber_fw import TranscriptionResult
    assert TranscriptionResult(text="Hallo", language="de").segments is None


def _dictation_result(monkeypatch, fake_config, info):
    from kira.transcriber_fw import Transcriber

    class FakeSegment:
        text = " Hallo Welt."
        no_speech_prob = 0.01
        avg_logprob = -0.2

    class FakeWhisperModel:
        def __init__(self, *a, **kw): pass
        def transcribe(self, audio, **kw):
            return iter([FakeSegment()]), info

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    return Transcriber(fake_config).transcribe(np.ones(16000, dtype=np.float32))


def test_dictation_result_carries_the_certainty_of_the_detected_language(monkeypatch, fake_config):
    class Info:
        language = "nl"
        language_probability = 0.83

    result = _dictation_result(monkeypatch, fake_config, Info())
    assert (result.language, result.language_probability) == ("nl", 0.83)


def test_dictation_result_without_a_certainty_says_so(monkeypatch, fake_config):
    class Info:
        language = "nl"

    assert _dictation_result(monkeypatch, fake_config, Info()).language_probability is None


def _loaded_with(monkeypatch, whisper):
    from kira.config import Config
    from kira.transcriber_fw import Transcriber
    seen = {}

    class FakeWhisperModel:
        def __init__(self, name, **kw):
            seen.update(kw, name=name)

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    Transcriber(Config.model_validate({"whisper": whisper}))._ensure_model()
    return seen


def test_cpu_device_loads_the_processor_model_with_int8(monkeypatch):
    from kira.transcriber_fw import cpu_threads
    seen = _loaded_with(monkeypatch, {"model": "large-v3", "device": "cpu", "cpu_model": "C:/m/faster-whisper-small"})
    assert seen["name"] == "C:/m/faster-whisper-small"
    assert seen["device"] == "cpu"
    assert seen["compute_type"] == "int8"
    assert seen["cpu_threads"] == cpu_threads()


def test_gpu_device_keeps_cuda_with_float16(monkeypatch):
    seen = _loaded_with(monkeypatch, {"model": "large-v3", "cpu_model": "small"})
    assert seen["name"] == "large-v3"
    assert seen["device"] == "cuda"
    assert seen["compute_type"] == "float16"


@pytest.mark.parametrize("count, expected", [(16, 8), (32, 8), (8, 4), (4, 2), (1, 1), (None, 1)])
def test_cpu_threads_uses_half_the_logical_cores_up_to_eight(monkeypatch, count, expected):
    from kira import transcriber_fw
    monkeypatch.setattr(transcriber_fw.os, "cpu_count", lambda: count)
    assert transcriber_fw.cpu_threads() == expected


def test_gpu_model_follows_a_changed_config(monkeypatch):
    from kira.config import Config
    from kira.transcriber_fw import Transcriber
    seen = {}

    class FakeWhisperModel:
        def __init__(self, name, **kw):
            seen["name"] = name

    monkeypatch.setattr("kira.transcriber_fw.WhisperModel", FakeWhisperModel)
    cfg = Config.model_validate({"whisper": {"model": "large-v3"}})
    transcriber = Transcriber(cfg)
    cfg.whisper.model = "C:/m/faster-whisper-large-v3"
    transcriber._ensure_model()
    assert seen["name"] == "C:/m/faster-whisper-large-v3"
