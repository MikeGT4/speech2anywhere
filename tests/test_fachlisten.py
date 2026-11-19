# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import pytest

from kira.config import FACHGEBIETE
from kira.fachwortschatz import SPRACHEN, standard_verzeichnis


def _zeilen(gebiet: str, sprache: str) -> list[str]:
    return (standard_verzeichnis() / f"{gebiet}-{sprache}.txt").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("gebiet", FACHGEBIETE)
@pytest.mark.parametrize("sprache", SPRACHEN)
def test_liste_ohne_doppelte_und_ohne_gedankenstrich(gebiet, sprache):
    zeilen = _zeilen(gebiet, sprache)
    assert len({z.casefold() for z in zeilen}) == len(zeilen)
    assert not any(chr(0x2014) in z for z in zeilen)


@pytest.mark.parametrize("gebiet, sprache, begriff", [
    ("medikamente", "de", "Metoprolol"),
    ("medikamente", "en", "metoprolol"),
    ("it", "de", "nginx"),
    ("it", "en", "nginx"),
    ("medizin", "de", "Myokardinfarkt"),
    ("medizin", "de", "Pneumonie"),
])
def test_gaengige_fachbegriffe_vorhanden(gebiet, sprache, begriff):
    assert begriff.casefold() in {z.casefold() for z in _zeilen(gebiet, sprache)}


@pytest.mark.parametrize("begriff", ["Myokardinfarkt", "Pneumonie"])
def test_fachsynonym_steht_bei_haeufigen_eintraegen_vorn(begriff):
    zeilen = [z.casefold() for z in _zeilen("medizin", "de")]
    assert zeilen.index(begriff.casefold()) < 1000
