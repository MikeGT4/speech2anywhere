# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations
import io
import re
import tokenize
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ERSATZ = re.compile(r"\b\w*(laeuf|spaeter|naechst|oeffn|laedt|fuer\b|ueber|zusaetz|verknuepf|startmenue|ausfuehr|anhaeng)\w*", re.I)


def _strings(pfad: Path) -> list[str]:
    quelle = pfad.read_text(encoding="utf-8")
    texte = []
    for token in tokenize.generate_tokens(io.StringIO(quelle).readline):
        if token.type == tokenize.STRING and not token.string.lstrip("rbuRBUfF").startswith(('"""', "\'\'\'")):
            texte.append(token.string)
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
