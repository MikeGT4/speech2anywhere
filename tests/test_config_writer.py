from __future__ import annotations
import pytest
import yaml

from kira.config_writer import update_scalars


SAMPLE_CONFIG = """\
audio:
  # Software gain multiplier applied to raw mic samples.
  # Long lessons-learned comment block here.
  input_gain: 2.0
  # Pinned to the physical microphone.
  input_device: "USB Headset"

whisper:
  # Full Whisper large-v3 model.
  model: C:/Users/user/models/faster-whisper-large-v3
  language: de
  vad_threshold: 0.15

styler:
  # Polish-step LLM. gemma3:12b is the sweet spot.
  model: gemma3:12b
  timeout_seconds: 30.0
"""


def test_update_single_scalar_preserves_comments():
    out = update_scalars(SAMPLE_CONFIG, {"audio.input_gain": 5.0})
    assert "# Software gain multiplier" in out
    assert "# Long lessons-learned" in out
    assert "input_gain: 5.0" in out
    assert "input_gain: 2.0" not in out


def test_update_multiple_scalars_in_one_pass():
    out = update_scalars(SAMPLE_CONFIG, {
        "audio.input_gain": 5.0,
        "whisper.language": "en",
        "styler.timeout_seconds": 60.0,
    })
    assert "input_gain: 5.0" in out
    assert "language: en" in out
    assert "timeout_seconds: 60.0" in out
    assert "input_gain: 2.0" not in out
    assert "language: de" not in out
    assert "timeout_seconds: 30.0" not in out


def test_section_aware_updates_correct_model():
    out = update_scalars(SAMPLE_CONFIG, {"styler.model": "qwen3:8b"})
    assert "model: qwen3:8b" in out
    assert "model: C:/Users/user/models/faster-whisper-large-v3" in out


def test_quotes_string_with_special_chars():
    out = update_scalars(SAMPLE_CONFIG, {"audio.input_device": "Headset Mic"})
    import yaml
    parsed = yaml.safe_load(out)
    assert parsed["audio"]["input_device"] == "Headset Mic"


def test_null_value():
    out = update_scalars(SAMPLE_CONFIG, {"audio.input_device": None})
    import yaml
    parsed = yaml.safe_load(out)
    assert parsed["audio"]["input_device"] is None


def test_int_and_float_values():
    out = update_scalars(SAMPLE_CONFIG, {
        "audio.input_gain": 10,
        "whisper.vad_threshold": 0.5,
    })
    import yaml
    parsed = yaml.safe_load(out)
    assert parsed["audio"]["input_gain"] == 10
    assert parsed["whisper"]["vad_threshold"] == 0.5


def test_unknown_section_appends_at_eof():
    out = update_scalars(SAMPLE_CONFIG, {"hotkey.combo": "f8"})
    assert "hotkey:" in out
    assert "  combo: f8" in out
    import yaml
    parsed = yaml.safe_load(out)
    assert parsed["hotkey"]["combo"] == "f8"
    assert "# Long lessons-learned" in out


def test_unknown_key_in_known_section_appends_in_section():
    out = update_scalars(SAMPLE_CONFIG, {"audio.new_field": 42})
    import yaml
    parsed = yaml.safe_load(out)
    assert parsed["audio"]["new_field"] == 42
    assert out.count("audio:") == 1


def test_multiple_missing_keys_one_existing_one_new_section():
    out = update_scalars(SAMPLE_CONFIG, {
        "audio.gain_boost": 1.5,
        "hotkey.combo": "f8",
        "hotkey.edit_combo": "f9",
    })
    import yaml
    parsed = yaml.safe_load(out)
    assert parsed["audio"]["gain_boost"] == 1.5
    assert parsed["hotkey"]["combo"] == "f8"
    assert parsed["hotkey"]["edit_combo"] == "f9"
    assert parsed["audio"]["input_gain"] == 2.0


def test_existing_keys_still_updated_when_others_missing():
    out = update_scalars(SAMPLE_CONFIG, {
        "audio.input_gain": 5.0,
        "hotkey.edit_combo": "f9",
    })
    import yaml
    parsed = yaml.safe_load(out)
    assert parsed["audio"]["input_gain"] == 5.0
    assert parsed["hotkey"]["edit_combo"] == "f9"


def test_no_section_in_dotted_path_raises():
    with pytest.raises(ValueError):
        update_scalars(SAMPLE_CONFIG, {"flat_key": 1})


def test_idempotent_update():
    out = update_scalars(SAMPLE_CONFIG, {"audio.input_gain": 2.0})
    import yaml
    assert yaml.safe_load(out) == yaml.safe_load(SAMPLE_CONFIG)


def test_blank_lines_between_sections_preserved():
    out = update_scalars(SAMPLE_CONFIG, {"audio.input_gain": 5.0})
    assert "\n\nwhisper:" in out or "\n  \nwhisper:" in out


def test_learning_switch_is_appended_to_old_config():
    from kira.config_writer import update_scalars
    out = update_scalars("audio:\n  input_gain: 1.8\n", {"learning.enabled": False})
    assert "learning:\n  enabled: false\n" in out


def test_list_value_is_written_in_flow_style_and_reads_back():
    out = update_scalars("ui:\n  hud_style: comic\n", {"ui.sound_events": ["start", "fertig"]})
    assert "sound_events: [start, fertig]" in out
    assert yaml.safe_load(out)["ui"] == {"hud_style": "comic", "sound_events": ["start", "fertig"]}


def test_existing_flow_list_is_replaced_in_place():
    out = update_scalars("ui:\n  sound_events: [stopp, fertig]\n  hud_style: comic\n", {"ui.sound_events": []})
    assert out == "ui:\n  sound_events: []\n  hud_style: comic\n"


def test_block_list_is_replaced_without_leftover_items():
    text = "ui:\n  sound_events:\n  - stopp\n  - fertig\n  hud_style: comic\n"
    out = update_scalars(text, {"ui.sound_events": ["fehler"]})
    assert yaml.safe_load(out)["ui"] == {"sound_events": ["fehler"], "hud_style": "comic"}


def test_indented_block_list_is_replaced_without_leftover_items():
    text = "ui:\n  sound_events:\n    - stopp\n    - fertig\nstyler:\n  model: x\n"
    out = update_scalars(text, {"ui.sound_events": ["start"]})
    assert yaml.safe_load(out) == {"ui": {"sound_events": ["start"]}, "styler": {"model": "x"}}


def test_keys_go_on_their_own_line_when_the_file_lacks_a_final_newline():
    out = update_scalars("ui:\n  hud_style: halloween\n  hud_live_words: true",
                         {"ui.sound_feedback": False, "ui.sound_events": ["stopp"]})
    assert yaml.safe_load(out)["ui"] == {"hud_style": "halloween", "hud_live_words": True,
                                         "sound_feedback": False, "sound_events": ["stopp"]}


def test_keys_after_a_final_comment_without_newline_stay_outside_the_comment():
    out = update_scalars("ui:\n  hud_style: comic\n# Ende", {"ui.sound_events": ["fehler"]})
    assert yaml.safe_load(out)["ui"] == {"hud_style": "comic", "sound_events": ["fehler"]}


def test_inserted_keys_follow_the_indent_of_their_section():
    out = update_scalars("ui:\n    hud_style: comic\nstyler:\n    model: x\n", {"ui.sound_events": ["fehler"]})
    assert "    sound_events: [fehler]\n" in out
    assert yaml.safe_load(out) == {"ui": {"hud_style": "comic", "sound_events": ["fehler"]}, "styler": {"model": "x"}}
