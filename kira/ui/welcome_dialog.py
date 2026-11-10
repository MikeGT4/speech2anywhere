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
from kira.texte import language, tr

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


def welcomed_before() -> bool:
    return _WELCOME_MARKER.exists()


_NEWS_HTML = """
<h3>Neu in v{version}</h3>
<ul>
  <li>Die Schrift ist in allen Fenstern glatt, ohne Farbsaum.</li>
  <li>Das gilt für Hinweise, Untertitel, Eingabefelder, die Anleitung und die Menüs.</li>
  <li>Knöpfe, Reiter, Titel und die Taste im gelben Hinweis zeichnen schärfer.</li>
  <li>Seit 0.6.1 dabei: Rechnen auf dem Prozessor, Messung in der Ersteinrichtung, Hugging Face, Statuspunkt im Tray-Menü.</li>
</ul>
"""


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
<p>Lieber drücken statt halten? In den Einstellungen im Reiter „Tasten“ gibt es
<b>Umschalten</b>: einmal drücken startet, noch einmal drücken beendet.</p>
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
als <code>.txt</code> neben der Eingabedatei, dazu eine <code>.srt</code> mit Zeitmarken
für Untertitel.</p>

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
<code>learning.sources</code> stehen. Alles bleibt lokal. Gelernt wird aus deutschen Diktaten.</p>

<h3>6. Unzensiertes Modell (optional)</h3>
<p>Mit Grafikkarte poliert Speech2Anywhere mit <code>gemma4:12b</code>, auf kleineren Karten und auf dem
Prozessor mit <code>gemma4:e4b</code>. Mit Grafikkarte lädt in den Einstellungen,
Reiter „Politur“, der Knopf <b>„Laden…“</b> bei „Unzensiert“ optional
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
Update-Button. Hat sich seit deiner Version nur das Programm geändert, lädt
Speech2Anywhere nur das Programmpaket (knapp 3 MB), prüft dessen Prüfsumme, spielt es
nach einem kurzen Beenden ein und startet von selbst neu. Sonst lädt es das ganze
Paket (Stub + Splits), verifiziert die SHA256-Hashes und startet den Setup-Wizard.</p>
<p>Jedes Release ist mit einer bestimmten Ollama-Version und bestimmten Fassungen der
Politur-Modelle gemessen. Ist dein Ollama älter als das geprüfte oder nutzt du eines der
gemessenen Modelle in einer anderen Fassung, meldet Speech2Anywhere das einmal im Tray; unter
<b>„Ollama-Empfehlung ansehen…“</b> aktualisierst du das Windows-Ollama und das Modell per Knopf.</p>

<h3>8. Tray &amp; Status</h3>
<p>Das Tray-Symbol zeigt immer das Logo:</p>
<ul>
  <li><b>Ruhig</b>: bereit, oder Speech2Anywhere transkribiert und poliert gerade</li>
  <li><b>Der Mund plappert</b>: Aufnahme läuft</li>
  <li><b>Rotoranger Punkt</b>: Fehler, siehe „Protokoll öffnen…“</li>
</ul>

<h3>9. Prozessor oder Grafikkarte</h3>
<p>Im Reiter „Mikrofon“ legt <b>Rechnen auf</b> fest, ob Erkennung und Politur auf dem Prozessor oder auf der NVIDIA-Grafikkarte laufen.<br>
Die Hilfeseite daneben zeigt Downloads und gemessene Zeiten.<br>
Bei der Ersteinrichtung misst Speech2Anywhere deinen Rechner und schlägt eins von beidem vor.<br>
Umstellen kannst du jederzeit.</p>
<p>Weitere Modelle für die Politur: Reiter „Politur“, Knopf <b>„Hugging Face…“</b>.<br>
Den Namen so eintragen: <code>hf.co/Nutzer/Modell:Q4_K_M</code>, Speichern lädt das Modell.<br>
Geprüft sind nur die gemma4-Modelle.</p>

<h3>Konfiguration</h3>
<p>Tray → <b>„Einstellungen…“</b>: Reiter Mikrofon, Politur, Tasten, Anzeige,
Sound, Lernen und Über. Seltene Felder (Ersetzungen, Modi, Initial-Prompt) über
„Rohconfig öffnen…“.</p>

<h3>Logs</h3>
<p>Tray → <b>„Protokoll öffnen…“</b>: <code>%LOCALAPPDATA%\\Kira\\speech2anywhere.log</code>.
Bei nativen Crashes: <code>speech2anywhere-faulthandler.log</code> daneben.</p>
"""


_NEWS_HTML_EN = """
<h3>New in v{version}</h3>
<ul>
  <li>Text is smooth in every window, without colour fringes.</li>
  <li>That covers hints, subtitles, input fields, the guide and the menus.</li>
  <li>Buttons, tabs, titles and the key in the yellow hint draw sharper.</li>
  <li>Since 0.6.1: running on the processor, measuring in first-run setup, Hugging Face, status dot in the tray menu.</li>
</ul>
"""


_GUIDE_HTML_EN = """
<p>Speech2Anywhere is your local speech-to-text helper. Everything runs on your PC:
no cloud, no telemetry. Whisper transcribes, a language model (Ollama)
cleans up.</p>

<h3>1. Dictating (push to talk)</h3>
<ul>
  <li>Hold <b>F8</b> in any program.</li>
  <li>Say what you want to type.</li>
  <li>Let go of F8: the cleaned-up text appears right where your cursor is.</li>
</ul>
<p class="small">Hold for at least ~300 ms, otherwise the
recording counts as an accidental tap.</p>
<p>Rather press than hold? On the “Keys” tab of the settings there is
<b>Toggle</b>: press once to start, press once more to stop.</p>
<p>At the pointer, the recording indicator shows level and state. If it says
<b>TOO CLOSE</b>, keep a little distance from the microphone; with <b>NO SIGNAL</b> the
microphone delivers silence. You choose the style on the “Indicator” tab of the
settings.</p>

<h3>2. Editing (reworking selected text)</h3>
<ul>
  <li>Select text in any app.</li>
  <li>Hold <b>F9</b> and say a command:
    “make this formal” / “translate into German” /
    “sum this up in 3 bullets”.</li>
  <li>Let go of F9: the selection is replaced by the reworked text.</li>
</ul>
<p class="small">F9 uses Ctrl+C in the background.
If nothing is selected, nothing happens.</p>

<h3>3. Transcribing a file</h3>
<p>Tray icon (bottom right) → right-click → <b>“Transcribe File…”</b>.
Choose audio (.wav, .mp3, .m4a, .flac, .ogg, .opus) or video
(.mp4, .mov, .mkv, .webm). Speech2Anywhere saves the transcript
as <code>.txt</code> next to the input file, plus an <code>.srt</code> with timestamps
for subtitles.</p>

<h3>4. Modes &amp; custom dictionary</h3>
<p>Speech2Anywhere detects which app you are typing in (Outlook → formal
email, Slack → casual chat, VS Code → code) and cleans up differently for each
program. Built-in modes:
<code>email</code>, <code>chat</code>, <code>code</code>,
<code>terminal</code>, <code>plain</code>, <code>clean</code>
(filler filter only),
<code>translate_en</code> (German→English),
<code>email_formal</code> (formal business style).</p>
<p>Proper names, brand names and technical terms are often transcribed wrongly
(“what's app” instead of “WhatsApp”, “power point” instead of “PowerPoint”,
“java skript” instead of “JavaScript”). Under Settings, “About” tab,
“Open raw config…” you set a replacement list that corrects the recognized text
before clean-up:</p>
<pre>
whisper:
  replacements:
    "what's app": "WhatsApp"
    "power point": "PowerPoint"
    "java skript": "JavaScript"
</pre>
<p>Only whole words are replaced; longer entries go first.</p>

<h3>5. Learning from corrections</h3>
<p>If you correct a misrecognized word before you send the text,
Speech2Anywhere remembers the pair. If it shows up in two dictations, it applies by
itself; single cases wait under Tray → <b>“Learned Words…”</b> for your
approval. What you discard there, Speech2Anywhere doesn’t learn again. The messages
come from chat histories whose folders are listed in the raw config under
<code>learning.sources</code>. Everything stays local. Learning works for German dictations.</p>

<h3>6. Uncensored model (optional)</h3>
<p>With a graphics card Speech2Anywhere cleans up with <code>gemma4:12b</code>, on smaller cards and on the
processor with <code>gemma4:e4b</code>. With a graphics card, the <b>“Download…”</b> button next to “Uncensored”
on the “Clean-up” tab of the settings optionally loads
an abliterated model (Qwen3.6 27B, about 17 GB) whose content filters
are removed (useful when the normal clean-up tones wording down
or refuses it). Speech2Anywhere checks your video memory first.</p>

<h3>7. Updates</h3>
<p>At start, Speech2Anywhere automatically checks whether a newer version
is on GitHub, and then asks. While Speech2Anywhere is running, it checks again every six
hours; it then reports a new version once in the tray, and the top of the
tray menu shows “Install update to …”. You can switch this off in the raw config via
<code>updates.check_on_start</code>; the interval is set by
<code>updates.check_interval_hours</code>.</p>
<p>Manually: Tray → <b>“Check for updates…”</b> or Settings → “About” tab →
update button. If only the program has changed since your version,
Speech2Anywhere downloads just the program package (just under 3 MB), verifies its checksum, installs it
after closing briefly and restarts by itself. Otherwise it downloads the whole
package (stub + splits), verifies the SHA256 hashes and starts the setup wizard.</p>
<p>Every release is measured with a specific Ollama version and specific versions of the
clean-up models. If your Ollama is older than the tested one, or you use one of the
measured models in a different version, Speech2Anywhere reports that once in the tray; under
<b>“View Ollama recommendation…”</b> you update the Windows Ollama and the model with one button.</p>

<h3>8. Tray &amp; status</h3>
<p>The tray icon always shows the logo:</p>
<ul>
  <li><b>At rest</b>: ready, or Speech2Anywhere is transcribing and cleaning up</li>
  <li><b>The mouth chatters</b>: recording</li>
  <li><b>Orange-red dot</b>: error, see “Open Log…”</li>
</ul>

<h3>9. Processor or graphics card</h3>
<p>On the “Microphone” tab, <b>Run on</b> decides whether recognition and clean-up run on the processor or on the NVIDIA graphics card.<br>
The help page next to it shows downloads and measured times.<br>
During the first-run setup Speech2Anywhere measures your PC and suggests one of the two.<br>
You can switch at any time.</p>
<p>More models for the clean-up: “Clean-up” tab, <b>“Hugging Face…”</b> button.<br>
Enter the name like this: <code>hf.co/user/model:Q4_K_M</code>, saving downloads the model.<br>
Only the gemma4 models are tested.</p>

<h3>Configuration</h3>
<p>Tray → <b>“Settings…”</b>: tabs Microphone, Clean-up, Keys, Indicator,
Sound, Learning and About. Rare fields (replacements, modes, initial prompt) via
“Open raw config…”.</p>

<h3>Logs</h3>
<p>Tray → <b>“Open Log…”</b>: <code>%LOCALAPPDATA%\\Kira\\speech2anywhere.log</code>.
For native crashes: <code>speech2anywhere-faulthandler.log</code> next to it.</p>
"""


def _news_html() -> str:
    return _NEWS_HTML_EN if language() == "en" else _NEWS_HTML


def _guide_html() -> str:
    return _GUIDE_HTML_EN if language() == "en" else _GUIDE_HTML


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
            self.setWindowTitle(tr("Speech2Anywhere: Anleitung"))
            tab_text, card_title, cta_text = tr("Anleitung"), tr("So funktioniert Speech2Anywhere"), tr("Schließen")
        else:
            self.setWindowTitle(tr("Willkommen bei Speech2Anywhere"))
            tab_text, card_title, cta_text = tr("Willkommen"), tr("Willkommen bei Speech2Anywhere"), tr("Loslegen")

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
        guide.document().setDefaultFont(comic.smooth_font(text_font))
        guide.setLineWrapMode(QTextBrowser.LineWrapMode.FixedPixelWidth)
        guide.setLineWrapColumnOrWidth(_GUIDE_WIDTH)
        guide.document().setDefaultStyleSheet(_guide_css())
        with_news = not as_help and welcomed_before()
        guide.setHtml(_news_html().format(version=__version__) + _guide_html() if with_news else _guide_html())
        card.add_note(guide)
        body.addWidget(card, 1)

        left = None
        if not as_help:
            self.cb_dont_show = QCheckBox(
                tr("Bei diesem Update (v{}) nicht erneut zeigen").format(__version__) if with_news else tr("Nicht erneut zeigen")
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
