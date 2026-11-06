# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QDialog, QPushButton, QTextBrowser

from kira._resources import assets_dir
from kira.texte import language, tr
from kira.ui import _comic as comic
from kira.ui._dialog_style import apply_light_theme
from kira.ui.welcome_dialog import _GUIDE_WIDTH, _guide_css

_HELP_HTML = """
<h3>Was der Schalter umstellt</h3>
<p>Speech2Anywhere arbeitet in zwei Schritten.<br>
Whisper erkennt, was du sagst.<br>
Ein Sprachmodell poliert danach den Text.<br>
<b>Rechnen auf</b> legt fest, ob beides auf dem Prozessor oder auf der Grafikkarte läuft.</p>

<h3>Prozessor (CPU)</h3>
<ul>
  <li>Läuft auf jedem Windows-PC, auch ohne NVIDIA-Grafikkarte.</li>
  <li>Erkennung mit Whisper small, Download rund 0,5 GB.</li>
  <li>Politur mit gemma4:e4b, Download rund 10 GB, belegt rund 5,4 GB Arbeitsspeicher.</li>
  <li>Gemessen auf einem Desktop-Prozessor mit 8 Kernen: rund 1 s für die Erkennung eines kurzen Diktats,
  dazu 2 bis 3 s für die Politur.</li>
  <li>Ein Laptop braucht länger.</li>
  <li>Ohne Politur bleibt rund 1 s. Den Schalter dafür findest du im Reiter <b>Politur</b>.</li>
  <li>Wortfetzen in der Anzeige gibt es nur mit Grafikkarte.</li>
</ul>

<h3>Grafikkarte (GPU)</h3>
<ul>
  <li>Braucht eine NVIDIA-Grafikkarte mit rund 10 GB freiem Grafikspeicher, für gemma4:12b rund 14 GB.</li>
  <li>Erkennung mit Whisper large-v3, Download rund 3 GB.</li>
  <li>Politur mit dem Modell aus dem Reiter <b>Politur</b>, etwa gemma4:12b mit rund 8 GB Download.</li>
  <li>Gemessen auf einer aktuellen NVIDIA-Karte: rund 0,4 s für die Erkennung, dazu 0,15 s für die Politur.</li>
</ul>

<h3>Genauigkeit</h3>
<p>Gemessen mit 39 vorgelesenen deutschen Sätzen, zusammen 273 Wörter.<br>
Whisper small machte 8 Fehler, Whisper large-v3 4 bis 5.</p>

<h3>Umschalten</h3>
<p>Wähle im Reiter <b>Mikrofon</b> unter <b>Rechnen auf</b> und klick auf <b>Speichern</b>.<br>
Fehlt ein Modell, lädt Speech2Anywhere es vorher.<br>
Danach fragt es nach einem kurzen Neustart.<br>
Ohne NVIDIA-Grafikkarte bleibt es beim Prozessor.</p>
"""

_HELP_HTML_EN = """
<h3>What the switch changes</h3>
<p>Speech2Anywhere works in two steps.<br>
Whisper recognises what you say.<br>
A language model then cleans up the text.<br>
<b>Run on</b> decides whether both run on the processor or on the graphics card.</p>

<h3>Processor (CPU)</h3>
<ul>
  <li>Runs on any Windows PC, even without an NVIDIA graphics card.</li>
  <li>Recognition with Whisper small, a download of about 0.5 GB.</li>
  <li>Clean-up with gemma4:e4b, a download of about 10 GB, using about 5.4 GB of memory.</li>
  <li>Measured on a desktop processor with 8 cores: about 1 s to recognise a short dictation,
  plus 2 to 3 s for the clean-up.</li>
  <li>A laptop takes longer.</li>
  <li>Without clean-up it stays at about 1 s. The switch for that is on the <b>Clean-up</b> tab.</li>
  <li>Live words in the indicator need the graphics card.</li>
</ul>

<h3>Graphics card (GPU)</h3>
<ul>
  <li>Needs an NVIDIA graphics card with about 10 GB of free video memory, about 14 GB for gemma4:12b.</li>
  <li>Recognition with Whisper large-v3, a download of about 3 GB.</li>
  <li>Clean-up with the model from the <b>Clean-up</b> tab, such as gemma4:12b with a download of about 8 GB.</li>
  <li>Measured on a current NVIDIA card: about 0.4 s for recognition, plus 0.15 s for the clean-up.</li>
</ul>

<h3>Accuracy</h3>
<p>Measured with 39 German sentences read aloud, 273 words in total.<br>
Whisper small made 8 errors, Whisper large-v3 made 4 to 5.</p>

<h3>Switching</h3>
<p>On the <b>Microphone</b> tab, pick an option under <b>Run on</b> and click <b>Save</b>.<br>
If a model is missing, Speech2Anywhere downloads it first.<br>
Then it asks for a quick restart.<br>
Without an NVIDIA graphics card it stays on the processor.</p>
"""


def help_html() -> str:
    return _HELP_HTML_EN if language() == "en" else _HELP_HTML


class ComputeHelpDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Speech2Anywhere: Prozessor oder Grafikkarte"))
        icon_path = assets_dir() / "icon-branded.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(700, 560)
        self.resize(740, 780)
        self.setModal(True)
        apply_light_theme(self)
        body = comic.dialog_frame(self, tr("Hilfe"))
        card = comic.ComicCard(tr("Prozessor oder Grafikkarte?"), comic.mascot_pixmap(32))
        text = QTextBrowser()
        text.setFrameShape(QTextBrowser.Shape.NoFrame)
        text.setStyleSheet("QTextBrowser { border: none; padding: 0; background: #FFFFFF; }")
        text.setOpenLinks(False)
        font = QFont("Segoe UI")
        font.setPixelSize(16)
        text.document().setDefaultFont(font)
        text.setLineWrapMode(QTextBrowser.LineWrapMode.FixedPixelWidth)
        text.setLineWrapColumnOrWidth(_GUIDE_WIDTH)
        text.document().setDefaultStyleSheet(_guide_css())
        text.setHtml(help_html())
        card.add_note(text)
        body.addWidget(card, 1)
        close = QPushButton(tr("Schließen"))
        close.setObjectName("comicPrimary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        body.addLayout(comic.footer_row(None, close))
