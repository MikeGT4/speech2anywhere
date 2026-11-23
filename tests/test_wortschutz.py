# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest

from kira.app import KiraApp, _StubInjector
from kira.config import Config
from kira.recorder import Recorder
from kira.wortschutz import protect


@pytest.mark.parametrize("source, polished, uncertain, expected", [
    ("Dollar ist drin.", "Docker ist drin", [], "Dollar ist drin"),
    ("Dollar ist drin.", "Docker ist drin", ["Dollar"], "Docker ist drin"),
    ("dass es ohne N8 einläuft?", "dass es ohne 1NCE einläuft", [], "dass es ohne N8 einläuft"),
    ("Also, pass auf, da hat auch", "Pass auf, da hat auch", [], "Pass auf, da hat auch"),
    ("in den WhatsApp-Fälle aufgewiesen.", "in den WhatsApp-Fällen aufgewiesen.", [],
     "in den WhatsApp-Fällen aufgewiesen."),
    ("Ich hab die Minis weggeschickt.", "Ich habe die Minis weggeschickt.", [], "Ich habe die Minis weggeschickt."),
    ("am Dienstag, nein, am Freitag.", "am Freitag.", [], "am Freitag."),
    ("über Kann Bahn Karte", "über Kanban-Karte", [], "über Kann Bahn Karte"),
    ("das sind zwei Dateien", "das sind 2 Dateien", [], "das sind 2 Dateien"),
    ("mach mal git pull", "Mach mal git pull.", [], "Mach mal git pull."),
])
def test_protect_keeps_certain_words(source, polished, uncertain, expected):
    assert protect(source, polished, uncertain)[0] == expected


def test_protect_allows_offered_terms():
    out, reverted = protect("über Kann Bahn Karte", "über Kanban-Karte", [], ["Kanban-Karte"])
    assert out == "über Kanban-Karte" and reverted == []


def test_protect_removes_invented_words():
    out, reverted = protect("das ist drin", "das ist schon drin", [])
    assert out == "das ist drin"
    assert reverted == [("", "schon")]


def test_protect_capitalizes_restored_sentence_start():
    assert protect("dollar ist drin", "Docker ist drin.", [])[0] == "Dollar ist drin."


class _Transcriber:
    def transcribe(self, audio):
        return SimpleNamespace(text="Dollar ist drin.", language="de", uncertain_words=(),
                               avg_logprob=-0.2, raw_text="Dollar ist drin.", language_probability=0.99)


class _Styler:
    def __init__(self, answer):
        self.answer, self.modes = answer, []

    async def polish(self, text, mode, **kwargs):
        self.modes.append((mode, kwargs))
        return self.answer


def _run(monkeypatch, mode, answer, wortgetreu=False):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: mode)
    cfg = Config()
    cfg.styler.wortgetreu = wortgetreu
    styler, injector = _Styler(answer), _StubInjector()
    app = KiraApp(config=cfg, recorder=Recorder(), transcriber=_Transcriber(),
                  styler=styler, injector=injector)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    return injector.last, styler.modes


def test_pipeline_reverts_swapped_certain_word(monkeypatch):
    out, _ = _run(monkeypatch, "plain", "Docker ist drin.")
    assert out == "Dollar ist drin."


def test_pipeline_leaves_mail_untouched(monkeypatch):
    out, _ = _run(monkeypatch, "email", "Docker ist drin.")
    assert out == "Docker ist drin."


def test_wortgetreu_uses_its_own_prompt_without_terms(monkeypatch):
    out, modes = _run(monkeypatch, "chat", "Dollar ist drin.", wortgetreu=True)
    assert [m for m, _ in modes] == ["wortgetreu"]
    assert "glossary" not in modes[0][1] and "fachgebiete" not in modes[0][1]
    assert out == "Dollar ist drin."


def test_wortgetreu_keeps_mail_mode(monkeypatch):
    _, modes = _run(monkeypatch, "email", "Hallo", wortgetreu=True)
    assert modes[0][0] == "email"


def test_pipeline_leaves_terminal_commands_untouched(monkeypatch):
    out, _ = _run(monkeypatch, "terminal", "Docker ist drin.")
    assert out == "Docker ist drin."
