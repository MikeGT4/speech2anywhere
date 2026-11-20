<p align="center"><img src="assets/readme-splash.jpg" alt="Speech2Anywhere" width="720"></p>

# Speech2Anywhere

**Hold a key, speak, release. Local AI turns it into polished text at the cursor.**

Speech2Anywhere: Your voice into any Windows application. E-Mail, Chat, Word, Browser, Terminal, Code Editor. Just hold a key and talk. Release. Your local language model will turn your speech into clean text, directly at the cursor. Activate specialist vocabulary in 7 areas (medicine, IT...). So you get correct technical terms much more often. Without cloud. No account. No subscription.

[![Latest release](https://img.shields.io/github/v/release/MikeGT4/speech2anywhere?label=release)](https://github.com/MikeGT4/speech2anywhere/releases/latest)
![Windows 11, NVIDIA GPU or CPU](https://img.shields.io/badge/Windows%2011-NVIDIA%20GPU%20or%20CPU-0078d4)
![macOS Apple Silicon](https://img.shields.io/badge/macOS-Apple%20Silicon-black)
![100 percent local](https://img.shields.io/badge/100%25-local-2ea44f)
![Personal use license](https://img.shields.io/badge/license-personal%20use-lightgrey)

<p align="center"><a href="https://speech2anywhere.de/en/"><img src="assets/readme-demo.gif" alt="Demo: an email is dictated and lands polished at the cursor, a voice command makes it friendlier, then a prompt is dictated to a coding agent" width="880"></a></p>

Website with all features: [speech2anywhere.de](https://speech2anywhere.de/en/), also in [German](https://speech2anywhere.de/).

## What it does

+ Use in any application: it'll give you the text if there's a text cursor. No app specific plugin. No copy and paste. Your clipboard content (images, files, formatted text) is restored.
+ Not just transcription. A local model with Ollama refines the text from Whisper. Punctuation, cut out fillers. It also corrects slip-ups (e.g. "on Tuesday, no, on Friday" -> "on Friday") and adapts to the style of the app. E.g. mail looks like a mail, terminal prompt stays literal.
+ Specialist vocabulary. You can activate fields in a separate settings tab: medicine, medications, law, business, science and engineering, chemistry, IT. So the cleanup is aware of the field and will find up to 5 similar sounding terms per dictation. If Whisper hears "lefotyruxin", it will become "Levothyroxin". Tested on 60 made-up specialist dictations in German and English: 1 of 133 terms wrong with field activated. 8 without. No change for everyday dictation.
+ Voice edit. Select text. Then hold F9 and say what should change. E.g. "make it more friendly".
+ All on your PC. Audio and text will never leave your machine. Speech2Anywhere will only go online for updates and model downloads.

+ 8 dictation languages (German, English, French, Italian, Dutch, Polish, Portuguese, Spanish) or auto detect. Cleanup will respond in the language you spoke. Interface in German, English.
+ Uses an NVIDIA graphics card. Or (if no graphics card) the processor. The first-run wizard will test your PC and give a recommendation.
+ Press and hold the key. Or press once to start. Once again to stop.
+ Makes a text file and .srt subtitles from audio/video files.
+ Learns from your pre-send corrections. (German dictations)
+ Use any Ollama model for the cleanup. Also GGUF models from Hugging Face.
+ Live indicator at the cursor. You can choose from eighteen styles. Sounds optional.

## Two builds, one idea

| | Windows 11 (this repository) | macOS (Mac App Store, separate code base) |
|---|---|---|
| Hotkey | hold **F8** or tap it in toggle mode, **F9** for AI edit commands | hold **fn** (Globe key) |
| Speech to text | faster-whisper, `large-v3` on CUDA or `small` on the processor | Whisper `large-v3-turbo`, runs on the Mac |
| Text cleanup | Ollama, `gemma4:12b`, or `gemma4:e4b` with little video memory and on the processor, uncensored model optional | Qwen3 8B, runs on the Mac, no Ollama needed |
| Hardware | NVIDIA GPU with about 10 GB of free video memory (14 GB for `gemma4:12b`), or the processor | Apple silicon, macOS 15 or later, about 6.3 GB of free disk space for the two models |
| Install | installer on the [Releases page](https://github.com/MikeGT4/speech2anywhere/releases/latest) | coming soon to the Mac App Store, see the [website](https://speech2anywhere.de/en/) |

## Requirements

- Windows 11 (Windows 10 should work, untested)
- An NVIDIA GPU with about 10 GB of free video memory (about 14 GB for `gemma4:12b`), or no graphics card: then Speech2Anywhere runs on the processor. That is slower and works best with 12 GB of RAM or more
- 25 GB of free disk space: the installer is about 3.5 GB, the first-run wizard pulls 10 to 13 GB of models into `%USERPROFILE%\models\` and `%USERPROFILE%\.ollama\`
- A stable internet connection for the first start (one-time model download)

## Install (end users)

Download everything from the [latest release](https://github.com/MikeGT4/speech2anywhere/releases/latest) into the same folder: `Kira-Setup-vX.Y.Z.exe`, the `.bin` parts (`-1.bin`, `-2.bin`) and `SHA256SUMS.txt`. The setup is split into parts, so the `.bin` files must sit next to the `.exe`. The file `kira-X.Y.Z-py3-none-any.whl` is the program package for in-app updates; a fresh install does not need it.

1. Double-click `Kira-Setup-vX.Y.Z.exe`.
2. If Windows Defender SmartScreen warns: "More info", then "Run anyway". Speech2Anywhere is not code-signed. Verify the download with `certutil -hashfile Kira-Setup-vX.Y.Z.exe SHA256` against `SHA256SUMS.txt` if you want to be sure.
3. Click through the setup wizard.
4. On first start a second wizard measures your PC, recommends graphics card or processor and downloads the matching models (10 to 13 GB from Hugging Face and the Ollama registry). One time only; dictation works offline afterwards.
5. Speech2Anywhere starts in the tray with a yellow framed logo. **Hold F8, speak, release.**

Later updates run from the tray menu. When a new version is out, the tray icon shows a green mark with an arrow; its tooltip gives the version. If only the program changed since your version, Speech2Anywhere loads just the program package (about 6 MB), checks its SHA-256 and restarts itself; otherwise it loads the full setup.

### Installation (Deutsch)

Alle Dateien der [neuesten Release](https://github.com/MikeGT4/speech2anywhere/releases/latest) in denselben Ordner laden: `Kira-Setup-vX.Y.Z.exe`, die `.bin`-Teile und `SHA256SUMS.txt`. Die `.bin`-Teile müssen neben der `.exe` liegen; die Datei `kira-X.Y.Z-py3-none-any.whl` ist das Programmpaket für Updates aus der App und für eine neue Installation nicht nötig. Doppelklick auf die `.exe`, bei der SmartScreen-Warnung „Weitere Informationen" und „Trotzdem ausführen" (Speech2Anywhere ist nicht signiert). Beim ersten Start misst ein zweiter Assistent deinen Rechner, empfiehlt Grafikkarte oder Prozessor und lädt die Modelle dazu, danach funktioniert das Diktieren ohne Internet. Speech2Anywhere erscheint in der Taskleiste: **F8 halten, sprechen, loslassen.**

## Developers

Install from source, configuration, learning from corrections and troubleshooting: [DEVELOPERS.md](DEVELOPERS.md).

## License

Personal use. See [`LICENSE`](LICENSE) (English and German). Commercial use needs written consent.

The word lists `assets/wordlist-*.txt` are derived from [wordfreq](https://github.com/rspeer/wordfreq) data, licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

Made by [Digitalroots](https://www.digitalroots.de/en/leistungen/assistenten/speech2anywhere/), Mike Pollow.
