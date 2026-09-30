from __future__ import annotations
import re
import sys
import textwrap
from pathlib import Path
import pytest
from kira.config import Config, effective_hotkey, load_config


def test_load_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg.hotkey.combo == "fn"
    assert cfg.whisper.model == "mlx-community/whisper-large-v3-turbo"
    assert cfg.styler.provider == "ollama"
    assert cfg.styler.model == "gemma2:2b"
    assert cfg.injector.strategy == "clipboard"


def test_load_from_yaml(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(textwrap.dedent("""
        hotkey:
          combo: ctrl+shift+d
          min_duration_ms: 500
        styler:
          provider: ollama
          model: llama3.2:3b
          timeout_seconds: 5
          fallback_to_raw: true
    """))
    cfg = load_config(yaml_file)
    assert cfg.hotkey.combo == "ctrl+shift+d"
    assert cfg.hotkey.min_duration_ms == 500
    assert cfg.styler.model == "llama3.2:3b"


def test_invalid_provider_raises(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("styler:\n  provider: invalid\n")
    with pytest.raises(ValueError):
        load_config(yaml_file)


def test_default_config_path_mac(monkeypatch):
    from kira import config as cfg_mod
    monkeypatch.setattr(cfg_mod.sys, "platform", "darwin")
    monkeypatch.setattr(cfg_mod, "_HOME", Path("/Users/fake"))
    p = cfg_mod.default_config_path()
    assert p.as_posix() == "/Users/fake/.config/kira/config.yaml"


def test_default_config_path_windows(monkeypatch):
    from kira import config as cfg_mod
    monkeypatch.setattr(cfg_mod.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\Fake\AppData\Roaming")
    p = cfg_mod.default_config_path()
    assert str(p).replace("/", "\\") == r"C:\Users\Fake\AppData\Roaming\Kira\config.yaml"


def test_config_defaults_validate():
    from kira.config import Config
    c = Config()
    assert c.whisper.model
    assert c.styler.provider == "ollama"


def test_default_context_modes_platform_specific(monkeypatch):
    from kira import config as cfg_mod
    monkeypatch.setattr(cfg_mod.sys, "platform", "win32")
    modes = cfg_mod.platform_context_modes()
    assert modes.get("outlook.exe") == "email"

    monkeypatch.setattr(cfg_mod.sys, "platform", "darwin")
    modes = cfg_mod.platform_context_modes()
    assert modes.get("com.apple.mail") == "email"


def test_effective_hotkey_maps_fn_to_f8_on_windows(monkeypatch):
    from kira import config as cfg_mod
    monkeypatch.setattr(cfg_mod.sys, "platform", "win32")
    assert cfg_mod.effective_hotkey("fn") == "f8"


def test_effective_hotkey_keeps_fn_on_mac(monkeypatch):
    from kira import config as cfg_mod
    monkeypatch.setattr(cfg_mod.sys, "platform", "darwin")
    assert cfg_mod.effective_hotkey("fn") == "fn"


def test_effective_hotkey_passes_explicit_combo_through(monkeypatch):
    from kira import config as cfg_mod
    monkeypatch.setattr(cfg_mod.sys, "platform", "win32")
    assert cfg_mod.effective_hotkey("ctrl+shift+space") == "ctrl+shift+space"
    assert cfg_mod.effective_hotkey("f10") == "f10"


def test_styler_fast_mode_defaults_off():
    c = Config()
    assert c.styler.fast_mode is False
    assert c.styler.fast_model == "gemma4:e4b"


def test_styler_fast_mode_loaded_from_yaml(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(textwrap.dedent("""
        styler:
          model: gemma3:12b
          fast_mode: true
          fast_model: gemma3:4b
    """))
    cfg = load_config(yaml_file)
    assert cfg.styler.fast_mode is True
    assert cfg.styler.fast_model == "gemma3:4b"
    assert cfg.styler.model == "gemma3:12b"


def test_updates_check_on_start_defaults_on():
    c = Config()
    assert c.updates.check_on_start is True


def test_updates_check_on_start_can_be_disabled_via_yaml(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(textwrap.dedent("""
        updates:
          check_on_start: false
    """))
    cfg = load_config(yaml_file)
    assert cfg.updates.check_on_start is False


def test_updates_section_optional_in_yaml(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("styler:\n  model: gemma3:12b\n")
    cfg = load_config(yaml_file)
    assert cfg.updates.check_on_start is True


def test_context_modes_yaml_merges_with_builtin_table(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "context_modes:\n"
        "  mychat.exe: chat\n"
        "  outlook.exe: plain\n"
    )
    cfg = load_config(yaml_file)
    assert cfg.context_modes["mychat.exe"] == "chat"
    assert cfg.context_modes["outlook.exe"] == "plain"
    assert "cmd.exe" in cfg.context_modes


def test_context_modes_absent_yields_full_builtin_table(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("styler:\n  model: gemma3:12b\n")
    cfg = load_config(yaml_file)
    assert len(cfg.context_modes) > 5


def test_learning_defaults():
    from kira.config import Config
    cfg = Config()
    assert cfg.learning.enabled is True
    assert cfg.learning.sources == []


def test_learning_section_is_read_from_yaml(tmp_path):
    from kira.config import load_config
    path = tmp_path / "config.yaml"
    path.write_text(
        "learning:\n  enabled: false\n  sources:\n    - C:/daten/verlaeufe\n",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.learning.enabled is False
    assert cfg.learning.sources == ["C:/daten/verlaeufe"]


def test_hud_defaults_are_comic_at_150_percent(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg.ui.hud_style == "comic"
    assert cfg.ui.hud_scale == 1.5


def test_explicit_phosphor_stays_phosphor(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text("ui:\n  hud_style: phosphor\n", encoding="utf-8")
    assert load_config(yaml_file).ui.hud_style == "phosphor"


@pytest.mark.parametrize("raw, expected", [
    ("gun_barrel", "gun_barrel"),
    ("  Klartext ", "klartext"),
    ("gibtsnicht", "comic"),
    ("", "comic"),
    (None, "comic"),
])
def test_hud_style_unknown_falls_back_to_default(tmp_path, raw, expected):
    yaml_file = tmp_path / "config.yaml"
    value = "null" if raw is None else repr(raw)
    yaml_file.write_text(f"ui:\n  hud_style: {value}\n", encoding="utf-8")
    assert load_config(yaml_file).ui.hud_style == expected


@pytest.mark.parametrize("raw, expected", [
    ("1.0", 1.0), ("2", 2.0), ("0.1", 0.75), ("9", 3.0), ("'gross'", 1.5), (".nan", 1.5),
])
def test_hud_scale_is_bounded(tmp_path, raw, expected):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(f"ui:\n  hud_scale: {raw}\n", encoding="utf-8")
    assert load_config(yaml_file).ui.hud_scale == expected


def test_update_interval_default_and_bounds(tmp_path):
    assert load_config(tmp_path / "missing.yaml").updates.check_interval_hours == 6.0
    yaml_file = tmp_path / "config.yaml"
    for raw, expected in (("0", 0.0), ("-3", 0.0), ("0.01", 1.0), ("0.5", 1.0), ("12", 12.0),
                          ("1000", 168.0), ("'oft'", 6.0), (".nan", 6.0)):
        yaml_file.write_text(f"updates:\n  check_interval_hours: {raw}\n", encoding="utf-8")
        assert load_config(yaml_file).updates.check_interval_hours == expected


def test_config_template_names_neither_old_product_nor_developer():
    template = Path(__file__).resolve().parent.parent / "installer" / "config.yaml.template"
    text = template.read_text(encoding="utf-8")
    assert "kira" not in text.lower()
    assert re.findall(r"C:/Users/([^/]+)/", text) == ["${USERNAME}"]
