from __future__ import annotations
import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Callable
import ollama
from kira.config import LANGUAGE_NAMES, Config, ModeConfig
from kira.ollama_env import describe_tuning_env, read_tuning_env, vram_tuning_set
from kira.ollama_host import client_host
from kira.texte import N_, tr

log = logging.getLogger(__name__)

SLOW_POLISH_THRESHOLD_SEC = 3.0
SLOW_POLISH_TRIGGER_COUNT = 3
FORCE_FAST_DURATION_SEC = 5 * 60
FORCE_FAST_KEEP_ALIVE = f"{FORCE_FAST_DURATION_SEC}s"
PLACEMENT_CHECK_TIMEOUT_SEC = 2.0

CONNECTION_FAIL_TRIGGER_COUNT = 3


GPU_RESIDENCY_FULL_RATIO = 0.95

_TUNING_NOTICE = {
    True: N_(" (VRAM-Tuning ist gesetzt, greift nach dem Neustart)"),
    False: N_(" (VRAM-Tuning fehlt, Details im Protokoll)"),
    None: "",
}

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


LANGUAGE_RULE = (
    "Sprache: Gib den Text in genau der Sprache zurück, in der der Input steht. "
    "Übersetze nie, auch nicht ins Deutsche. Ist der Input nicht deutsch, gelten "
    "alle Regeln sinngemäß in seiner Sprache, auch für die dort üblichen Füllwörter."
)
LANGUAGE_RULE_EXEMPT = frozenset({"translate_en"})
LANGUAGE_HINT = "Der Input steht auf {name}. Antworte auf {name}, nicht auf Deutsch."
LANGUAGE_HINT_BY_CODE = (
    "Der Input steht in der Sprache mit dem Kürzel „{code}“. "
    "Antworte in dieser Sprache, nicht auf Deutsch."
)
LANGUAGE_HINT_MODES = frozenset({"email", "email_formal"})

SELF_CORRECTION_RULE = (
    "Selbstkorrektur (einzige Ausnahme von der Regel, den Inhalt exakt beizubehalten): "
    "Nimmt der Sprecher mitten im Satz eine eben gemachte Angabe "
    "zurück und ersetzt sie sofort durch eine andere derselben Art, bleibt nur die "
    "neue Angabe stehen; das Signalwort und die alte Angabe entfallen. Muster: "
    "„um neun, nein, um elf“ wird „um elf“. Signalwörter sind etwa „nein“, „nee“, "
    "„ach Quatsch“, „ich meine“, „Korrektur“, „Moment“, „no wait“, „scratch that“, "
    "„I mean“, „actually“, „sorry“. Steht ein solches Wort am Satzanfang oder leitet "
    "es eine Aussage, Meinung oder Erklärung ein („Nein, danke.“, „Ich meine, wir "
    "sollten warten.“, „Actually, it works.“), ist es Inhalt und bleibt unverändert "
    "stehen. Im Zweifel nichts streichen."
)
SELF_CORRECTION_MODES = frozenset({"plain", "chat", "email", "email_formal"})


def _insert_before_input(template: str, block: str) -> str:
    marker = "\nInput:"
    idx = template.find(marker)
    if idx == -1:
        return block + "\n\n" + template
    return template[:idx] + "\n" + block + "\n" + template[idx:]


def _language_hint(language: str | None) -> str | None:
    if not language or language == "de":
        return None
    name = LANGUAGE_NAMES.get(language)
    hint = LANGUAGE_HINT.format(name=name) if name else LANGUAGE_HINT_BY_CODE.format(code=language)
    return hint.replace("{", "{{").replace("}", "}}")


def _template_with_rules(template: str, mode: str, language: str | None = None) -> str:
    if mode in SELF_CORRECTION_MODES:
        template = _insert_before_input(template, SELF_CORRECTION_RULE)
    if mode in LANGUAGE_RULE_EXEMPT:
        return template
    template = _insert_before_input(template, LANGUAGE_RULE)
    hint = _language_hint(language) if mode in LANGUAGE_HINT_MODES else None
    return _insert_before_input(template, hint) if hint else template


def _template_with_glossary(template: str, glossary: list[str] | None) -> str:
    if not glossary:
        return template
    block = GLOSSARY_INSTRUCTION.format(terms=", ".join(glossary))
    block = block.replace("{", "{{").replace("}", "}}")
    return _insert_before_input(template, block)


_THINKING_MODEL_RE = re.compile(r"qwen3|gemma[-_ ]?[4-9]", re.IGNORECASE)


def _thinking_kwargs(model: str) -> dict:
    return {"think": False} if _THINKING_MODEL_RE.search(model) else {}


def _loaded_entries(resp, model: str):
    names = {model} if ":" in model else {model, f"{model}:latest"}
    for entry in getattr(resp, "models", None) or []:
        if not names.isdisjoint({getattr(entry, "model", None), getattr(entry, "name", None)}):
            yield entry


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

    @property
    def cpu_mode(self) -> bool:
        return self._config.whisper.device == "cpu"

    def _options(self, **options) -> dict:
        if self.cpu_mode:
            options["num_gpu"] = 0
        return options

    def _resolve_model(self, mode: str | None = None) -> str:
        if mode is not None:
            mode_cfg = self._config.styler.modes.get(mode, ModeConfig())
            if mode_cfg.model:
                return mode_cfg.model
        if self.cpu_mode or self._config.styler.fast_mode or self._is_force_fast_active():
            return self._config.styler.fast_model
        return self._config.styler.model

    def _is_force_fast_active(self) -> bool:
        if self._force_fast_until is None:
            return False
        if time.monotonic() < self._force_fast_until:
            return True
        self._force_fast_until = None
        return False

    def _keep_alive_for(self, model: str) -> str:
        if self._is_force_fast_active() and model == self._config.styler.fast_model:
            return FORCE_FAST_KEEP_ALIVE
        return self._config.styler.keep_alive

    def _activate_force_fast(self) -> None:
        self._force_fast_until = time.monotonic() + FORCE_FAST_DURATION_SEC
        log.warning(
            "Politur über Schwelle (%d in Folge > %.1f s; Ladezeit abgezogen, "
            "soweit Ollama sie meldet; Zeitüberschreitungen zählen voll), "
            "schalte vorübergehend auf fast_model=%s für %d s um. Prüfe "
            "`ollama ps` und die GPU-Auslastung "
            "(Politur-Modell liegt vermutlich auf CPU oder die Grafikkarte "
            "ist ausgelastet).",
            SLOW_POLISH_TRIGGER_COUNT,
            SLOW_POLISH_THRESHOLD_SEC,
            self._config.styler.fast_model,
            FORCE_FAST_DURATION_SEC,
        )

    async def _fully_in_vram(self, model: str) -> bool:
        try:
            resp = await asyncio.wait_for(
                self._client.ps(), timeout=PLACEMENT_CHECK_TIMEOUT_SEC,
            )
        except Exception as exc:
            log.warning(
                "Belegungsprüfung vor dem Umschalten nicht möglich (%r), "
                "schalte wie bisher um",
                exc,
            )
            return False
        entry = next(_loaded_entries(resp, model), None)
        if entry is None or entry.size is None or entry.size_vram is None:
            return False
        return int(entry.size) > 0 and int(entry.size_vram) >= int(entry.size)

    async def _observe_polish_duration(self, duration: float) -> None:
        if self.cpu_mode:
            return
        if duration <= SLOW_POLISH_THRESHOLD_SEC:
            self._slow_polish_count = 0
            return
        self._slow_polish_count += 1
        if (
            self._slow_polish_count < SLOW_POLISH_TRIGGER_COUNT
            or self._is_force_fast_active()
        ):
            return
        self._slow_polish_count = 0
        model = self._resolve_model(None)
        if await self._fully_in_vram(model):
            log.info(
                "Politur langsam, %s liegt aber ganz im Grafikspeicher: kein "
                "Umschalten, vermutlich fremde Last auf der Grafikkarte",
                model,
            )
            return
        if not self._config.styler.fast_mode:
            self._activate_force_fast()
        if self._on_slow_polish_detected is not None:
            try:
                self._on_slow_polish_detected()
            except Exception:
                log.exception("on_slow_polish_detected callback raised")

    async def warmup(self) -> None:
        model = self._resolve_model(None)
        keep_alive = self._keep_alive_for(model)
        try:
            await asyncio.wait_for(
                self._client.chat(
                    model=model,
                    messages=[{"role": "user", "content": "ok"}],
                    options=self._options(temperature=0.0, num_predict=1),
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
        if self.cpu_mode:
            log.info("Polish-Modell %s rechnet im Prozessor-Modus auf der CPU", model)
            return "cpu"
        try:
            resp = await self._client.ps()
        except Exception as exc:
            log.warning(
                "GPU-Placement-Check übersprungen, ollama.ps() "
                "fehlgeschlagen (%s)", exc,
            )
            return None
        for m in _loaded_entries(resp, model):
            size = m.size
            vram = m.size_vram
            if size is None or vram is None or int(size) <= 0:
                return None
            if int(size) > 0 and int(vram) == 0:
                tuning = read_tuning_env()
                log.warning(
                    "Polish-Modell %s liegt KOMPLETT auf CPU (size=%.1f GB, "
                    "size_vram=0). Polish ist dadurch ~5-10x langsamer. "
                    "Abhilfe: Ollama neu starten; Speech2Anywhere setzt "
                    "OLLAMA_FLASH_ATTENTION=1 + OLLAMA_KV_CACHE_TYPE=q8_0 "
                    "persistent, das senkt den VRAM-Bedarf und bringt das "
                    "Modell in den VRAM. Bleibt es auf CPU: Programme schließen, "
                    "die Grafikspeicher belegen, oder ein kleineres Modell "
                    "wählen; kein Downgrade, die gemma4-Modelle brauchen "
                    "Ollama ab 0.30. Achtung: Hält ein WSL-/"
                    "Docker-Ollama den Port 11434, gilt stattdessen die "
                    "Port-Diagnose-Zeile direkt nach dieser (Windows). "
                    "Benutzervariablen in HKCU\\Environment: %s.",
                    model, int(size) / 1e9, describe_tuning_env(tuning),
                )
                if self._on_cpu_fallback_detected is not None:
                    msg = (
                        tr(
                            "Politur-Modell {} läuft auf CPU statt GPU, stark verlangsamt. Ollama neu starten{}. Hilft das "
                            "nicht: Programme schließen, die Grafikspeicher belegen, oder ein kleineres Modell wählen."
                        ).format(model, tr(_TUNING_NOTICE[vram_tuning_set(tuning)]))
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
                    "schließen oder kleineres Modell wählen. "
                    "Benutzervariablen in HKCU\\Environment: %s.",
                    model, int(vram) / 1e9, int(size) / 1e9,
                    describe_tuning_env(read_tuning_env()),
                )
                if self._on_cpu_fallback_detected is not None:
                    msg = (
                        tr(
                            "Politur-Modell {} liegt nur teilweise im VRAM ({:.1f}/{:.1f} GB), Politur deutlich verlangsamt. "
                            "Ollama neu starten; bleibt der Split, VRAM freiräumen oder kleineres Modell nutzen."
                        ).format(model, int(vram) / 1e9, int(size) / 1e9)
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

    async def polish(
        self, text: str, mode: str, glossary: list[str] | None = None, language: str | None = None,
    ) -> str:
        if not text.strip():
            return text
        template = _template_with_rules(load_prompt(mode), mode, language)
        prompt = _template_with_glossary(template, glossary).format(text=text)
        mode_cfg = self._config.styler.modes.get(mode, ModeConfig())
        model = self._resolve_model(mode)
        timeout = mode_cfg.timeout_seconds or self._config.styler.timeout_seconds
        temperature = (
            mode_cfg.temperature if mode_cfg.temperature is not None else 0.2
        )
        start = time.monotonic()
        load_seconds = 0.0
        try:
            response = await asyncio.wait_for(
                self._client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    options=self._options(temperature=temperature),
                    keep_alive=self._keep_alive_for(model),
                    **_thinking_kwargs(model),
                ),
                timeout=timeout,
            )
            load_seconds = (response.get("load_duration") or 0) / 1e9
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
            elapsed = time.monotonic() - start
            counted = max(0.0, elapsed - load_seconds)
            if load_seconds and elapsed > SLOW_POLISH_THRESHOLD_SEC:
                log.info(
                    "Politur dauerte %.1f s, davon %.1f s Laden von %s; "
                    "für die Langsam-Erkennung zählen %.1f s",
                    elapsed, load_seconds, model, counted,
                )
            await self._observe_polish_duration(counted)

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
                    options=self._options(temperature=temperature),
                    keep_alive=self._keep_alive_for(model),
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
