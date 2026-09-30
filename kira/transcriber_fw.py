from __future__ import annotations
import logging
import re
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

_DLL_HANDLES: list = []

if sys.platform == "win32":
    import site
    _dll_dirs = []
    for _sp in site.getsitepackages():
        _nvidia_base = os.path.join(_sp, "nvidia")
        if os.path.isdir(_nvidia_base):
            for _subdir in ("cublas", "cudnn"):
                _dll_dir = os.path.join(_nvidia_base, _subdir, "bin")
                if os.path.isdir(_dll_dir):
                    _dll_dirs.append(_dll_dir)
                    _DLL_HANDLES.append(os.add_dll_directory(_dll_dir))
    if _dll_dirs:
        os.environ["PATH"] = os.pathsep.join(_dll_dirs) + os.pathsep + os.environ.get("PATH", "")

import numpy as np
from faster_whisper import WhisperModel
from kira.config import Config
from kira import replacements
from kira.lexicon import build_initial_prompt

log = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    language: str
    raw_text: str = ""
    avg_logprob: float | None = None


_MLX_PREFIX = "mlx-community/whisper-"

_KNOWN_HALLUCINATIONS = frozenset({
    "vielen dank.",
    "vielen dank",
    "vielen dank fürs zuschauen.",
    "vielen dank für die aufmerksamkeit.",
    "vielen dank für ihr interesse.",
    "vielen dank für eure aufmerksamkeit.",
    "tschüss.",
    "tschüss",
    "danke.",
    "danke",
    "thank you.",
    "thank you",
    "thanks for watching.",
    "thanks for watching",
    "untertitel im auftrag des zdf.",
    "untertitel im auftrag des zdf für funk, 2017",
    "untertitel der amara.org-community",
    "untertitelung aufgrund der amara.org-community",
    "untertitelung des zdf, 2020",
    "untertitel von stephanie geiges",
    "© zdf 2024",
    "subtitles by the amara.org community",
})


_NOT_WORDS = re.compile(r"[^\w\s]")


def _normalized(text: str) -> str:
    return " ".join(_NOT_WORDS.sub("", text.lower()).split())


_NORMALIZED_HALLUCINATIONS = frozenset(_normalized(entry) for entry in _KNOWN_HALLUCINATIONS)


def _is_hallucination(text: str) -> bool:
    if not text:
        return False
    return _normalized(text) in _NORMALIZED_HALLUCINATIONS


def _log_replacement(found: str, replacement: str) -> None:
    log.info("Ersetzung: %r -> %r", found, replacement)


def _translate_model_name(name: str) -> str:
    if name.startswith(_MLX_PREFIX):
        return name[len(_MLX_PREFIX):]
    return name


class Transcriber:
    def __init__(self, config: Config):
        self._config = config
        original = config.whisper.model
        self._model_name = _translate_model_name(original)
        if self._model_name != original:
            log.info("Translated MLX model %s -> %s for faster-whisper", original, self._model_name)
        self._model: WhisperModel | None = None
        self._model_lock = threading.Lock()
        self._lexicon = None
        self._prompt_cache: tuple[int | None, str | None] = (None, None)
        self._lexicon_errors: set[str] = set()

    def _ensure_model(self) -> WhisperModel:
        with self._model_lock:
            if self._model is None:
                log.info("Loading faster-whisper model %s on CUDA", self._model_name)
                self._model = WhisperModel(
                    self._model_name,
                    device="cuda",
                    compute_type="float16",
                    download_root=str(Path.home() / ".cache" / "faster-whisper"),
                )
            return self._model

    def warmup(self) -> None:
        try:
            self._ensure_model()
            log.info(
                "Transcriber warmup complete (model=%s)", self._model_name,
            )
        except Exception:
            log.warning(
                "Transcriber warmup failed, first F8 will pay the "
                "cold-start cost. Non-fatal.",
                exc_info=True,
            )

    def set_lexicon(self, lexicon) -> None:
        self._lexicon = lexicon
        self._prompt_cache = (None, None)

    def _lexicon_failed(self, exc: Exception) -> None:
        kind = type(exc).__name__
        if kind in self._lexicon_errors:
            return
        self._lexicon_errors.add(kind)
        log.warning(
            "Lernen: gelernte Begriffe nicht nutzbar (%s: %s), "
            "Whisper nimmt die Werte aus config.yaml", kind, exc,
        )

    def _initial_prompt(self, model) -> str | None:
        base = self._config.whisper.initial_prompt
        lexicon = self._lexicon
        if lexicon is None:
            return base
        try:
            version = lexicon.version
            if self._prompt_cache[0] == version:
                return self._prompt_cache[1]
            tokenizer = getattr(model, "hf_tokenizer", None)

            def count_tokens(text: str) -> int:
                if tokenizer is None:
                    return len(text) // 2
                return len(tokenizer.encode(" " + text, add_special_tokens=False).ids)

            prompt = build_initial_prompt(base, lexicon.vocabulary_terms(), count_tokens)
            self._prompt_cache = (version, prompt)
            if prompt != base:
                log.info("Whisper-Prompt mit gelernten Begriffen: %d Token", count_tokens(prompt or ""))
            return prompt
        except Exception as exc:
            self._lexicon_failed(exc)
            return base

    def _replacements(self) -> dict[str, str]:
        manual = self._config.whisper.replacements
        if self._lexicon is None:
            return manual
        try:
            return {**self._lexicon.active_replacements(), **manual}
        except Exception as exc:
            self._lexicon_failed(exc)
            return manual

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        if audio.size == 0:
            return TranscriptionResult(text="", language="")
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        model = self._ensure_model()
        wcfg = self._config.whisper
        lang = wcfg.language
        try:
            segments, info = model.transcribe(
                audio,
                language=None if lang == "auto" else lang,
                beam_size=5,
                vad_filter=False,
                condition_on_previous_text=wcfg.condition_on_previous_text,
                initial_prompt=self._initial_prompt(model),
                no_speech_threshold=0.9,
                compression_ratio_threshold=2.0,
                temperature=0.0,
            )
            seg_list = list(segments)
            if seg_list:
                stats = " ".join(
                    f"[no_speech={getattr(s, 'no_speech_prob', 0.0):.2f} "
                    f"avg_logp={getattr(s, 'avg_logprob', 0.0):.2f}]"
                    for s in seg_list
                )
                log.info(
                    "Whisper %d segment(s): %s",
                    len(seg_list), stats,
                )
            else:
                log.info("Whisper produced 0 segments (silence?)")
            text = " ".join(s.text.strip() for s in seg_list).strip()
            raw_text = text
            logprobs = [getattr(s, "avg_logprob", None) for s in seg_list]
            logprobs = [lp for lp in logprobs if lp is not None]
            min_logprob = min(logprobs) if logprobs else None
            if _is_hallucination(text):
                log.warning(
                    "Whisper hallucination filter caught %r, pipeline "
                    "will abort before polish",
                    text,
                )
                return TranscriptionResult(text="", language=info.language)
            mapping = self._replacements()
            if mapping:
                fixed = replacements.apply(text, mapping, on_replace=_log_replacement)
                if fixed != text:
                    log.info(
                        "Replacements changed transcription "
                        "(map_size=%d, before=%d chars, after=%d chars)",
                        len(mapping), len(text), len(fixed),
                    )
                    text = fixed
            return TranscriptionResult(
                text=text, language=info.language,
                raw_text=raw_text, avg_logprob=min_logprob,
            )
        except Exception as exc:
            log.exception("faster-whisper transcription failed: %s", exc)
            raise

    def transcribe_file(self, path: str) -> TranscriptionResult:
        model = self._ensure_model()
        wcfg = self._config.whisper
        lang = wcfg.language
        log.info("Transcribing file: %s (lang=%s)", path, lang)
        try:
            segments, info = model.transcribe(
                str(path),
                language=None if lang == "auto" else lang,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"threshold": wcfg.vad_threshold},
                condition_on_previous_text=wcfg.condition_on_previous_text,
                initial_prompt=self._initial_prompt(model),
            )
            kept_segments = []
            dropped = 0
            for seg in segments:
                seg_text = seg.text.strip()
                if _is_hallucination(seg_text):
                    dropped += 1
                    log.info(
                        "File-mode dropped halluzinated segment: %r",
                        seg_text,
                    )
                    continue
                if seg_text:
                    kept_segments.append(seg_text)
            text = " ".join(kept_segments).strip()
            if dropped:
                log.info("File-mode: %d Segmente als Halluzination gefiltert", dropped)
            mapping = self._replacements()
            if mapping:
                fixed = replacements.apply(text, mapping, on_replace=_log_replacement)
                if fixed != text:
                    log.info(
                        "File-Replacements: %d chars -> %d chars",
                        len(text), len(fixed),
                    )
                    text = fixed
            log.info(
                "File transcribed: %d kept seg(s), %d chars, lang=%s",
                len(kept_segments), len(text), info.language,
            )
            return TranscriptionResult(text=text, language=info.language)
        except Exception:
            log.exception("File transcription failed: %s", path)
            raise
