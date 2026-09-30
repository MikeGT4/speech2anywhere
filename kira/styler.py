from __future__ import annotations
import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Callable
import ollama
from kira.config import Config, ModeConfig
from kira.ollama_host import client_host

log = logging.getLogger(__name__)

SLOW_POLISH_THRESHOLD_SEC = 3.0
SLOW_POLISH_TRIGGER_COUNT = 3
FORCE_FAST_DURATION_SEC = 5 * 60

CONNECTION_FAIL_TRIGGER_COUNT = 3


GPU_RESIDENCY_FULL_RATIO = 0.95

from kira._resources import prompts_dir as _prompts_dir
PROMPT_DIR = _prompts_dir()
VALID_MODES = (
    "email", "chat", "terminal", "code", "plain",
    "clean", "translate_en", "email_formal",
)


def load_prompt(mode: str) -> str:
    candidate = PROMPT_DIR / f"{mode}.md"
    if not candidate.exists():
        candidate = PROMPT_DIR / "plain.md"
    return candidate.read_text(encoding="utf-8")


GLOSSARY_INSTRUCTION = (
    "Möglicherweise gemeinte Begriffe: {terms}. Ersetze ein Wort nur, wenn es "
    "offensichtlich falsch erkannt wurde und einem dieser Begriffe entspricht. "
    "Sonst nichts ändern."
)


def _template_with_glossary(template: str, glossary: list[str] | None) -> str:
    if not glossary:
        return template
    block = GLOSSARY_INSTRUCTION.format(terms=", ".join(glossary))
    block = block.replace("{", "{{").replace("}", "}}")
    marker = "\nInput:"
    idx = template.find(marker)
    if idx == -1:
        return block + "\n\n" + template
    return template[:idx] + "\n" + block + "\n" + template[idx:]


_THINKING_MODEL_RE = re.compile(r"qwen3|gemma[-_ ]?[4-9]", re.IGNORECASE)


def _thinking_kwargs(model: str) -> dict:
    return {"think": False} if _THINKING_MODEL_RE.search(model) else {}


class Styler:
    def __init__(
        self,
        config: Config,
        on_slow_polish_detected: Callable[[], None] | None = None,
        on_cpu_fallback_detected: Callable[[str], None] | None = None,
    ):
        self._config = config
        self._client = ollama.AsyncClient(host=client_host())
        self._on_slow_polish_detected = on_slow_polish_detected
        self._on_cpu_fallback_detected = on_cpu_fallback_detected
        self._slow_polish_count = 0
        self._force_fast_until: float | None = None
        self._warmup_succeeded = False
        self._on_connection_lost: Callable[[], None] | None = None
        self._connection_fail_count = 0
        self._connection_notice_sent = False

    def set_on_slow_polish_detected(
        self, callback: Callable[[], None] | None,
    ) -> None:
        self._on_slow_polish_detected = callback

    def set_on_cpu_fallback_detected(
        self, callback: Callable[[str], None] | None,
    ) -> None:
        self._on_cpu_fallback_detected = callback

    def set_on_connection_lost(
        self, callback: Callable[[], None] | None,
    ) -> None:
        self._on_connection_lost = callback

    def _note_connection_result(self, failed: bool) -> None:
        if not failed:
            self._connection_fail_count = 0
            return
        self._connection_fail_count += 1
        if (
            self._connection_fail_count >= CONNECTION_FAIL_TRIGGER_COUNT
            and not self._connection_notice_sent
            and self._on_connection_lost is not None
        ):
            self._connection_notice_sent = True
            try:
                self._on_connection_lost()
            except Exception:
                log.exception("connection-lost callback raised")

    @property
    def warmup_succeeded(self) -> bool:
        return self._warmup_succeeded

    def _resolve_model(self, mode: str | None = None) -> str:
        if mode is not None:
            mode_cfg = self._config.styler.modes.get(mode, ModeConfig())
            if mode_cfg.model:
                return mode_cfg.model
        if self._config.styler.fast_mode or self._is_force_fast_active():
            return self._config.styler.fast_model
        return self._config.styler.model

    def _is_force_fast_active(self) -> bool:
        if self._force_fast_until is None:
            return False
        if time.monotonic() < self._force_fast_until:
            return True
        self._force_fast_until = None
        return False

    def _activate_force_fast(self) -> None:
        self._force_fast_until = time.monotonic() + FORCE_FAST_DURATION_SEC
        log.warning(
            "Polish-Latenz über Schwelle (%d in Folge > %.1fs), switche "
            "temporaer auf fast_model=%s fuer %d s. Pruefe `ollama ps` und "
            "GPU-Auslastung (Polish-Modell duerfte auf CPU geladen sein).",
            SLOW_POLISH_TRIGGER_COUNT,
            SLOW_POLISH_THRESHOLD_SEC,
            self._config.styler.fast_model,
            FORCE_FAST_DURATION_SEC,
        )

    def _observe_polish_duration(self, duration: float) -> None:
        if duration <= SLOW_POLISH_THRESHOLD_SEC:
            self._slow_polish_count = 0
            return
        self._slow_polish_count += 1
        if (
            self._slow_polish_count < SLOW_POLISH_TRIGGER_COUNT
            or self._is_force_fast_active()
        ):
            return
        if not self._config.styler.fast_mode:
            self._activate_force_fast()
        if self._on_slow_polish_detected is not None:
            try:
                self._on_slow_polish_detected()
            except Exception:
                log.exception("on_slow_polish_detected callback raised")
        self._slow_polish_count = 0

    async def warmup(self) -> None:
        model = self._resolve_model(None)
        keep_alive = self._config.styler.keep_alive
        try:
            await asyncio.wait_for(
                self._client.chat(
                    model=model,
                    messages=[{"role": "user", "content": "ok"}],
                    options={
                        "temperature": 0.0,
                        "num_predict": 1,
                    },
                    keep_alive=keep_alive,
                    **_thinking_kwargs(model),
                ),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            log.warning(
                "Styler warmup timed out after 60 s (model=%s). "
                "Model load takes longer than expected, first dictation "
                "may still be slow. Check `ollama list` for the model.",
                model,
            )
            return
        except Exception as exc:
            log.warning(
                "Styler warmup failed (%s). First dictation will pay the "
                "cold-start cost. Polish still falls back to raw on real "
                "errors, so this is non-fatal.",
                exc,
            )
            return
        self._warmup_succeeded = True
        log.info(
            "Styler warmup complete (model=%s, keep_alive=%s)",
            model, keep_alive,
        )
        try:
            await self.verify_gpu_placement()
        except Exception:
            log.exception("GPU-Placement-Check nach Warmup fehlgeschlagen")

    async def verify_gpu_placement(self) -> str | None:
        model = self._resolve_model(None)
        wanted = {model}
        if ":" not in model:
            wanted.add(f"{model}:latest")
        try:
            resp = await self._client.ps()
        except Exception as exc:
            log.warning(
                "GPU-Placement-Check übersprungen, ollama.ps() "
                "fehlgeschlagen (%s)", exc,
            )
            return None
        for m in getattr(resp, "models", None) or []:
            if wanted.isdisjoint({getattr(m, "model", None), getattr(m, "name", None)}):
                continue
            size = m.size
            vram = m.size_vram
            if size is None or vram is None or int(size) <= 0:
                return None
            if int(size) > 0 and int(vram) == 0:
                log.warning(
                    "Polish-Modell %s liegt KOMPLETT auf CPU (size=%.1f GB, "
                    "size_vram=0). Polish ist dadurch ~5-10x langsamer. "
                    "Abhilfe: Ollama neu starten; Speech2Anywhere setzt "
                    "OLLAMA_FLASH_ATTENTION=1 + OLLAMA_KV_CACHE_TYPE=q8_0 "
                    "persistent, das senkt den VRAM-Bedarf und bringt das "
                    "Modell in den VRAM. Bleibt es auf CPU: Programme schließen, "
                    "die Grafikspeicher belegen, oder ein kleineres Modell "
                    "wählen; kein Downgrade, die gemma4-Modelle brauchen "
                    "Ollama ab 0.30. Achtung: Haelt ein WSL-/"
                    "Docker-Ollama den Port 11434, gilt stattdessen die "
                    "Port-Diagnose-Zeile direkt nach dieser (Windows).",
                    model, int(size) / 1e9,
                )
                if self._on_cpu_fallback_detected is not None:
                    msg = (
                        f"Polish-Modell {model} läuft auf CPU statt GPU, "
                        f"stark verlangsamt. Ollama neu starten (Speech2Anywhere hat das "
                        f"VRAM-Tuning gesetzt, es greift nach dem Neustart). "
                        f"Hilft das nicht: Programme schließen, die "
                        f"Grafikspeicher belegen, oder ein kleineres Modell "
                        f"wählen."
                    )
                    try:
                        self._on_cpu_fallback_detected(msg)
                    except Exception:
                        log.exception(
                            "on_cpu_fallback_detected callback raised"
                        )
                return "cpu"
            if int(vram) < int(size) * GPU_RESIDENCY_FULL_RATIO:
                log.warning(
                    "Polish-Modell %s liegt nur TEILWEISE im VRAM "
                    "(%.1f/%.1f GB auf GPU). Der CPU-Anteil bremst jede "
                    "Token-Generation. Abhilfe wie beim CPU-Fallback: "
                    "Ollama neu starten (VRAM-Tuning greift), VRAM-Fresser "
                    "schließen oder kleineres Modell wählen.",
                    model, int(vram) / 1e9, int(size) / 1e9,
                )
                if self._on_cpu_fallback_detected is not None:
                    msg = (
                        f"Polish-Modell {model} liegt nur teilweise im VRAM "
                        f"({int(vram) / 1e9:.1f}/{int(size) / 1e9:.1f} GB), "
                        f"Polish deutlich verlangsamt. Ollama neu starten; "
                        f"bleibt der Split, VRAM freiräumen oder kleineres "
                        f"Modell nutzen."
                    )
                    try:
                        self._on_cpu_fallback_detected(msg)
                    except Exception:
                        log.exception(
                            "on_cpu_fallback_detected callback raised"
                        )
                return "partial"
            log.info(
                "Polish-Modell %s liegt im VRAM (%.1f/%.1f GB auf GPU)",
                model, int(vram) / 1e9, int(size) / 1e9,
            )
            return "gpu"
        return None

    async def polish(self, text: str, mode: str, glossary: list[str] | None = None) -> str:
        if not text.strip():
            return text
        prompt = _template_with_glossary(load_prompt(mode), glossary).format(text=text)
        mode_cfg = self._config.styler.modes.get(mode, ModeConfig())
        model = self._resolve_model(mode)
        timeout = mode_cfg.timeout_seconds or self._config.styler.timeout_seconds
        temperature = (
            mode_cfg.temperature if mode_cfg.temperature is not None else 0.2
        )
        start = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self._client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    options={
                        "temperature": temperature,
                    },
                    keep_alive=self._config.styler.keep_alive,
                    **_thinking_kwargs(model),
                ),
                timeout=timeout,
            )
            polished = response["message"]["content"].strip()
            self._note_connection_result(False)
            if not polished:
                log.warning(
                    "Styler returned empty response (model=%s, raw_chars=%d). "
                    "Falling back to raw transcription.",
                    model, len(text),
                )
                if self._config.styler.fallback_to_raw:
                    return text
                raise RuntimeError(
                    f"Styler returned empty response (model={model})"
                )
            return polished
        except asyncio.TimeoutError:
            self._note_connection_result(False)
            log.warning(
                "Styler timed out after %.1fs (model=%s). "
                "First-call cold-start can be ~14s for 27B-class models; "
                "raise styler.timeout_seconds in config.yaml if this keeps "
                "firing. Falling back to raw transcription.",
                timeout, model,
            )
            if self._config.styler.fallback_to_raw:
                return text
            raise
        except Exception as exc:
            self._note_connection_result(isinstance(exc, ConnectionError))
            log.warning("Styler failed (%s). Fallback to raw.", exc)
            if self._config.styler.fallback_to_raw:
                return text
            raise
        finally:
            self._observe_polish_duration(time.monotonic() - start)

    async def edit_command(self, selection: str, command: str) -> str:
        if not selection.strip() or not command.strip():
            return selection
        template = load_prompt("edit_command")
        prompt = template.format(selection=selection, command=command)
        mode_cfg = self._config.styler.modes.get("edit_command", ModeConfig())
        model = self._resolve_model("edit_command")
        timeout = mode_cfg.timeout_seconds or self._config.styler.timeout_seconds
        temperature = (
            mode_cfg.temperature if mode_cfg.temperature is not None else 0.2
        )
        try:
            response = await asyncio.wait_for(
                self._client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    options={
                        "temperature": temperature,
                    },
                    keep_alive=self._config.styler.keep_alive,
                    **_thinking_kwargs(model),
                ),
                timeout=timeout,
            )
            edited = response["message"]["content"].strip()
            if not edited:
                log.warning(
                    "edit_command returned empty (model=%s, sel=%d chars, "
                    "cmd=%r), returning original selection",
                    model, len(selection), command[:60],
                )
                return selection
            return edited
        except asyncio.TimeoutError:
            log.warning(
                "edit_command timed out after %.1fs (model=%s), "
                "returning original selection",
                timeout, model,
            )
            return selection
        except Exception as exc:
            log.warning(
                "edit_command failed (%s), returning original selection",
                exc,
            )
            return selection
