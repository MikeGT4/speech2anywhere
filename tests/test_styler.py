import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from ollama import ProcessResponse
from kira.config import Config, ModeConfig
from kira.styler import (
    Styler,
    load_prompt,
    _thinking_kwargs,
    SLOW_POLISH_THRESHOLD_SEC,
    SLOW_POLISH_TRIGGER_COUNT,
)


def _ps(model_name, size, size_vram, *, name=None):
    return ProcessResponse(models=[ProcessResponse.Model(
        model=model_name, name=name if name is not None else model_name,
        size=size, size_vram=size_vram,
    )])


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


def test_observe_fast_polish_does_not_increment_counter():
    cfg = Config()
    styler = Styler(cfg)
    styler._observe_polish_duration(0.5)
    assert styler._slow_polish_count == 0
    assert styler._force_fast_until is None


def test_observe_slow_polish_increments_counter_but_does_not_trigger():
    cfg = Config()
    styler = Styler(cfg)
    styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert styler._slow_polish_count == 1
    assert styler._force_fast_until is None


def test_observe_three_slow_polishes_in_a_row_triggers_force_fast():
    cfg = Config()
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert styler._force_fast_until is not None
    callback.assert_called_once()
    assert styler._slow_polish_count == 0


def test_observe_fast_polish_resets_counter():
    cfg = Config()
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    styler._observe_polish_duration(0.5)
    styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert styler._slow_polish_count == 1
    assert styler._force_fast_until is None
    callback.assert_not_called()


def test_observe_force_fast_active_blocks_re_notification():
    cfg = Config()
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert callback.call_count == 1
    for _ in range(SLOW_POLISH_TRIGGER_COUNT * 2):
        styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
    assert callback.call_count == 1


def test_observe_does_not_switch_when_fast_mode_already_user_enabled():
    cfg = Config()
    cfg.styler.fast_mode = True
    callback = MagicMock()
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
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


def test_callback_exception_does_not_break_observe():
    cfg = Config()
    callback = MagicMock(side_effect=RuntimeError("tray dead"))
    styler = Styler(cfg, on_slow_polish_detected=callback)
    for _ in range(SLOW_POLISH_TRIGGER_COUNT):
        styler._observe_polish_duration(SLOW_POLISH_THRESHOLD_SEC + 1.0)
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
    monkeypatch.setattr(
        styler, "_observe_polish_duration",
        lambda d: observed.append(d),
    )
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


@pytest.mark.asyncio
async def test_polish_without_glossary_sends_unchanged_prompt():
    styler = Styler(Config())
    fake_client = MagicMock()
    fake_client.chat = AsyncMock(return_value={"message": {"content": "Hallo Welt."}})
    styler._client = fake_client
    await styler.polish("hallo welt", mode="plain")
    sent = fake_client.chat.call_args.kwargs["messages"][0]["content"]
    assert sent == load_prompt("plain").format(text="hallo welt")


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
