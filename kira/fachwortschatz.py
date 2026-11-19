# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import difflib
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from kira._resources import assets_dir
from kira.config import LANGUAGE_NAMES
from kira.phonetics import phonetic_code
from kira.wordlist import default_wordlist, is_common

log = logging.getLogger(__name__)

SPRACHEN = tuple(LANGUAGE_NAMES)
SPRACHEN_OHNE_ERKENNUNG = ("de", "en")
GEBIET_NAMEN = {
    "medizin": "der Medizin", "medikamente": "dem Bereich Medikamente und Wirkstoffe", "jura": "dem Recht",
    "wirtschaft": "der Wirtschaft", "technik": "Wissenschaft und Technik", "chemie": "der Chemie", "it": "der IT",
}
SCHWELLE_DEUTSCH = 0.75
SCHWELLE_SONST = 0.8
MIN_BUCHSTABEN = 5
ABSTAND_ZUM_BESTEN = 0.05
SPRACHEN_IM_SPEICHER = 3
_WORT_RE = re.compile(r"\w+")
_VERNEINUNG_RE = re.compile(r"\b\w+n['’]t\b", re.IGNORECASE)
_VERBUNDEN_RE = re.compile(r"\w+(?:[-']\w+)+")
_BUCHSTABEN_RE = re.compile(r"[^\W\d_]")


def standard_verzeichnis() -> Path:
    return assets_dir() / "fachwortschatz"


def _lade_datei(pfad: Path) -> list[str]:
    try:
        zeilen = pfad.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        log.warning("Fachwortschatz: Datei fehlt: %s", pfad.name)
        return []
    return [z.strip() for z in zeilen if z.strip()]


def _reissverschluss(listen: Iterable[list[str]]) -> list[str]:
    listen = [l for l in listen if l]
    ergebnis: list[str] = []
    gesehen: set[str] = set()
    tiefe = max((len(l) for l in listen), default=0)
    for i in range(tiefe):
        for liste in listen:
            if i < len(liste):
                begriff = liste[i]
                schluessel = begriff.casefold()
                if schluessel not in gesehen:
                    gesehen.add(schluessel)
                    ergebnis.append(begriff)
    return ergebnis


def _loeschvarianten(code: str) -> set[str]:
    varianten = {code}
    if len(code) > 2:
        varianten.update(code[:i] + code[i + 1:] for i in range(len(code)))
    return varianten


def _nur_buchstaben(text: str) -> str:
    return "".join(_BUCHSTABEN_RE.findall(text.casefold()))


def _gramme(text: str) -> list[str]:
    woerter = _WORT_RE.findall(_VERNEINUNG_RE.sub(" ", text))
    gramme: list[str] = []
    for n in (1, 2, 3):
        gramme.extend(" ".join(woerter[i:i + n]) for i in range(len(woerter) - n + 1))
    return list(dict.fromkeys(gramme))


class Fachwortschatz:
    def __init__(self, begriffe: dict[str, list[str]], gebiete: Iterable[str] = ()) -> None:
        self.gebiete = [g for g in gebiete if g in GEBIET_NAMEN]
        self._begriffe = {s: begriffe.get(s, []) for s in SPRACHEN}
        self._index: dict[str, dict[str, list[int]]] = {}
        self._bekannte: dict[str, frozenset[str]] = {}

    @classmethod
    def laden(cls, gebiete: Iterable[str], verzeichnis: Path | None = None) -> "Fachwortschatz | None":
        gebiete = list(gebiete)
        if not gebiete:
            return None
        verzeichnis = verzeichnis or standard_verzeichnis()
        begriffe = {
            sprache: _reissverschluss(_lade_datei(verzeichnis / f"{g}-{sprache}.txt") for g in gebiete)
            for sprache in SPRACHEN
        }
        if not any(begriffe.values()):
            return None
        log.info(
            "Fachwortschatz geladen: %s (%s)", ", ".join(gebiete),
            ", ".join(f"{s} {len(b)}" for s, b in begriffe.items()),
        )
        return cls(begriffe, gebiete)

    @property
    def kontext(self) -> list[str]:
        return [GEBIET_NAMEN[g] for g in self.gebiete]

    def begriffe(self, sprache: str) -> list[str]:
        return self._begriffe.get(sprache, [])

    @staticmethod
    def sprachen_fuer(sprache: str | None) -> tuple[str, ...]:
        if sprache in SPRACHEN:
            return (sprache,)
        if not sprache or sprache == "auto":
            return SPRACHEN_OHNE_ERKENNUNG
        return ()

    def vorbereiten(self, sprache: str | None) -> None:
        for s in self.sprachen_fuer(sprache):
            self._index_fuer(s)
            self._bekannt(s)
            default_wordlist(s)

    def _bekannt(self, sprache: str) -> frozenset[str]:
        bekannt = self._bekannte.get(sprache)
        if bekannt is None:
            bekannt = frozenset(b.casefold() for b in self.begriffe(sprache))
            self._bekannte[sprache] = bekannt
        return bekannt

    def _index_fuer(self, sprache: str) -> dict[str, list[int]]:
        index = self._index.get(sprache)
        if index is None:
            index = defaultdict(list)
            for nummer, begriff in enumerate(self.begriffe(sprache)):
                code = phonetic_code(begriff)
                if len(code) < 2:
                    continue
                for variante in _loeschvarianten(code):
                    index[variante].append(nummer)
            self._index[sprache] = index
            for alt in list(self._index)[:-SPRACHEN_IM_SPEICHER]:
                del self._index[alt]
                self._bekannte.pop(alt, None)
        else:
            self._index[sprache] = self._index.pop(sprache)
        return index

    def glossar(self, text: str, sprache: str | None, grenze: int) -> list[str]:
        if not text or grenze <= 0:
            return []
        gramme = _gramme(text)
        vorhanden = {g.casefold() for g in gramme}
        vorhanden.update(t.casefold() for t in _VERBUNDEN_RE.findall(text))
        beste: dict[str, tuple[float, str]] = {}
        sprachen = self.sprachen_fuer(sprache)
        alltag = [default_wordlist(s) for s in sprachen]
        for s in sprachen:
            index = self._index_fuer(s)
            liste = self.begriffe(s)
            bekannt = self._bekannt(s)
            schwelle = SCHWELLE_DEUTSCH if s == "de" else SCHWELLE_SONST
            for gramm in gramme:
                roh = _nur_buchstaben(gramm)
                if len(roh) < MIN_BUCHSTABEN or gramm.casefold() in bekannt:
                    continue
                if any(is_common(gramm, liste_alltag) for liste_alltag in alltag):
                    continue
                code = phonetic_code(gramm)
                if len(code) < 2:
                    continue
                nummern: set[int] = set()
                for variante in _loeschvarianten(code):
                    nummern.update(index.get(variante, ()))
                treffer: list[tuple[float, str]] = []
                for nummer in sorted(nummern):
                    begriff = liste[nummer]
                    if begriff.casefold() in vorhanden:
                        continue
                    ziel = _nur_buchstaben(begriff)
                    if 2 * min(len(roh), len(ziel)) / (len(roh) + len(ziel)) < schwelle:
                        continue
                    wert = difflib.SequenceMatcher(None, roh, ziel, autojunk=False).ratio()
                    if wert >= schwelle:
                        treffer.append((wert, begriff))
                if not treffer:
                    continue
                grenzwert = max(wert for wert, _ in treffer) - ABSTAND_ZUM_BESTEN
                for wert, begriff in treffer:
                    schluessel = begriff.casefold()
                    if wert >= grenzwert and wert > beste.get(schluessel, (0.0, ""))[0]:
                        beste[schluessel] = (wert, begriff)
        geordnet = sorted(beste.values(), key=lambda paar: -paar[0])
        return [begriff for _, begriff in geordnet[:grenze]]
