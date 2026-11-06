import asyncio
import logging
import re
import time
from unittest.mock import AsyncMock, MagicMock
import pytest
from ollama import ChatResponse, Message, ProcessResponse
import kira.styler as styler_module
from kira.config import Config, ModeConfig
from kira.ollama_env import TUNING_ENV
from kira.styler import (
    Styler,
    load_prompt,
    _thinking_kwargs,
    FORCE_FAST_DURATION_SEC,
    SLOW_POLISH_THRESHOLD_SEC,
    SLOW_POLISH_TRIGGER_COUNT,
)


def _ps(model_name, size, size_vram, *, name=None):
    return ProcessResponse(models=[ProcessResponse.Model(
        model=model_name, name=name if name is not None else model_name,
        size=size, size_vram=size_vram,
    )])


@pytest.fixture(autouse=True)
def _user_environment_not_read(monkeypatch):
    monkeypatch.setattr(styler_module, "read_tuning_env", lambda: None, raising=False)


@pytest.fixture(autouse=True)
def _no_real_ollama(monkeypatch):
    def offline_client(*_args, **_kwargs):
        client = MagicMock()
        client.ps = AsyncMock(side_effect=ConnectionError("kein Ollama im Test"))
        client.chat = AsyncMock(side_effect=ConnectionError("kein Ollama im Test"))
        return client

    monkeypatch.setattr(styler_module.ollama, "AsyncClient", offline_client)


def _recording(observed: list):
    async def record(duration: float) -> None:
        observed.append(duration)
    return record


@pytest.mark.asyncio
async def test_polish_returns_model_output():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "Hallo Welt."}})
    styler._client = fake_client
    result = await styler.polish("hallo welt", mode="plain")
    assert result == "Hallo Welt."


@pytest.mark.asyncio
async def test_polish_falls_back_to_raw_on_error():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=Exception("ollama down"))
    styler._client = fake_client
    result = await styler.polish("raw text", mode="plain")
    assert result == "raw text"


@pytest.mark.asyncio
async def test_polish_falls_back_to_raw_on_empty_response():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": ""}})
    styler._client = fake_client
    result = await styler.polish("raw text", mode="plain")
    assert result == "raw text"


@pytest.mark.asyncio
async def test_polish_falls_back_to_raw_on_whitespace_response():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "   \n  "}})
    styler._client = fake_client
    result = await styler.polish("raw text", mode="plain")
    assert result == "raw text"


@pytest.mark.asyncio
async def test_polish_raises_when_fallback_disabled():
    cfg = Config()
    cfg.styler.fallback_to_raw = False
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=Exception("ollama down"))
    styler._client = fake_client
    with pytest.raises(Exception):
        await styler.polish("raw text", mode="plain")


def test_load_prompt_returns_template():
    tpl = load_prompt("plain")
    assert "{text}" in tpl
    assert len(tpl) > 50


def test_load_prompt_unknown_mode_falls_back_to_plain():
    tpl = load_prompt("nonexistent")
    assert "{text}" in tpl


def test_new_prompts_exist_and_have_text_placeholder():
    for mode in ("clean", "translate_en", "email_formal"):
        tpl = load_prompt(mode)
        assert "{text}" in tpl, f"prompts/{mode}.md fehlt das {{text}} Token"


@pytest.mark.asyncio
async def test_polish_uses_per_mode_model_override():
    cfg = Config()
    cfg.styler.model = "gemma2:2b"
    cfg.styler.modes["translate_en"] = ModeConfig(model="qwen3:8b")
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value={"message": {"content": "Hello world."}}
    )
    styler._client = fake_client

    await styler.polish("hallo welt", mode="translate_en")

    fake_client.chat.assert_called_once()
    kwargs = fake_client.chat.call_args.kwargs
    assert kwargs["model"] == "qwen3:8b", \
        "Mode-Override sollte das gemma2:2b-Default ueberschreiben"


@pytest.mark.asyncio
async def test_polish_uses_default_model_when_no_mode_config():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value={"message": {"content": "Hallo Welt."}}
    )
    styler._client = fake_client

    await styler.polish("hallo welt", mode="plain")

    kwargs = fake_client.chat.call_args.kwargs
    assert kwargs["model"] == "gemma3:12b"


@pytest.mark.asyncio
async def test_polish_uses_per_mode_temperature():
    cfg = Config()
    cfg.styler.modes["code"] = ModeConfig(temperature=0.0)
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value={"message": {"content": "x = 1"}}
    )
    styler._client = fake_client

    await styler.polish("x ist gleich eins", mode="code")

    kwargs = fake_client.chat.call_args.kwargs
    assert kwargs["options"]["temperature"] == 0.0


@pytest.mark.asyncio
async def test_edit_command_calls_llm_with_selection_and_command():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value={"message": {"content": "Sehr geehrte Damen und Herren,"}}
    )
    styler._client = fake_client

    result = await styler.edit_command(
        selection="hi leute",
        command="mach das foermlich",
    )

    assert result == "Sehr geehrte Damen und Herren,"
    kwargs = fake_client.chat.call_args.kwargs
    user_msg = kwargs["messages"][0]["content"]
    assert "hi leute" in user_msg
    assert "mach das foermlich" in user_msg


@pytest.mark.asyncio
async def test_edit_command_returns_selection_on_empty_response():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": ""}})
    styler._client = fake_client

    result = await styler.edit_command(
        selection="original text",
        command="mach was",
    )
    assert result == "original text"


@pytest.mark.asyncio
async def test_edit_command_returns_selection_on_exception():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=Exception("ollama down"))
    styler._client = fake_client

    result = await styler.edit_command(
        selection="original text",
        command="mach was",
    )
    assert result == "original text"


@pytest.mark.asyncio
async def test_edit_command_skips_llm_when_either_input_empty():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(
        return_value={"message": {"content": "should-not-see-this"}}
    )
    styler._client = fake_client

    assert await styler.edit_command(selection="", command="cmd") == ""
    assert await styler.edit_command(
        selection="text", command="",
    ) == "text"
    fake_client.chat.assert_not_called()


@pytest.mark.asyncio
async def test_edit_command_uses_per_mode_model_override():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.modes["edit_command"] = ModeConfig(model="qwen3:8b")
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "out"}})
    styler._client = fake_client

    await styler.edit_command(selection="text", command="cmd")

    kwargs = fake_client.chat.call_args.kwargs
    assert kwargs["model"] == "qwen3:8b"


@pytest.mark.asyncio
async def test_polish_uses_fast_model_when_fast_mode_enabled():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.fast_model = "gemma3:4b"
    cfg.styler.fast_mode = True
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client

    await styler.polish("text", mode="plain")

    assert fake_client.chat.call_args.kwargs["model"] == "gemma3:4b"


@pytest.mark.asyncio
async def test_polish_uses_quality_model_when_fast_mode_disabled():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.fast_model = "gemma3:4b"
    cfg.styler.fast_mode = False
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client

    await styler.polish("text", mode="plain")

    assert fake_client.chat.call_args.kwargs["model"] == "gemma3:12b"


@pytest.mark.asyncio
async def test_polish_per_mode_override_beats_fast_mode():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.fast_model = "gemma3:4b"
    cfg.styler.fast_mode = True
    cfg.styler.modes["translate_en"] = ModeConfig(model="qwen3:8b")
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "out"}})
    styler._client = fake_client

    await styler.polish("text", mode="translate_en")

    assert fake_client.chat.call_args.kwargs["model"] == "qwen3:8b"


@pytest.mark.asyncio
async def test_warmup_uses_fast_model_when_fast_mode_enabled():
    cfg = Config()
    cfg.styler.fast_model = "gemma3:4b"
    cfg.styler.fast_mode = True
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client

    await styler.warmup()

    assert fake_client.chat.call_args.kwargs["model"] == "gemma3:4b"


@pytest.mark.asyncio
async def test_edit_command_uses_fast_model_when_fast_mode_enabled():
    cfg = Config()
    cfg.styler.fast_model = "gemma3:4b"
    cfg.styler.fast_mode = True
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "edited"}})
    styler._client = fake_client

    await styler.edit_command(selection="text", command="cmd")

    assert fake_client.chat.call_args.kwargs["model"] == "gemma3:4b"


@pytest.mark.asyncio
async def test_observe_fast_polish_does_not_increment_counter():
    cfg = Config()
    styler = Styler(cfg)
    await styler._observe_polish_duration(0.5)
    assert styler._slow_polish_count == 0
    assert styler._force_fast_until is None


@pytest.mark.asyncio
async def test_observe_slow_polish_increments_counter_but_does_not_trigger():
    cfg = Config()
    styler = Styler(cfg)
    await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert styler._slow_polish_count == 1
    assert styler._force_fast_until is None


@pytest.mark.asyncio
async def test_observe_three_slow_polishes_in_a_row_triggers_force_fast():
    cfg = Config()
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert styler._force_fast_until is not None
    callback.assert_called_once()
    assert styler._slow_polish_count == 0


@pytest.mark.asyncio
async def test_observe_fast_polish_resets_counter():
    cfg = Config()
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    await styler._observe_polish_duration(0.5)
    await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert styler._slow_polish_count == 1
    assert styler._force_fast_until is None
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_observe_force_fast_active_blocks_re_notification():
    cfg = Config()
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert callback.call_count == 1
    for _ in range(SLOW_POLISH_TRIGGER_COUNT * 2):
        await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert callback.call_count == 1


@pytest.mark.asyncio
async def test_observe_does_not_switch_when_fast_mode_already_user_enabled():
    cfg = Config()
    cfg.styler.fast_mode = True
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    callback.assert_called_once()
    assert styler._force_fast_until is None


def test_resolve_model_uses_fast_model_when_force_fast_active():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.fast_model = "gemma3:4b"
    styler = Styler(cfg)
    styler._activate_force_fast()
    assert styler._resolve_model("plain") == "gemma3:4b"


def test_resolve_model_falls_back_to_default_after_force_fast_expires(monkeypatch):
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.fast_model = "gemma3:4b"
    styler = Styler(cfg)
    styler._activate_force_fast()
    import kira.styler as styler_mod
    until = styler._force_fast_until
    assert until is not None
    fake_now = until + 1.0
    monkeypatch.setattr(styler_mod.time, "monotonic", lambda: fake_now)
    assert styler._resolve_model("plain") == "gemma3:12b"
    assert styler._force_fast_until is None


def test_resolve_model_per_mode_override_beats_force_fast():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.fast_model = "gemma3:4b"
    cfg.styler.modes["translate_en"] = ModeConfig(model="qwen3:8b")
    styler = Styler(cfg)
    styler._activate_force_fast()
    assert styler._resolve_model("translate_en") == "qwen3:8b"


@pytest.mark.asyncio
async def test_callback_exception_does_not_break_observe():
    cfg = Config()
    callback = MagicMock(side_effect=RuntimeError("tray dead"))
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert styler._slow_polish_count == 0
    assert styler._force_fast_until is not None


@pytest.mark.asyncio
async def test_polish_observes_duration_via_finally(monkeypatch):
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client
    observed = []
    monkeypatch.setattr(styler, "_observe_polish_duration", _recording(observed))
    await styler.polish("hi", mode="plain")
    assert len(observed) == 1
    assert observed[0] >= 0.0


SAMPLING_OPTIONS = {"temperature", "num_predict"}


@pytest.mark.asyncio
async def test_polish_sends_only_sampling_options():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client

    await styler.polish("text", mode="plain")

    assert set(fake_client.chat.call_args.kwargs["options"]) <= SAMPLING_OPTIONS


@pytest.mark.asyncio
async def test_warmup_sends_only_sampling_options():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    fake_client.ps = AsyncMock(return_value=MagicMock(models=[]))
    styler._client = fake_client

    await styler.warmup()

    assert set(fake_client.chat.call_args.kwargs["options"]) <= SAMPLING_OPTIONS


@pytest.mark.asyncio
async def test_edit_command_sends_only_sampling_options():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "edited"}})
    styler._client = fake_client

    await styler.edit_command(selection="text", command="cmd")

    assert set(fake_client.chat.call_args.kwargs["options"]) <= SAMPLING_OPTIONS


@pytest.mark.asyncio
async def test_verify_gpu_placement_detects_cpu_fallback():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=11_779_775_936, size_vram=0)
    )

    result = await styler.verify_gpu_placement()

    assert result == "cpu"
    callback.assert_called_once()
    msg = callback.call_args.args[0]
    assert "gemma3:12b" in msg
    assert "neu starten" in msg.lower()
    assert "grafikspeicher" in msg.lower()
    assert "0.24" not in msg


@pytest.mark.asyncio
async def test_verify_gpu_placement_returns_gpu_when_resident_in_vram():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=11_779_775_936, size_vram=11_779_775_936)
    )

    result = await styler.verify_gpu_placement()

    assert result == "gpu"
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_verify_gpu_placement_model_not_running_returns_none():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("llama3:8b", size=4_000_000_000, size_vram=0)
    )

    result = await styler.verify_gpu_placement()

    assert result is None
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_verify_gpu_placement_handles_ps_exception():
    cfg = Config()
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(side_effect=Exception("ollama unreachable"))

    result = await styler.verify_gpu_placement()

    assert result is None
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_verify_gpu_placement_none_size_vram_is_unknown():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=11_779_775_936, size_vram=None)
    )

    result = await styler.verify_gpu_placement()

    assert result is None
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_verify_gpu_placement_matches_by_name_field():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    resp = ProcessResponse(models=[ProcessResponse.Model(
        model=None, name="gemma3:12b", size=11_779_775_936, size_vram=0,
    )])
    styler._client.ps = AsyncMock(return_value=resp)

    result = await styler.verify_gpu_placement()

    assert result == "cpu"
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_verify_gpu_placement_checks_active_model_under_fast_mode():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    cfg.styler.fast_model = "gemma3:4b"
    cfg.styler.fast_mode = True
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:4b", size=3_300_000_000, size_vram=0)
    )

    result = await styler.verify_gpu_placement()

    assert result == "cpu"
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_verify_gpu_placement_callback_exception_swallowed():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock(side_effect=RuntimeError("tray dead"))
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=11_779_775_936, size_vram=0)
    )

    result = await styler.verify_gpu_placement()
    assert result == "cpu"


@pytest.mark.asyncio
async def test_verify_gpu_placement_no_callback_configured():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    styler = Styler(cfg)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=11_779_775_936, size_vram=0)
    )

    result = await styler.verify_gpu_placement()
    assert result == "cpu"


def test_set_on_cpu_fallback_detected_late_binding():
    cfg = Config()
    styler = Styler(cfg)
    callback = MagicMock()
    styler.set_on_cpu_fallback_detected(callback)
    assert styler._on_cpu_fallback_detected is callback


@pytest.mark.asyncio
async def test_warmup_triggers_gpu_placement_check(monkeypatch):
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client
    calls = []

    async def fake_verify():
        calls.append(True)
        return "gpu"

    monkeypatch.setattr(styler, "verify_gpu_placement", fake_verify)

    await styler.warmup()

    assert calls == [True]


@pytest.mark.asyncio
async def test_warmup_gpu_check_failure_does_not_break_warmup(monkeypatch):
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client

    async def boom():
        raise RuntimeError("ps blew up")

    monkeypatch.setattr(styler, "verify_gpu_placement", boom)

    await styler.warmup()


@pytest.mark.asyncio
async def test_warmup_success_sets_warmup_succeeded():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    fake_client.ps = AsyncMock(side_effect=Exception("ps egal"))
    styler._client = fake_client

    assert styler.warmup_succeeded is False
    await styler.warmup()
    assert styler.warmup_succeeded is True


@pytest.mark.asyncio
async def test_warmup_failure_leaves_warmup_succeeded_false():
    cfg = Config()
    styler = Styler(cfg)
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=Exception("Server disconnected"))
    styler._client = fake_client

    await styler.warmup()
    assert styler.warmup_succeeded is False


@pytest.mark.asyncio
async def test_verify_gpu_placement_detects_partial_offload():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=12_000_000_000, size_vram=6_000_000_000)
    )

    result = await styler.verify_gpu_placement()

    assert result == "partial"
    callback.assert_called_once()
    msg = callback.call_args.args[0]
    assert "gemma3:12b" in msg
    assert "teilweise" in msg.lower()


@pytest.mark.asyncio
async def test_verify_gpu_placement_tolerates_small_nonvram_share():
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=12_000_000_000, size_vram=11_700_000_000)
    )

    result = await styler.verify_gpu_placement()

    assert result == "gpu"
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_verify_gpu_placement_matches_untagged_model_as_latest():
    cfg = Config()
    cfg.styler.model = "gemma3"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:latest", size=3_300_000_000, size_vram=0)
    )

    result = await styler.verify_gpu_placement()

    assert result == "cpu"
    callback.assert_called_once()


@pytest.mark.parametrize("model", [
    "gemma4:12b",
    "gemma4:e4b",
    "gemma4:26b-a4b-it-qat",
    "gemma-4-abliterated:31b-v2",
    "GEMMA4:12B",
    "qwen3:8b",
    "qwen3.6:35b-a3b",
    "huihui_ai/Qwen3.6-abliterated:35b-q4_K",
])
def test_thinking_is_disabled_for_reasoning_models(model):
    assert _thinking_kwargs(model) == {"think": False}


@pytest.mark.parametrize("model", [
    "gemma3:12b",
    "gemma3:4b",
    "gemma2:9b",
    "llama3.3:8b",
    "mistral-small3.2:24b",
])
def test_thinking_flag_omitted_for_non_reasoning_models(model):
    assert _thinking_kwargs(model) == {}


@pytest.mark.asyncio
async def test_polish_passes_think_false_for_gemma4():
    cfg = Config()
    cfg.styler.model = "gemma4:12b"
    styler = Styler(cfg)
    styler._client = MagicMock()
    styler._client.chat = AsyncMock(
        return_value={"message": {"content": "Hallo Welt."}}
    )

    await styler.polish("hallo welt", mode="plain")

    assert styler._client.chat.await_args.kwargs["think"] is False


def test_styler_client_targets_loopback_for_bind_all_host(monkeypatch):
    seen = {}

    class FakeAsyncClient:
        def __init__(self, host=None, **kwargs):
            seen["host"] = host

    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    monkeypatch.setattr("kira.styler.ollama.AsyncClient", FakeAsyncClient)
    Styler(Config())
    assert seen["host"] == "http://127.0.0.1:11434"


def test_styler_client_keeps_library_default_for_remote_host(monkeypatch):
    seen = {}

    class FakeAsyncClient:
        def __init__(self, host=None, **kwargs):
            seen["host"] = host

    monkeypatch.setenv("OLLAMA_HOST", "10.0.0.5:11434")
    monkeypatch.setattr("kira.styler.ollama.AsyncClient", FakeAsyncClient)
    Styler(Config())
    assert seen["host"] is None


@pytest.mark.asyncio
async def test_connection_lost_notice_fires_once_after_three_failures():
    calls = []
    styler = Styler(Config())
    styler.set_on_connection_lost(lambda: calls.append(1))
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=ConnectionError("Failed to connect to Ollama"))
    styler._client = fake_client
    for _ in range(5):
        assert await styler.polish("hallo welt", mode="plain") == "hallo welt"
    assert calls == [1]


@pytest.mark.asyncio
async def test_connection_counter_resets_after_success():
    calls = []
    styler = Styler(Config())
    styler.set_on_connection_lost(lambda: calls.append(1))
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=[
        ConnectionError("x"), ConnectionError("x"),
        {"message": {"content": "Hallo Welt."}},
        ConnectionError("x"), ConnectionError("x"),
    ])
    styler._client = fake_client
    for _ in range(5):
        await styler.polish("hallo welt", mode="plain")
    assert calls == []


@pytest.mark.asyncio
async def test_other_errors_do_not_count_as_connection_loss():
    calls = []
    styler = Styler(Config())
    styler.set_on_connection_lost(lambda: calls.append(1))
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=RuntimeError("model not found"))
    styler._client = fake_client
    for _ in range(4):
        await styler.polish("hallo welt", mode="plain")
    assert calls == []


@pytest.mark.asyncio
async def test_timeout_resets_connection_counter():
    calls = []
    styler = Styler(Config())
    styler.set_on_connection_lost(lambda: calls.append(1))
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(side_effect=[
        ConnectionError("x"), ConnectionError("x"),
        asyncio.TimeoutError(),
        ConnectionError("x"), ConnectionError("x"),
    ])
    styler._client = fake_client
    for _ in range(5):
        await styler.polish("hallo welt", mode="plain")
    assert calls == []


async def _sent_prompt(mode: str, glossary: list[str] | None = None, language: str | None = None) -> str:
    styler = Styler(Config())
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "Hallo Welt."}})
    styler._client = fake_client
    await styler.polish("hallo welt", mode=mode, glossary=glossary, language=language)
    return fake_client.chat.call_args.kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_polish_without_glossary_sends_no_glossary_block():
    sent = await _sent_prompt("plain")
    assert "Möglicherweise gemeinte Begriffe" not in sent
    assert "hallo welt" in sent
    assert sent.rstrip().endswith("Output:")


@pytest.mark.asyncio
async def test_translation_prompt_goes_out_unchanged():
    sent = await _sent_prompt("translate_en")
    assert sent == load_prompt("translate_en").format(text="hallo welt")


@pytest.mark.asyncio
async def test_every_polish_mode_but_translation_carries_the_language_rule():
    from kira.styler import LANGUAGE_RULE, VALID_MODES
    for mode in VALID_MODES:
        sent = await _sent_prompt(mode)
        assert (LANGUAGE_RULE in sent) == (mode != "translate_en"), mode


@pytest.mark.asyncio
async def test_self_correction_rule_only_in_prose_modes():
    from kira.styler import SELF_CORRECTION_RULE, VALID_MODES
    for mode in VALID_MODES:
        sent = await _sent_prompt(mode)
        assert (SELF_CORRECTION_RULE in sent) == (mode in {"plain", "chat", "email", "email_formal"}), mode


@pytest.mark.asyncio
async def test_rules_stand_between_the_prompt_and_the_input():
    from kira.styler import LANGUAGE_RULE, SELF_CORRECTION_RULE
    sent = await _sent_prompt("plain")
    assert sent.index(SELF_CORRECTION_RULE) < sent.index(LANGUAGE_RULE) < sent.index("\nInput:")
    assert sent.rstrip().endswith("Output:")


@pytest.mark.asyncio
async def test_glossary_block_follows_the_rules():
    from kira.styler import LANGUAGE_RULE
    sent = await _sent_prompt("plain", glossary=["LAN"])
    assert sent.index(LANGUAGE_RULE) < sent.index("Möglicherweise gemeinte Begriffe: LAN.") < sent.index("\nInput:")


def test_rules_carry_no_format_braces():
    from kira.styler import LANGUAGE_RULE, SELF_CORRECTION_RULE
    assert "{" not in LANGUAGE_RULE + SELF_CORRECTION_RULE
    assert "}" not in LANGUAGE_RULE + SELF_CORRECTION_RULE


@pytest.mark.asyncio
async def test_polish_with_glossary_inserts_block_before_input():
    styler = Styler(Config())
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "ok"}})
    styler._client = fake_client
    await styler.polish("das Kabel steckt im lahn", mode="terminal", glossary=["LAN", "Kubernetes"])
    sent = fake_client.chat.call_args.kwargs["messages"][0]["content"]
    block_at = sent.index("Möglicherweise gemeinte Begriffe: LAN, Kubernetes.")
    assert block_at < sent.index("\nInput:")
    assert "das Kabel steckt im lahn" in sent
    assert sent.rstrip().endswith("Output:")


def test_glossary_block_is_prepended_without_input_line_and_braces_survive():
    from kira.styler import _template_with_glossary
    out = _template_with_glossary("Nur {text}", ["A{B}"]).format(text="x")
    assert out.startswith("Möglicherweise gemeinte Begriffe: A{B}.")
    assert out.endswith("Nur x")


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


def _chat_answering_after(clock: _FakeClock, seconds: float, load_duration: int | None = None):
    async def chat(**_kwargs):
        clock.now += seconds
        return ChatResponse(
            message=Message(role="assistant", content="Hallo Welt."),
            load_duration=load_duration,
        )
    return chat


@pytest.mark.asyncio
async def test_polish_counts_wall_time_minus_model_load_time(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(styler_module, "time", clock)
    styler = Styler(Config())
    styler._client = MagicMock()
    styler._client.chat = _chat_answering_after(clock, 12.0, load_duration=11_500_000_000)
    observed = []
    monkeypatch.setattr(styler, "_observe_polish_duration", _recording(observed))

    await styler.polish("hallo welt", mode="plain")

    assert observed == [pytest.approx(0.5)]


@pytest.mark.asyncio
async def test_polish_without_load_time_counts_full_wall_time(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(styler_module, "time", clock)
    styler = Styler(Config())
    styler._client = MagicMock()
    styler._client.chat = _chat_answering_after(clock, 12.0)
    observed = []
    monkeypatch.setattr(styler, "_observe_polish_duration", _recording(observed))

    await styler.polish("hallo welt", mode="plain")

    assert observed == [pytest.approx(12.0)]


@pytest.mark.asyncio
async def test_model_load_wait_does_not_switch_to_fast_model(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(styler_module, "time", clock)
    callback = MagicMock()
    styler = Styler(Config(), on_slow_polish_detected=callback)
    styler._client = MagicMock()
    styler._client.chat = _chat_answering_after(clock, 13.5, load_duration=12_900_000_000)

    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        assert await styler.polish("hallo welt", mode="plain") == "Hallo Welt."

    callback.assert_not_called()
    assert styler._force_fast_until is None


@pytest.mark.asyncio
async def test_slow_computation_after_model_load_still_switches(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(styler_module, "time", clock)
    callback = MagicMock()
    styler = Styler(Config(), on_slow_polish_detected=callback)
    styler._client = MagicMock()
    styler._client.chat = _chat_answering_after(clock, 13.5, load_duration=500_000_000)
    styler._client.ps = AsyncMock(return_value=_ps("gemma2:2b", size=RESIDENT_SIZE, size_vram=0))

    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        await styler.polish("hallo welt", mode="plain")

    callback.assert_called_once()
    assert styler._force_fast_until is not None


@pytest.mark.asyncio
async def test_polish_timeouts_still_count_as_slow(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(styler_module, "time", clock)
    callback = MagicMock()
    styler = Styler(Config(), on_slow_polish_detected=callback)

    async def chat_runs_into_limit(**_kwargs):
        clock.now += 26.0
        raise asyncio.TimeoutError()

    styler._client = MagicMock()
    styler._client.chat = chat_runs_into_limit
    styler._client.ps = AsyncMock(return_value=_ps("gemma2:2b", size=RESIDENT_SIZE, size_vram=0))

    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        assert await styler.polish("hallo welt", mode="plain") == "hallo welt"

    callback.assert_called_once()


@pytest.mark.asyncio
async def test_slow_polish_log_names_model_load_share(monkeypatch, caplog):
    clock = _FakeClock()
    monkeypatch.setattr(styler_module, "time", clock)
    styler = Styler(Config())
    styler._client = MagicMock()
    styler._client.chat = _chat_answering_after(clock, 13.5, load_duration=12_900_000_000)
    caplog.set_level(logging.INFO, logger="kira.styler")

    await styler.polish("hallo welt", mode="plain")

    assert "13.5 s, davon 12.9 s Laden" in caplog.text


@pytest.mark.asyncio
async def test_fast_model_switch_log_says_what_counts(caplog):
    caplog.set_level(logging.WARNING, logger="kira.styler")
    styler = Styler(Config())

    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)

    assert "Ladezeit abgezogen, soweit Ollama sie meldet" in caplog.text
    assert "Zeitüberschreitungen zählen voll" in caplog.text


async def _cpu_notice(monkeypatch, caplog, tuning, model="gemma3:12b"):
    monkeypatch.setattr(styler_module, "read_tuning_env", lambda: tuning, raising=False)
    cfg = Config()
    cfg.styler.model = model
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(return_value=_ps(model, size=15_837_303_929, size_vram=0))
    caplog.set_level(logging.WARNING, logger="kira.styler")
    assert await styler.verify_gpu_placement() == "cpu"
    return callback.call_args.args[0]


async def _partial_notice(monkeypatch, caplog, tuning):
    monkeypatch.setattr(styler_module, "read_tuning_env", lambda: tuning, raising=False)
    cfg = Config()
    cfg.styler.model = "gemma3:12b"
    callback = MagicMock()
    styler = Styler(cfg, on_cpu_fallback_detected=callback)
    styler._client = MagicMock()
    styler._client.ps = AsyncMock(
        return_value=_ps("gemma3:12b", size=12_000_000_000, size_vram=6_000_000_000)
    )
    caplog.set_level(logging.WARNING, logger="kira.styler")
    assert await styler.verify_gpu_placement() == "partial"
    return callback.call_args.args[0]


@pytest.mark.asyncio
async def test_cpu_warning_lists_tuning_values_from_user_environment(monkeypatch, caplog):
    notice = await _cpu_notice(monkeypatch, caplog, dict(TUNING_ENV))

    for name, value in TUNING_ENV.items():
        assert f"{name}={value}" in caplog.text
    assert "VRAM-Tuning ist gesetzt" in notice


@pytest.mark.asyncio
async def test_cpu_notice_says_when_tuning_is_missing(monkeypatch, caplog):
    notice = await _cpu_notice(monkeypatch, caplog, {"LLAMA_ARG_CACHE_RAM": "0"})

    assert "OLLAMA_FLASH_ATTENTION fehlt" in caplog.text
    assert "OLLAMA_KV_CACHE_TYPE fehlt" in caplog.text
    assert "VRAM-Tuning fehlt" in notice
    assert "gesetzt" not in notice


@pytest.mark.asyncio
async def test_cpu_notice_makes_no_tuning_claim_when_registry_unreadable(monkeypatch, caplog):
    notice = await _cpu_notice(monkeypatch, caplog, None)

    assert "nicht lesbar" in caplog.text
    assert "VRAM-Tuning" not in notice


@pytest.mark.asyncio
async def test_cpu_notice_fits_windows_balloon_with_installed_model(monkeypatch, caplog):
    for tuning in (dict(TUNING_ENV), {}, None):
        notice = await _cpu_notice(monkeypatch, caplog, tuning, model="gemma4:26b-a4b-it-qat")
        assert len(notice) <= 255, (len(notice), notice)


@pytest.mark.asyncio
async def test_partial_offload_warning_lists_tuning_values(monkeypatch, caplog):
    await _partial_notice(monkeypatch, caplog, dict(TUNING_ENV))

    for name, value in TUNING_ENV.items():
        assert f"{name}={value}" in caplog.text


@pytest.mark.asyncio
async def test_placement_notices_say_politur(monkeypatch, caplog):
    notices = [
        await _cpu_notice(monkeypatch, caplog, dict(TUNING_ENV)),
        await _partial_notice(monkeypatch, caplog, dict(TUNING_ENV)),
    ]

    for notice in notices:
        assert "Politur-Modell" in notice
        assert "Polish" not in notice


RESIDENT_SIZE = 15_837_303_929


async def _three_slow_polishes(monkeypatch, ps):
    clock = _FakeClock()
    monkeypatch.setattr(styler_module, "time", clock)
    callback = MagicMock()
    styler = Styler(Config(), on_slow_polish_detected=callback)
    styler._client = MagicMock()
    styler._client.chat = _chat_answering_after(clock, 13.5, load_duration=500_000_000)
    styler._client.ps = ps
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        await styler.polish("hallo welt", mode="plain")
    return styler, callback


@pytest.mark.asyncio
async def test_slow_polish_does_not_switch_when_model_lies_fully_in_vram(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="kira.styler")
    ps = AsyncMock(return_value=_ps("gemma2:2b", size=RESIDENT_SIZE, size_vram=RESIDENT_SIZE))

    styler, callback = await _three_slow_polishes(monkeypatch, ps)

    callback.assert_not_called()
    assert styler._force_fast_until is None
    assert styler._slow_polish_count == 0
    assert "ganz im Grafikspeicher" in caplog.text


@pytest.mark.asyncio
async def test_slow_polish_switches_when_model_is_not_fully_in_vram(monkeypatch):
    for answer in (
        _ps("gemma2:2b", size=RESIDENT_SIZE, size_vram=0),
        _ps("gemma2:2b", size=RESIDENT_SIZE, size_vram=RESIDENT_SIZE - 1),
        _ps("gemma4:e4b", size=RESIDENT_SIZE, size_vram=RESIDENT_SIZE),
    ):
        styler, callback = await _three_slow_polishes(monkeypatch, AsyncMock(return_value=answer))

        callback.assert_called_once()
        assert styler._force_fast_until is not None


@pytest.mark.asyncio
async def test_slow_polish_switches_when_placement_check_fails(monkeypatch):
    ps = AsyncMock(side_effect=ConnectionError("ps nicht erreichbar"))

    styler, callback = await _three_slow_polishes(monkeypatch, ps)

    callback.assert_called_once()
    assert styler._force_fast_until is not None


@pytest.mark.asyncio
async def test_placement_check_before_switch_waits_only_briefly(monkeypatch):
    monkeypatch.setattr(styler_module, "PLACEMENT_CHECK_TIMEOUT_SEC", 0.05, raising=False)

    async def ps_hangs():
        await asyncio.sleep(30)

    started = time.perf_counter()
    styler, callback = await _three_slow_polishes(monkeypatch, ps_hangs)

    assert time.perf_counter() - started < 5
    callback.assert_called_once()


@pytest.mark.asyncio
async def test_fast_model_is_loaded_only_briefly_while_switched():
    cfg = Config()
    cfg.styler.model = "gemma4:26b-a4b-it-qat"
    cfg.styler.fast_model = "gemma4:e4b"
    styler = Styler(cfg)
    styler._client = MagicMock()
    styler._client.chat = AsyncMock(return_value={"message": {"content": "Hallo Welt."}})
    styler._activate_force_fast()

    await styler.polish("hallo welt", mode="plain")
    await styler.edit_command(selection="text", command="cmd")

    calls = styler._client.chat.call_args_list
    assert [call.kwargs["model"] for call in calls] == ["gemma4:e4b", "gemma4:e4b"]
    keep_alives = [call.kwargs["keep_alive"] for call in calls]
    assert cfg.styler.keep_alive not in keep_alives
    assert set(keep_alives) == {styler_module.FORCE_FAST_KEEP_ALIVE}


def test_short_keep_alive_has_a_unit_and_spans_the_switch_window():
    value = styler_module.FORCE_FAST_KEEP_ALIVE
    assert re.fullmatch(r"\d+[smh]", value)
    assert int(value[:-1]) * {"s": 1, "m": 60, "h": 3600}[value[-1]] == FORCE_FAST_DURATION_SEC


@pytest.mark.asyncio
async def test_other_models_keep_configured_keep_alive_while_switched():
    cfg = Config()
    cfg.styler.fast_model = "gemma4:e4b"
    cfg.styler.modes["translate_en"] = ModeConfig(model="qwen3:8b")
    styler = Styler(cfg)
    styler._client = MagicMock()
    styler._client.chat = AsyncMock(return_value={"message": {"content": "Hello world."}})
    styler._activate_force_fast()

    await styler.polish("hallo welt", mode="translate_en")

    assert styler._client.chat.call_args.kwargs["keep_alive"] == cfg.styler.keep_alive


@pytest.mark.asyncio
async def test_foreign_language_is_named_after_the_language_rule():
    from kira.styler import LANGUAGE_RULE
    sent = await _sent_prompt("email", language="nl")
    assert sent.index(LANGUAGE_RULE) < sent.index("Niederländisch") < sent.index("\nInput:")


@pytest.mark.asyncio
async def test_german_and_unknown_language_add_no_language_line():
    for language in (None, "", "de"):
        sent = await _sent_prompt("email", language=language)
        assert "Der Input steht" not in sent, language


@pytest.mark.asyncio
async def test_language_without_a_name_is_given_by_its_code():
    sent = await _sent_prompt("email", language="sv")
    assert "„sv“" in sent


@pytest.mark.asyncio
async def test_language_line_is_limited_to_the_mail_modes():
    for mode in ("plain", "chat", "terminal", "clean", "code"):
        assert "Niederländisch" not in await _sent_prompt(mode, language="nl"), mode
    for mode in ("email", "email_formal"):
        assert "Niederländisch" in await _sent_prompt(mode, language="nl"), mode


@pytest.mark.asyncio
async def test_language_line_tells_the_model_to_answer_in_that_language():
    sent = await _sent_prompt("email", language="nl")
    assert "Der Input steht auf Niederländisch. Antworte auf Niederländisch, nicht auf Deutsch." in sent


@pytest.mark.asyncio
async def test_translation_mode_gets_no_language_line():
    sent = await _sent_prompt("translate_en", language="nl")
    assert sent == load_prompt("translate_en").format(text="hallo welt")


def _processor_styler(**styler_cfg):
    cfg = Config.model_validate({"whisper": {"device": "cpu"}, "styler": {"model": "gemma4:12b", **styler_cfg}})
    styler = Styler(cfg)
    styler._client = MagicMock()
    styler._client.chat = AsyncMock(return_value={"message": {"content": "Hallo Welt."}})
    return styler


def test_processor_mode_polishes_with_the_fast_model_unless_a_mode_names_one():
    styler = _processor_styler(fast_model="gemma4:e4b", modes={"code": {"model": "qwen3:4b"}})
    assert styler.cpu_mode
    assert styler._resolve_model(None) == "gemma4:e4b"
    assert styler._resolve_model("plain") == "gemma4:e4b"
    assert styler._resolve_model("code") == "qwen3:4b"


@pytest.mark.asyncio
async def test_processor_mode_keeps_every_request_off_the_graphics_card():
    styler = _processor_styler()
    await styler.polish("hallo welt", mode="plain")
    await styler.edit_command("Hallo", "mach das förmlich")
    await styler.warmup()
    assert [call.kwargs["options"].get("num_gpu") for call in styler._client.chat.call_args_list] == [0, 0, 0]


@pytest.mark.asyncio
async def test_graphics_mode_sends_no_num_gpu():
    styler = Styler(Config())
    styler._client = MagicMock()
    styler._client.chat = AsyncMock(return_value={"message": {"content": "Hallo Welt."}})
    await styler.polish("hallo welt", mode="plain")
    assert "num_gpu" not in styler._client.chat.call_args.kwargs["options"]


@pytest.mark.asyncio
async def test_processor_mode_never_reports_slow_polish_or_cpu_fallback():
    slow, fallback = MagicMock(), MagicMock()
    styler = _processor_styler()
    styler.set_on_slow_polish_detected(slow)
    styler.set_on_cpu_fallback_detected(fallback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT + 1):
        await styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 5.0)
    styler._client.ps = AsyncMock(return_value=_ps("gemma4:e4b", size=5_000_000_000, size_vram=0))
    assert await styler.verify_gpu_placement() == "cpu"
    slow.assert_not_called()
    fallback.assert_not_called()
    assert styler._force_fast_until is None
