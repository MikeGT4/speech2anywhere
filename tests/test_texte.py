# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import ast
import io
import re
import tokenize
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ERSATZ = re.compile(r"\b[^\W_]*(laeuf|spaeter|naechst|oeffn|laedt|fuer\b|ueber|zusaetz|verknuepf|startmenue|ausfuehr|anhaeng|temporaer|pruef|duerf|haelt|liess)[^\W_]*", re.I)
UMLAUT_ERSATZ = re.compile(r"\b\w*(?:ae|oe|ue)\w*|\bgross\b", re.I)


def _dreifach(quelltext: str) -> bool:
    return quelltext.lstrip("rbuRBUfF").startswith(('"""', "\'\'\'"))


def _strings(pfad: Path) -> list[str]:
    quelle = pfad.read_text(encoding="utf-8")
    texte = []
    for token in tokenize.generate_tokens(io.StringIO(quelle).readline):
        if token.type == tokenize.STRING and not _dreifach(token.string):
            texte.append(token.string)
    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, ast.JoinedStr) and not _dreifach(ast.get_source_segment(quelle, knoten) or ""):
            texte.append("".join(teil.value for teil in knoten.values if isinstance(teil, ast.Constant)))
    return texte


def test_update_messages_and_wizard_use_real_umlauts():
    for datei in ("kira/ui/_update_runner.py", "kira/setup_wizard.py"):
        treffer = [t for t in _strings(WURZEL / datei) if ERSATZ.search(t)]
        assert treffer == [], (datei, treffer)


def test_installer_texts_use_real_umlauts():
    zeilen = [z for z in (WURZEL / "installer/kira.iss").read_text(encoding="utf-8-sig").splitlines()
              if z.strip() and not z.lstrip().startswith((";", "//"))]
    treffer = [z for z in zeilen if ERSATZ.search(z)]
    assert treffer == []
    roh = (WURZEL / "installer/kira.iss").read_bytes()
    assert not roh.startswith(b"\xef\xbb\xbf")
    assert b"#if Ver < EncodeVer(6, 3, 0)" in roh


def test_ready_log_line_without_long_dash():
    assert not [t for t in _strings(WURZEL / "kira/main.py") if "\u2014" in t]


def test_visible_texts_in_package_use_real_umlauts():
    treffer = [
        (datei.relative_to(WURZEL).as_posix(), text)
        for datei in sorted((WURZEL / "kira").rglob("*.py"))
        for text in _strings(datei)
        if ERSATZ.search(text)
    ]
    assert treffer == []


def test_notice_titles_say_politur():
    titel = [t for t in _strings(WURZEL / "kira/main.py") if t.strip("\"'").startswith("Speech2Anywhere: ")]
    assert titel
    assert [t for t in titel if "Polish" in t] == []


def test_prompts_use_real_umlauts():
    treffer = {}
    for pfad in sorted((WURZEL / "prompts").glob("*.md")):
        woerter = [w for w in UMLAUT_ERSATZ.findall(pfad.read_text(encoding="utf-8")) if w != "fluent"]
        if woerter:
            treffer[pfad.name] = woerter
    assert treffer == {}


def test_german_license_text_uses_real_umlauts():
    lizenz = (WURZEL / "LICENSE").read_text(encoding="utf-8")
    deutsch = lizenz[lizenz.index("Deutsche Fassung"):]
    assert UMLAUT_ERSATZ.findall(deutsch) == []
    assert "ausschliesslich" not in deutsch
