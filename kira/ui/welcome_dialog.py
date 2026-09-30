from __future__ import annotations
import logging
import os
from pathlib import Path

from packaging.version import InvalidVersion, parse as parse_version
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QCheckBox, QDialog, QPushButton, QTextBrowser

from kira import __version__
from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme

log = logging.getLogger(__name__)
from kira._resources import assets_dir as _assets_dir  # noqa: E402
_ASSETS = _assets_dir()
_WELCOME_MARKER = Path(os.environ.get("APPDATA", str(Path.home()))) / "Kira" / ".welcomed"


def is_first_run() -> bool:
    if not _WELCOME_MARKER.exists():
        return True
    try:
        marker_text = _WELCOME_MARKER.read_text(encoding="utf-8").strip()
    except OSError as exc:
        log.warning("welcome marker unreadable: %s, showing dialog", exc)
        return True
    try:
        marker_version = parse_version(marker_text)
        current_version = parse_version(__version__)
    except InvalidVersion:
        log.info(
            "welcome marker holds non-version text %r, "
            "showing once, will upgrade to %s on accept",
            marker_text, __version__,
        )
        return True
    return marker_version < current_version


def mark_welcomed() -> None:
    _WELCOME_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _WELCOME_MARKER.write_text(__version__, encoding="utf-8")


_GUIDE_HTML = """
<p>Speech2Anywhere ist dein lokaler Sprache-zu-Text-Helfer. Alles läuft auf deinem PC:
keine Cloud, keine Telemetrie. Whisper transkribiert, ein Sprachmodell (Ollama)
poliert.</p>

<h3>1. Diktieren (Push-to-Talk)</h3>
<ul>
  <li>Halte <b>F8</b> in jedem beliebigen Programm.</li>
  <li>Sprich, was du tippen willst.</li>
  <li>Lass F8 los: Der polierte Text erscheint dort, wo dein Cursor steht.</li>
</ul>
<p class="small">Mindestens ~300 ms halten, sonst wird
die Aufnahme als Aus-Versehen-Tap gewertet.</p>
<p>Am Mauszeiger zeigt die Aufnahme-Anzeige Pegel und Zustand. Steht dort
<b>ZU NAH</b>, etwas Abstand zum Mikrofon halten; bei <b>KEIN SIGNAL</b> liefert
das Mikrofon Stille. Den Stil wählst du in den Einstellungen im Reiter
„Anzeige“.</p>

<h3>2. Bearbeiten (markierten Text überarbeiten)</h3>
<ul>
  <li>Markiere Text in einer beliebigen App.</li>
  <li>Halte <b>F9</b> und sage einen Befehl:
    „mach das förmlich" / „übersetz auf Englisch" /
    „fass das in 3 Bullets zusammen".</li>
  <li>Lass F9 los: Die Selektion wird durch den überarbeiteten Text ersetzt.</li>
</ul>
<p class="small">F9 nutzt Strg+C im Hintergrund.
Ist nichts markiert, passiert nichts.</p>

<h3>3. Datei transkribieren</h3>
<p>Tray-Icon (rechts unten) → Rechtsklick → <b>„Datei transkribieren..."</b>.
Audio (.wav, .mp3, .m4a, .flac, .ogg, .opus) oder Video
(.mp4, .mov, .mkv, .webm) auswählen. Speech2Anywhere speichert die Transkription
als <code>.txt</code> neben der Eingabedatei.</p>

<h3>4. Modi &amp; Custom Dictionary</h3>
<p>Speech2Anywhere erkennt automatisch in welcher App du tippst (Outlook → förmliche
Email, Slack → lockerer Chat, VS Code → Code) und poliert je nach Programm
anders. Eingebaute Modi:
<code>email</code>, <code>chat</code>, <code>code</code>,
<code>terminal</code>, <code>plain</code>, <code>clean</code>
(Filler-Filter only),
<code>translate_en</code> (Deutsch→Englisch),
<code>email_formal</code> (Sie-Form, Geschäftsstil).</p>
<p>Eigennamen, Markennamen und Fachbegriffe werden oft falsch transkribiert
(„what's app" statt „WhatsApp", „power point" statt „PowerPoint",
„java skript" statt „JavaScript"). Unter Einstellungen, Reiter „Über“,
„Rohconfig öffnen…“ setzt du eine Ersetzungsliste, die den erkannten Text
vor der Politur korrigiert:</p>
<pre>
whisper:
  replacements:
    "what's app": "WhatsApp"
    "power point": "PowerPoint"
    "java skript": "JavaScript"
</pre>
<p>Ersetzt werden nur ganze Wörter; längere Einträge gehen vor.</p>

<h3>5. Aus Korrekturen lernen</h3>
<p>Korrigierst du ein falsch erkanntes Wort, bevor du den Text abschickst,
merkt sich Speech2Anywhere das Paar. Taucht es in zwei Diktaten auf, greift es von
selbst; Einzelfälle warten unter Tray → <b>„Gelernte Wörter…“</b> auf dein
Häkchen. Was du dort verwirfst, lernt Speech2Anywhere nicht wieder. Die Nachrichten
stammen aus Chat-Verläufen, deren Ordner in der Rohconfig unter
<code>learning.sources</code> stehen. Alles bleibt lokal.</p>

<h3>6. Unzensiertes Modell (optional)</h3>
<p>Standardmäßig poliert Speech2Anywhere mit <code>gemma4:12b</code>. In den Einstellungen,
Reiter „Politur“, lädt der Knopf <b>„Laden…“</b> bei „Unzensiert“ optional
ein abliteriertes Modell (Qwen3.6 27B, rund 17 GB), dessen Inhaltsfilter
entfernt sind (nützlich, wenn die normale Politur Formulierungen abschwächt
oder zurückweist). Speech2Anywhere prüft vorher deinen Grafikspeicher.</p>

<h3>7. Updates</h3>
<p>Speech2Anywhere prüft beim Start automatisch, ob auf GitHub eine neuere Version
vorliegt, und fragt dann nach. Solange Speech2Anywhere läuft, prüft es alle sechs
Stunden erneut; eine neue Version meldet es dann einmal im Tray, und oben im
Tray-Menü steht „Update auf … installieren…“. Abschaltbar in der Rohconfig über
<code>updates.check_on_start</code>, den Takt ändert
<code>updates.check_interval_hours</code>.</p>
<p>Manuell: Tray → <b>„Updates suchen..."</b> oder Einstellungen → Reiter „Über“ →
Update-Button. Speech2Anywhere prüft GitHub Releases, lädt das Multi-Asset-Bundle
(Stub + Splits), verifiziert SHA256-Hashes (falls im Release vorhanden),
und startet den Setup-Wizard. Speech2Anywhere beendet sich dafür kurz.</p>

<h3>8. Tray &amp; Status</h3>
<p>Das Tray-Symbol zeigt immer das Logo:</p>
<ul>
  <li><b>Ruhig</b>: bereit, oder Speech2Anywhere transkribiert und poliert gerade</li>
  <li><b>Der Mund plappert</b>: Aufnahme läuft</li>
  <li><b>Rotoranger Punkt</b>: Fehler, siehe „Protokoll öffnen…“</li>
</ul>

<h3>Konfiguration</h3>
<p>Tray → <b>„Einstellungen…“</b>: Reiter Mikrofon, Politur, Tasten, Anzeige,
Lernen und Über. Seltene Felder (Ersetzungen, Modi, Initial-Prompt) über
„Rohconfig öffnen…“.</p>

<h3>Logs</h3>
<p>Tray → <b>„Protokoll öffnen…“</b>: <code>%LOCALAPPDATA%\\Kira\\speech2anywhere.log</code>.
Bei nativen Crashes: <code>speech2anywhere-faulthandler.log</code> daneben.</p>
"""


_GUIDE_WIDTH = 550


def _guide_css() -> str:
    fam = comic.load_fonts()
    return f"""
        body {{ color: {comic.INK}; }}
        h3 {{ font-family: "{fam[800]}"; font-size: 20px; font-weight: 800; margin-top: 18px; margin-bottom: 2px; }}
        p {{ margin-top: 6px; margin-bottom: 6px; line-height: 135%; }}
        li {{ margin-top: 2px; margin-bottom: 2px; }}
        code {{ font-family: "Consolas"; background-color: {comic.TINT}; }}
        pre {{ font-family: "Consolas"; font-size: 13px; background-color: {comic.TINT}; }}
        .small {{ color: {comic.LABEL}; font-size: 14px; }}
    """


class WelcomeDialog(QDialog):
    def __init__(self, as_help: bool = False) -> None:
        super().__init__()
        self._as_help = as_help

        if as_help:
            self.setWindowTitle("Speech2Anywhere: Anleitung")
            tab_text, card_title, cta_text = "Anleitung", "So funktioniert Speech2Anywhere", "Schließen"
        else:
            self.setWindowTitle("Willkommen bei Speech2Anywhere")
            tab_text, card_title, cta_text = "Willkommen", "Willkommen bei Speech2Anywhere", "Loslegen"

        icon_path = _ASSETS / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(700, 620)
        self.resize(740, 820)
        self.setModal(True)
        apply_light_theme(self)
        body = comic.dialog_frame(self, tab_text)

        card = comic.ComicCard(card_title, comic.mascot_pixmap(32))
        guide = QTextBrowser()
        guide.setFrameShape(QTextBrowser.Shape.NoFrame)
        guide.setStyleSheet("QTextBrowser { border: none; padding: 0; background: #FFFFFF; }")
        guide.setOpenLinks(False)
        text_font = QFont("Segoe UI")
        text_font.setPixelSize(16)
        guide.document().setDefaultFont(text_font)
        guide.setLineWrapMode(QTextBrowser.LineWrapMode.FixedPixelWidth)
        guide.setLineWrapColumnOrWidth(_GUIDE_WIDTH)
        guide.document().setDefaultStyleSheet(_guide_css())
        guide.setHtml(_GUIDE_HTML)
        card.add_note(guide)
        body.addWidget(card, 1)

        left = None
        if not as_help:
            self.cb_dont_show = QCheckBox(
                f"Bei diesem Update (v{__version__}) nicht erneut zeigen"
            )
            self.cb_dont_show.setChecked(True)
            left = self.cb_dont_show

        cta_btn = QPushButton(cta_text)
        cta_btn.setObjectName("comicPrimary")
        cta_btn.clicked.connect(self.accept)
        cta_btn.setDefault(True)
        body.addLayout(comic.footer_row(left, cta_btn))

    def accept(self) -> None:
        if not self._as_help and getattr(self, "cb_dont_show", None) is not None:
            if self.cb_dont_show.isChecked():
                mark_welcomed()
        super().accept()
