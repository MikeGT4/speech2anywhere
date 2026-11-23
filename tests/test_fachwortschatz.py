# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import asyncio
import time

import numpy as np
import pytest

from kira.app import KiraApp, _StubInjector, _StubTranscriber
from kira.config import FACHGEBIETE, Config
from kira.fachwortschatz import SPRACHEN, Fachwortschatz, standard_verzeichnis
from kira.recorder import Recorder


def _woerter(text: str) -> int:
    return len(text.replace(",", " ").split())


@pytest.fixture
def verzeichnis(tmp_path):
    (tmp_path / "medizin-de.txt").write_text("Hypothyreose\nAppendizitis\nTachykardie\n", encoding="utf-8")
    (tmp_path / "medizin-en.txt").write_text("hypothyroidism\nappendicitis\n", encoding="utf-8")
    (tmp_path / "it-de.txt").write_text("Kubernetes\nTachykardie\n", encoding="utf-8")
    (tmp_path / "it-en.txt").write_text("Kubernetes\n", encoding="utf-8")
    return tmp_path


def test_ohne_gebiete_kein_fachwortschatz(verzeichnis):
    assert Fachwortschatz.laden([], verzeichnis) is None


def test_fehlende_dateien_ergeben_keinen_fachwortschatz(tmp_path):
    assert Fachwortschatz.laden(["medizin"], tmp_path) is None


def test_gebiete_werden_im_wechsel_gemischt_ohne_doppelte(verzeichnis):
    fw = Fachwortschatz.laden(["medizin", "it"], verzeichnis)
    assert fw.begriffe("de") == ["Hypothyreose", "Kubernetes", "Appendizitis", "Tachykardie"]
    assert fw.begriffe("en") == ["hypothyroidism", "Kubernetes", "appendicitis"]


@pytest.mark.parametrize("sprache, erwartet", [
    ("de", ("de",)), ("en", ("en",)), ("fr", ("fr",)), ("auto", ("de", "en")), (None, ("de", "en")), ("ja", ()),
])
def test_sprachen_je_einstellung(sprache, erwartet):
    assert Fachwortschatz.sprachen_fuer(sprache) == erwartet


def test_glossar_findet_falsch_erkannten_fachbegriff(verzeichnis):
    fw = Fachwortschatz.laden(["medizin"], verzeichnis)
    assert fw.glossar("Der Patient hat eine Hypo Tyreose.", "de", 5) == ["Hypothyreose"]


def test_glossar_laesst_richtig_erkannte_begriffe_weg(verzeichnis):
    fw = Fachwortschatz.laden(["medizin"], verzeichnis)
    assert fw.glossar("Verdacht auf Appendizitis.", "de", 5) == []


def test_glossar_ohne_aehnlichkeit_bleibt_leer(verzeichnis):
    fw = Fachwortschatz.laden(["medizin"], verzeichnis)
    assert fw.glossar("Morgen gehen wir einkaufen und dann ins Kino.", "de", 5) == []


def test_glossar_schlaegt_fuer_alltagswoerter_nichts_vor(tmp_path):
    (tmp_path / "jura-de.txt").write_text("Landesgericht\nVerfügungen\n", encoding="utf-8")
    fw = Fachwortschatz.laden(["jura"], tmp_path)
    assert fw.glossar("Wir beantragen die Verfügung beim Landgericht.", "de", 5) == []


def test_glossar_schlaegt_auch_englisch_fuer_alltagswoerter_nichts_vor(tmp_path):
    (tmp_path / "medizin-en.txt").write_text("massage\nappendicitis\n", encoding="utf-8")
    fw = Fachwortschatz.laden(["medizin"], tmp_path)
    assert fw.glossar("Please send me a message about the apendicitis.", "en", 5) == ["appendicitis"]


def test_ohne_feste_sprache_zaehlen_die_alltagswoerter_beider_sprachen(tmp_path):
    (tmp_path / "medizin-de.txt").write_text("Appendizitis\n", encoding="utf-8")
    (tmp_path / "medizin-en.txt").write_text("infection\ntherapy\n", encoding="utf-8")
    fw = Fachwortschatz.laden(["medizin"], tmp_path)
    assert fw.glossar("Der Patient hat eine Infektion, die Therapie hilft.", "auto", 5) == []


def test_englische_verneinungen_loesen_keinen_vorschlag_aus(tmp_path):
    (tmp_path / "medizin-en.txt").write_text("shoulder\nweren\n", encoding="utf-8")
    fw = Fachwortschatz.laden(["medizin"], tmp_path)
    assert fw.glossar("We weren't sure, so we shouldn’t wait.", "en", 5) == []


def test_alltagswortlisten_fuer_alle_sprachen_mitgeliefert():
    from kira.wordlist import default_wordlist
    for sprache in SPRACHEN:
        assert len(default_wordlist(sprache)) > 40000, sprache


def test_glossar_ordnet_nach_aehnlichkeit(tmp_path):
    (tmp_path / "medizin-de.txt").write_text("Kolposkopie\nLaparoskopie\n", encoding="utf-8")
    fw = Fachwortschatz.laden(["medizin"], tmp_path)
    assert fw.glossar("Wir veranlassen eine Leparoskopie.", "de", 5)[0] == "Laparoskopie"


def test_glossar_nimmt_je_wort_nur_die_naechsten_begriffe(tmp_path):
    (tmp_path / "medizin-de.txt").write_text("Hyperthyreose\nHypothyreose\n", encoding="utf-8")
    fw = Fachwortschatz.laden(["medizin"], tmp_path)
    assert fw.glossar("Der Patient hat eine Hypo Tyreose.", "de", 5) == ["Hypothyreose"]


def test_hoechstens_drei_sprachen_bleiben_im_speicher(verzeichnis):
    fw = Fachwortschatz.laden(["medizin"], verzeichnis)
    for sprache in ("de", "en", "fr", "it", "de"):
        fw.glossar("Hypo Tyreose", sprache, 5)
    assert list(fw._index) == ["fr", "it", "de"]
    assert fw.glossar("Hypo Tyreose", "de", 5) == ["Hypothyreose"]


def test_glossar_achtet_auf_grenze(verzeichnis):
    fw = Fachwortschatz.laden(["medizin"], verzeichnis)
    assert len(fw.glossar("Hypo Tyreose und Tachy Kardie", "de", 1)) == 1


def test_mitgelieferte_listen_vollstaendig():
    verzeichnis = standard_verzeichnis()
    for gebiet in FACHGEBIETE:
        for sprache in SPRACHEN:
            pfad = verzeichnis / f"{gebiet}-{sprache}.txt"
            assert pfad.exists(), pfad.name
            zeilen = pfad.read_text(encoding="utf-8").splitlines()
            assert 100 <= len(zeilen) <= 6000, pfad.name
            assert all(z and z == z.strip() for z in zeilen), pfad.name


def test_glossar_mit_allen_listen_ist_schnell():
    fw = Fachwortschatz.laden(FACHGEBIETE)
    text = (
        "Ich habe heute mit dem Kollegen über die Hypo Tyreose gesprochen, danach haben wir den "
        "Kuber Netes Cluster neu gestartet und die Bilanz für das dritte Quartal angesehen. "
    ) * 3
    fw.glossar("Aufwärmen", "auto", 5)
    start = time.perf_counter()
    fw.glossar(text, "auto", 5)
    assert (time.perf_counter() - start) < 0.1


class _Lernen:
    def __init__(self, begriffe):
        self.begriffe = begriffe

    def glossary_for(self, text, uncertain=None):
        return self.begriffe

    def after_inject(self, **kwargs):
        pass


class _Politur:
    def __init__(self):
        self.glossare = []

    async def polish(self, text, mode, glossary=None, **kwargs):
        self.glossare.append(glossary)
        return text


class _Fach:
    kontext: list[str] = []

    def __init__(self, begriffe, fehler=False):
        self.begriffe, self.fehler, self.aufrufe = begriffe, fehler, []

    def glossar(self, text, sprache, grenze, unsicher=None):
        self.aufrufe.append((text, sprache, grenze))
        if self.fehler:
            raise RuntimeError("kaputt")
        return self.begriffe


def _lauf(learning, fach, monkeypatch):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    politur = _Politur()
    app = KiraApp(config=Config(), recorder=Recorder(), transcriber=_StubTranscriber(),
                  styler=politur, injector=_StubInjector(), learning=learning, fachwortschatz=fach)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    return politur.glossare


def test_fachbegriffe_erreichen_die_politur_ohne_lernen(monkeypatch):
    fach = _Fach(["Hypothyreose"])
    assert _lauf(None, fach, monkeypatch) == [["Hypothyreose"]]
    assert fach.aufrufe[0][0] == "stub"


def test_gelernte_begriffe_zuerst_hoechstens_fuenf(monkeypatch):
    fach = _Fach(["Zettelkasten", "B", "C", "D", "E", "F"])
    assert _lauf(_Lernen(["Zettelkasten", "A"]), fach, monkeypatch) == [["Zettelkasten", "A", "B", "C", "D"]]


def test_kaputter_fachwortschatz_bricht_kein_diktat(monkeypatch):
    assert _lauf(_Lernen(["A"]), _Fach([], fehler=True), monkeypatch) == [["A"]]


def test_kontext_nennt_die_gebiete(verzeichnis):
    assert Fachwortschatz.laden(["medizin", "it"], verzeichnis).kontext == ["der Medizin", "der IT"]


def test_politur_bekommt_den_kontext(monkeypatch):
    from kira.styler import _template_with_fachgebiete
    vorlage = "Regeln\nInput:\n{text}"
    assert _template_with_fachgebiete(vorlage, None) == vorlage
    mit = _template_with_fachgebiete(vorlage, ["der Medizin", "der Chemie", "der IT"])
    assert "aus der Medizin, der Chemie oder der IT" in mit
    assert mit.index("Fachgebiet:") < mit.index("Input:")
    assert mit.format(text="x").endswith("x")


def test_app_reicht_kontext_nur_mit_fachwortschatz_weiter(monkeypatch):
    class Politur:
        def __init__(self):
            self.kwargs = []

        async def polish(self, text, mode, **kwargs):
            self.kwargs.append(kwargs)
            return text

    class Fach(_Fach):
        kontext = ["der Medizin"]

    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    for fach, erwartet in ((None, None), (Fach([]), None), (Fach(["Hypothyreose"]), ["der Medizin"])):
        politur = Politur()
        app = KiraApp(config=Config(), recorder=Recorder(), transcriber=_StubTranscriber(),
                      styler=politur, injector=_StubInjector(), fachwortschatz=fach)
        asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
        assert politur.kwargs[0].get("fachgebiete") == erwartet


@pytest.mark.parametrize("modus, erwartet", [
    ("plain", True), ("chat", True), ("email", True), ("email_formal", True),
    ("terminal", True), ("code", True), ("clean", True), ("translate_en", True),
])
def test_fachwortschatz_wirkt_in_jedem_modus(monkeypatch, modus, erwartet):
    class Politur:
        def __init__(self):
            self.kwargs = []

        async def polish(self, text, mode, **kwargs):
            self.kwargs.append(kwargs)
            return text

    class Fach(_Fach):
        kontext = ["der IT"]

    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: modus)
    politur, fach = Politur(), Fach(["Kubernetes"])
    app = KiraApp(config=Config(), recorder=Recorder(), transcriber=_StubTranscriber(),
                  styler=politur, injector=_StubInjector(), fachwortschatz=fach)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert ("fachgebiete" in politur.kwargs[0]) is erwartet
    assert bool(fach.aufrufe) is erwartet


def test_ohne_politur_keine_begriffsauswahl(monkeypatch):
    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: "plain")
    cfg = Config()
    cfg.styler.enabled = False
    fach = _Fach(["Kubernetes"])
    app = KiraApp(config=cfg, recorder=Recorder(), transcriber=_StubTranscriber(),
                  styler=_Politur(), injector=_StubInjector(), fachwortschatz=fach)
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert fach.aufrufe == []


def test_unsichere_sprache_faellt_auf_die_einstellung_zurueck():
    class Ergebnis:
        def __init__(self, language, language_probability):
            self.language, self.language_probability = language, language_probability

    cfg = Config()
    cfg.whisper.language = "auto"
    app = KiraApp(config=cfg, recorder=Recorder(), transcriber=_StubTranscriber(),
                  styler=_Politur(), injector=_StubInjector())
    assert app._fach_sprache(Ergebnis("fr", 0.95)) == "fr"
    assert app._fach_sprache(Ergebnis("fr", 0.5)) == "auto"
    assert app._fach_sprache(Ergebnis("de", None)) == "de"


def test_glossar_laesst_richtige_begriffe_mit_bindestrich_weg(tmp_path):
    (tmp_path / "medizin-de.txt").write_text("Klinefelter-Syndrom\nHypothyreose\n", encoding="utf-8")
    fw = Fachwortschatz.laden(["medizin"], tmp_path)
    assert fw.glossar("Der Patient hat ein Klinefelter-Syndrom.", "de", 5) == []
    assert fw.glossar("Verdacht auf Hypo Thyreose.", "de", 5) == ["Hypothyreose"]
    assert fw.glossar("Verdacht auf Hypo Thyreose.", "de", 5, unsicher=[]) == []
    assert fw.glossar("Verdacht auf Hypo Thyreose.", "de", 5, unsicher=["Thyreose"]) == ["Hypothyreose"]


def test_vorbereiten_baut_den_index(verzeichnis):
    fw = Fachwortschatz.laden(["medizin"], verzeichnis)
    fw.vorbereiten("auto")
    assert set(fw._index) == {"de", "en"}


@pytest.mark.parametrize("modus, begriffe, erwartet", [
    ("terminal", [], False), ("code", [], False), ("terminal", ["Kubernetes"], True), ("plain", [], False),
    ("plain", ["Kubernetes"], True),
])
def test_befehle_ohne_treffer_bleiben_ohne_fachkontext(monkeypatch, modus, begriffe, erwartet):
    class Politur:
        def __init__(self):
            self.kwargs = []

        async def polish(self, text, mode, **kwargs):
            self.kwargs.append(kwargs)
            return text

    class Fach(_Fach):
        kontext = ["der IT"]

    monkeypatch.setattr("kira.app.detect_mode", lambda cfg: modus)
    politur = Politur()
    app = KiraApp(config=Config(), recorder=Recorder(), transcriber=_StubTranscriber(),
                  styler=politur, injector=_StubInjector(), fachwortschatz=Fach(begriffe))
    asyncio.run(app._run_pipeline(np.ones(16000, dtype=np.float32)))
    assert ("fachgebiete" in politur.kwargs[0]) is erwartet
