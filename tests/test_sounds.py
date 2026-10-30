# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import os
import sys
import tomllib
import types
import wave
from pathlib import Path

import numpy as np
import pytest

from kira._resources import assets_dir
from kira.app import State
from kira.config import HUD_STYLES, SOUND_EVENTS
from kira.sounds import SoundPlayer


def _player(tmp_path, yaml_text, sounds_dir=None):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml_text, encoding="utf-8")
    played: list[Path] = []
    player = SoundPlayer(config_path=cfg, sounds_dir=sounds_dir, play=played.append)
    return player, played, cfg


def _touch_later(path: Path, seconds: float) -> None:
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + seconds))


def test_sounds_stay_silent_by_default(tmp_path):
    player, played, _ = _player(tmp_path, "ui:\n  hud_style: manga\n")
    for state in State:
        player.on_state(state)
    assert played == []


def test_enabled_sounds_follow_release_result_and_error(tmp_path):
    player, played, _ = _player(tmp_path, "ui:\n  hud_style: manga\n  sound_feedback: true\n")
    for state in (State.RECORDING, State.TRANSCRIBING, State.STYLING, State.INJECTING, State.IDLE, State.ERROR):
        player.on_state(state)
    assert [(p.parent.name, p.stem) for p in played] == [("manga", "stopp"), ("manga", "fertig"), ("manga", "fehler")]


def test_start_sound_plays_only_when_listed(tmp_path):
    player, played, _ = _player(
        tmp_path, "ui:\n  hud_style: comic\n  sound_feedback: true\n  sound_events: [start, fertig]\n",
    )
    for state in (State.RECORDING, State.TRANSCRIBING, State.INJECTING, State.ERROR):
        player.on_state(state)
    assert [p.stem for p in played] == ["start", "fertig"]


def test_style_and_switch_changes_apply_without_restart(tmp_path):
    player, played, cfg = _player(tmp_path, "ui:\n  hud_style: comic\n  sound_feedback: true\n")
    player.on_state(State.INJECTING)
    cfg.write_text("ui:\n  hud_style: weihnachten\n  sound_feedback: true\n", encoding="utf-8")
    _touch_later(cfg, 5)
    player.on_state(State.INJECTING)
    cfg.write_text("ui:\n  hud_style: weihnachten\n  sound_feedback: false\n", encoding="utf-8")
    _touch_later(cfg, 10)
    player.on_state(State.INJECTING)
    assert [p.parent.name for p in played] == ["comic", "weihnachten"]


def test_missing_sound_is_skipped_and_logged_once(tmp_path, caplog):
    player, played, _ = _player(
        tmp_path, "ui:\n  hud_style: comic\n  sound_feedback: true\n", sounds_dir=tmp_path / "leer",
    )
    player.on_state(State.INJECTING)
    player.on_state(State.INJECTING)
    assert played == []
    assert sum("Ton fehlt" in record.getMessage() for record in caplog.records) == 1


def test_failing_playback_never_reaches_the_dictation(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("ui:\n  sound_feedback: true\n", encoding="utf-8")

    def broken(path):
        raise RuntimeError("kein Ausgabegerät")

    player = SoundPlayer(config_path=cfg, play=broken)
    player.on_state(State.INJECTING)
    assert player.play("comic", "fertig") is False


def test_preview_plays_a_style_even_when_switched_off(tmp_path):
    player, played, _ = _player(tmp_path, "ui:\n  hud_style: comic\n")
    assert player.play("klartext", "fertig") is True
    assert [(p.parent.name, p.stem) for p in played] == [("klartext", "fertig")]


def test_unknown_style_or_event_plays_nothing(tmp_path):
    player, played, _ = _player(tmp_path, "ui:\n  sound_feedback: true\n")
    assert player.play("gibt-es-nicht", "fertig") is False
    assert player.play("comic", "../comic/fertig") is False
    assert played == []


def test_all_variants_of_an_event_are_offered_to_the_chooser(tmp_path):
    folder = tmp_path / "toene" / "weihnachten"
    folder.mkdir(parents=True)
    for name in ("fertig.wav", "fertig-2.wav", "fertig-x.wav", "fertig-3.txt", "fehler.wav"):
        (folder / name).write_bytes(b"")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("ui:\n  hud_style: weihnachten\n  sound_feedback: true\n", encoding="utf-8")
    offered: list[list[str]] = []

    def last(paths):
        offered.append([path.name for path in paths])
        return paths[-1]

    played: list[Path] = []
    player = SoundPlayer(config_path=cfg, sounds_dir=tmp_path / "toene", play=played.append, choose=last)
    player.on_state(State.INJECTING)
    player.on_state(State.ERROR)
    assert player.play("weihnachten", "fertig") is True
    assert offered == [["fertig.wav", "fertig-2.wav"], ["fehler.wav"], ["fertig.wav", "fertig-2.wav"]]
    assert [path.name for path in played] == ["fertig-2.wav", "fehler.wav", "fertig-2.wav"]


def test_christmas_ships_two_finish_and_three_error_variants():
    folder = assets_dir() / "sounds" / "weihnachten"
    assert sorted(path.name for path in folder.glob("fertig*.wav")) == ["fertig-2.wav", "fertig.wav"]
    assert sorted(path.name for path in folder.glob("fehler*.wav")) == ["fehler-2.wav", "fehler-3.wav", "fehler.wav"]


def test_the_chooser_is_random_by_default(tmp_path):
    import random
    assert SoundPlayer(config_path=tmp_path / "config.yaml")._choose is random.choice


def test_odd_variant_names_are_ignored(tmp_path):
    folder = tmp_path / "toene" / "comic"
    folder.mkdir(parents=True)
    for name in ("fertig.wav", "fertig-\u00b2.wav", "fertig-02.wav", "fertig-.wav", "fertig-1.5.wav"):
        (folder / name).write_bytes(b"")
    offered: list[list[str]] = []

    def first(paths):
        offered.append([path.name for path in paths])
        return paths[0]

    player = SoundPlayer(config_path=tmp_path / "config.yaml", sounds_dir=tmp_path / "toene", play=lambda path: None,
                         choose=first)
    assert player.play("comic", "fertig") is True
    assert offered == [["fertig.wav", "fertig-02.wav"]]


def test_a_failing_sound_lookup_never_reaches_the_dictation(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("ui:\n  sound_feedback: true\n", encoding="utf-8")

    def broken(paths):
        raise RuntimeError("kaputt")

    player = SoundPlayer(config_path=cfg, play=lambda path: None, choose=broken)
    player.on_state(State.INJECTING)


@pytest.mark.parametrize("style", HUD_STYLES)
@pytest.mark.parametrize("event", SOUND_EVENTS)
def test_every_style_ships_all_four_events(style, event):
    assert (assets_dir() / "sounds" / style / f"{event}.wav").is_file()


@pytest.mark.parametrize(
    "path", sorted((assets_dir() / "sounds").glob("*/*.wav")), ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_every_shipped_sound_is_short_quiet_mono(path):
    with wave.open(str(path), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
        frames = w.getnframes()
        data = np.frombuffer(w.readframes(frames), dtype="<i2").astype(np.int32)
    assert 0.03 < frames / 44100 < 1.5
    assert np.abs(data).max() / 32768 < 10 ** (-6 / 20)


def test_wheel_ships_the_sounds():
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    mapping = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert mapping.get("assets/sounds") == "kira/_assets/sounds"


def test_windows_playback_is_asynchronous_without_fallback_beep(monkeypatch, tmp_path):
    import kira.sounds as sounds

    calls = []
    fake = types.SimpleNamespace(
        SND_FILENAME=0x20000, SND_ASYNC=0x1, SND_NODEFAULT=0x2,
        PlaySound=lambda name, flags: calls.append((name, flags)),
    )
    monkeypatch.setitem(sys.modules, "winsound", fake)
    sounds._winsound_play(tmp_path / "fertig.wav")
    assert calls == [(str(tmp_path / "fertig.wav"), 0x20000 | 0x1 | 0x2)]
