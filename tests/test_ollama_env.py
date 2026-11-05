from __future__ import annotations

import logging

import kira.ollama_env as oe


def test_tuning_env_disables_llama_server_prompt_cache():
    assert oe.TUNING_ENV["LLAMA_ARG_CACHE_RAM"] == "0"


def test_tuning_env_raises_cuda_jit_cache_to_its_maximum():
    assert oe.TUNING_ENV["CUDA_CACHE_MAXSIZE"] == str(4 * 1024 ** 3)


def test_pending_changes_empty_env_needs_all():
    assert oe.pending_changes({}) == oe.TUNING_ENV


def test_pending_changes_fully_set_needs_nothing():
    assert oe.pending_changes(dict(oe.TUNING_ENV)) == {}


def test_pending_changes_wrong_value_is_pending():
    current = dict(oe.TUNING_ENV)
    current["OLLAMA_KV_CACHE_TYPE"] = "f16"
    assert oe.pending_changes(current) == {
        "OLLAMA_KV_CACHE_TYPE": oe.TUNING_ENV["OLLAMA_KV_CACHE_TYPE"]
    }


def test_pending_changes_partial_only_missing():
    current = dict(oe.TUNING_ENV)
    del current["OLLAMA_KV_CACHE_TYPE"]
    assert oe.pending_changes(current) == {
        "OLLAMA_KV_CACHE_TYPE": oe.TUNING_ENV["OLLAMA_KV_CACHE_TYPE"]
    }


def test_pending_changes_ignores_unrelated_keys():
    current = {"PATH": "C:\\", **oe.TUNING_ENV}
    assert oe.pending_changes(current) == {}


def test_apply_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "linux")
    writes: list[tuple[str, str]] = []
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: writes.append((n, v)))
    monkeypatch.setattr(oe, "_read_user_env", lambda: {})
    assert oe.apply_tuning_env() == []
    assert writes == []


def test_apply_writes_all_when_unset(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "win32")
    monkeypatch.setattr(oe, "_read_user_env", lambda: {})
    writes: dict[str, str] = {}
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: writes.__setitem__(n, v))
    written = oe.apply_tuning_env()
    assert set(written) == set(oe.TUNING_ENV)
    assert writes == oe.TUNING_ENV


def test_apply_noop_when_already_set(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "win32")
    monkeypatch.setattr(oe, "_read_user_env", lambda: dict(oe.TUNING_ENV))
    writes: list[str] = []
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: writes.append(n))
    assert oe.apply_tuning_env() == []
    assert writes == []


def test_apply_writes_only_missing(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "win32")
    current = dict(oe.TUNING_ENV)
    del current["OLLAMA_KV_CACHE_TYPE"]
    monkeypatch.setattr(oe, "_read_user_env", lambda: current)
    writes: dict[str, str] = {}
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: writes.__setitem__(n, v))
    written = oe.apply_tuning_env()
    assert written == ["OLLAMA_KV_CACHE_TYPE"]
    assert writes == {"OLLAMA_KV_CACHE_TYPE": "q8_0"}


def test_apply_returns_empty_when_read_fails(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "win32")
    def boom() -> dict[str, str]:
        raise OSError("registry locked")
    monkeypatch.setattr(oe, "_read_user_env", boom)
    writes: list[str] = []
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: writes.append(n))
    assert oe.apply_tuning_env() == []
    assert writes == []


def test_apply_skips_key_when_write_fails(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "win32")
    monkeypatch.setattr(oe, "_read_user_env", lambda: {})
    def selective_write(name: str, value: str) -> None:
        if name == "OLLAMA_FLASH_ATTENTION":
            raise OSError("access denied")
    monkeypatch.setattr(oe, "_write_user_env", selective_write)
    written = oe.apply_tuning_env()
    assert written == [k for k in oe.TUNING_ENV if k != "OLLAMA_FLASH_ATTENTION"]


FOREIGN_NAME = "FREMDER_SCHLUESSEL"
FOREIGN_VALUE = "darf-nicht-ins-protokoll"


def _windows_registry_with(monkeypatch, current: dict[str, str]) -> None:
    monkeypatch.setattr(oe.sys, "platform", "win32")
    monkeypatch.setattr(oe, "_read_user_env", lambda: {**current, FOREIGN_NAME: FOREIGN_VALUE})


def test_start_log_lists_found_values_when_already_set(monkeypatch, caplog):
    _windows_registry_with(monkeypatch, dict(oe.TUNING_ENV))
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: None)
    caplog.set_level(logging.INFO, logger="kira.ollama_env")

    oe.apply_tuning_env()

    for name, value in oe.TUNING_ENV.items():
        assert f"{name}={value}" in caplog.text
    assert "bereits gesetzt" in caplog.text
    assert FOREIGN_NAME not in caplog.text
    assert FOREIGN_VALUE not in caplog.text


def test_start_log_names_found_and_newly_written_values(monkeypatch, caplog):
    current = dict(oe.TUNING_ENV)
    current["OLLAMA_KV_CACHE_TYPE"] = "f16"
    del current["OLLAMA_FLASH_ATTENTION"]
    _windows_registry_with(monkeypatch, current)
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: None)
    caplog.set_level(logging.INFO, logger="kira.ollama_env")

    oe.apply_tuning_env()

    assert "OLLAMA_FLASH_ATTENTION fehlt" in caplog.text
    assert "OLLAMA_KV_CACHE_TYPE=f16" in caplog.text
    assert "neu gesetzt: OLLAMA_FLASH_ATTENTION, OLLAMA_KV_CACHE_TYPE" in caplog.text
    assert FOREIGN_NAME not in caplog.text
    assert FOREIGN_VALUE not in caplog.text


def test_start_log_names_values_that_could_not_be_written(monkeypatch, caplog):
    _windows_registry_with(monkeypatch, {})

    def refuse_flash_attention(name: str, value: str) -> None:
        if name == "OLLAMA_FLASH_ATTENTION":
            raise OSError("access denied")

    monkeypatch.setattr(oe, "_write_user_env", refuse_flash_attention)
    caplog.set_level(logging.INFO, logger="kira.ollama_env")

    oe.apply_tuning_env()

    assert "nicht gesetzt: OLLAMA_FLASH_ATTENTION" in caplog.text
    assert FOREIGN_VALUE not in caplog.text


def test_start_log_says_skipped_for_other_provider(monkeypatch, caplog):
    monkeypatch.setattr(oe.sys, "platform", "win32")
    reads: list[int] = []
    monkeypatch.setattr(oe, "_read_user_env", lambda: reads.append(1) or {})
    writes: list[str] = []
    monkeypatch.setattr(oe, "_write_user_env", lambda n, v: writes.append(n))
    caplog.set_level(logging.INFO, logger="kira.ollama_env")

    assert oe.apply_tuning_env("openai") == []

    assert "übersprungen (provider=openai)" in caplog.text
    assert reads == []
    assert writes == []


def test_read_error_is_logged_as_warning(monkeypatch, caplog):
    monkeypatch.setattr(oe.sys, "platform", "win32")

    def boom() -> dict[str, str]:
        raise OSError("registry locked")

    monkeypatch.setattr(oe, "_read_user_env", boom)
    caplog.set_level(logging.INFO, logger="kira.ollama_env")

    oe.apply_tuning_env()

    assert [record.levelname for record in caplog.records] == ["WARNING"]
    assert "nicht lesbar" in caplog.text


def test_read_tuning_env_returns_only_own_values(monkeypatch):
    _windows_registry_with(monkeypatch, dict(oe.TUNING_ENV))

    assert oe.read_tuning_env() == oe.TUNING_ENV


def test_read_tuning_env_is_unknown_when_registry_unreadable(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "win32")

    def boom() -> dict[str, str]:
        raise OSError("registry locked")

    monkeypatch.setattr(oe, "_read_user_env", boom)

    assert oe.read_tuning_env() is None


def test_read_tuning_env_is_unknown_off_windows(monkeypatch):
    monkeypatch.setattr(oe.sys, "platform", "darwin")
    monkeypatch.setattr(oe, "_read_user_env", lambda: dict(oe.TUNING_ENV))

    assert oe.read_tuning_env() is None


def test_vram_tuning_set_checks_flash_attention_and_kv_cache():
    assert oe.vram_tuning_set(dict(oe.TUNING_ENV)) is True
    assert oe.vram_tuning_set({"OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": "q8_0"}) is True
    assert oe.vram_tuning_set({**oe.TUNING_ENV, "OLLAMA_KV_CACHE_TYPE": "f16"}) is False
    assert oe.vram_tuning_set({}) is False
    assert oe.vram_tuning_set(None) is None


def test_describe_tuning_env_marks_unreadable_registry():
    assert oe.describe_tuning_env(None) == "nicht lesbar"
