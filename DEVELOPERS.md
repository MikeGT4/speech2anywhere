# Speech2Anywhere for developers

This guide covers the setup from source, the configuration and troubleshooting, and the [README](README.md) has the overview.

## Details

- **Push to talk:** you hold F8 while you speak and release it when you are done. A 250 ms pre-roll buffer catches the first word even if you start speaking before the keyboard hook fires. If you prefer tapping, toggle mode in the settings starts with one press and stops with the next, and a forgotten recording ends after three minutes.
- **Graphics card or processor:** the first-run wizard measures graphics card, video memory, cores and RAM and recommends one of the two, and you can switch any time under Settings, Microphone, "Run on". On the processor Speech2Anywhere uses Whisper `small` and `gemma4:e4b`. Measured on a desktop processor with 8 cores: about 0.8 s to recognize a short sentence and about 2.3 s for the cleanup, against 0.4 s and 0.15 s on the graphics card. Not tested on a PC without an NVIDIA driver.
- **Cleanup model from a list:** the cleanup tab lists the models installed in Ollama with their size, the tested gemma4 models first. Typing a name still works, and saving pulls a model that is not installed yet. In fast mode and on the processor the field is greyed out, and a line below says which model cleans up.
- **More models from Hugging Face:** the **Hugging Face…** button on the cleanup tab opens the GGUF model search. When you enter a name like `hf.co/user/model:Q4_K_M`, saving pulls it through Ollama. Only the gemma4 models are tested.
- **Context-aware cleanup:** Speech2Anywhere detects the active app (Mail, Slack, Terminal, VS Code, Cursor, Obsidian and more) and rewrites in the right register. The model stays warm for 24 hours, so the first F8 after boot has the same latency as the hundredth.
- **Uncensored option:** the settings dialog offers an abliterated Qwen model as cleanup model. It is not tuned to refuse or lecture; it only cleans up what you said.
- **Audio and text stay on your PC.** Speech2Anywhere talks to Ollama on `127.0.0.1`. It goes online only for the update check against the GitHub Releases API (at start, every six hours by default, on request; the automatic checks can be switched off), for updates (searching for one also fetches the program package of about 6 MB; the full setup and the tested Ollama setup from the Ollama releases on GitHub only load after you confirm), and for loading models from Hugging Face and the Ollama registry. The bundled Ollama app checks for its own updates.
- **A missing microphone is no problem:** if the configured input device is not connected at start, Speech2Anywhere comes up anyway; pressing F8 turns the tray icon yellow for 3 seconds instead of crashing.
- **Crash diagnostics:** `faulthandler`, threading exception hook, Qt message handler and a 60 second heartbeat all flow into `speech2anywhere.log`.

## Install (developers)

Requirements: Python 3.12 on Windows (`py -3.12 --version`), for the graphics card mode an NVIDIA driver with CUDA (`nvidia-smi` works), `uv` (`py -3.12 -m pip install uv`), [Ollama for Windows](https://ollama.com/download) (`winget install Ollama.Ollama`) and Git.

```powershell
git clone https://github.com/MikeGT4/speech2anywhere.git C:\Users\<user>\dev\kira
cd C:\Users\<user>\dev\kira
.\scripts\install_win.ps1
ollama pull gemma4:12b
.\scripts\install_autostart.ps1
```

`install_win.ps1` creates `%USERPROFILE%\kira-venv`, installs faster-whisper, pystray and PyQt6 and embeds the branded icon into `kira.exe`. It does not write a config file, so you copy `installer\config.yaml.template` to `%APPDATA%\Kira\config.yaml` yourself; otherwise Speech2Anywhere falls back to the small built-in default model instead of `gemma4:12b`. The scripts default `-Source` to the repo containing them, and `-Source <path>` installs from a different checkout. To start it by hand, you run `C:\Users\<user>\kira-venv\Scripts\kira.exe`.

`pip install` regenerates the entry-point wrappers without resource info, so the EXE icon falls back to the generic Python icon after every reinstall. The script `scripts\embed_icon.ps1` puts it back, started with `powershell -ExecutionPolicy Bypass -File scripts\embed_icon.ps1`. If you change the logo (`assets/brand/speech2anywhere-logo-1024.png`), regenerate the icons first with `py -3.12 scripts\regenerate_branded_icon.py`.

## Configuration

The configuration lives in `%APPDATA%\Kira\config.yaml`. In the tray, "Settings" ("Einstellungen" in the German interface) opens a form for the common settings: microphone gain and device, dictation and interface language, cleanup model, hotkey and toggle mode. If a change needs a restart, the dialog offers one right after saving.

`audio.input_device` is a substring match: `'USB Microphone'` matches `Mikrofon (2- USB Microphone)`. If the configured device is not enumerated, Speech2Anywhere logs a `WARNING kira.recorder` line listing every input device it did see.

**Pin your physical microphone even if Windows shows it as the default.** On machines with an ASUS Intelligo or "AI Noise-Canceling Microphone" filter, the Windows default can flip to that virtual device for a moment, for example while a USB microphone is still enumerating after a cold boot, and the filter kills speech as noise. Symptom in `speech2anywhere.log`: `Recorder.stop: ... peak=0.0002 rms=0.0001`, then Whisper hallucinating "Vielen Dank.", then no text. A pinned device bypasses the filter. If the USB device is not ready when you press the hotkey, you get a 3 second yellow tray icon instead of a silent dictation.

### Fast mode

Settings, cleanup model: the checkbox **fast mode** switches to `gemma4:e4b`. It helps when the 12B model keeps sliding into CPU offload (`ollama ps` shows a `49/51 CPU/GPU` split). The small model is pulled once when you enable it. Standard cleanup (punctuation, fillers) stays practically identical, F9 edit commands get noticeably weaker, and slips of the tongue are resolved less reliably. The first-run wizard switches it on when the free video memory is too small for the 12B model.

### Learning from corrections

Since v0.4.0 Speech2Anywhere keeps a local dictation history (`%LOCALAPPDATA%\Kira\history`, deleted after three months) and compares it every 30 minutes with the messages you actually sent. If you fixed a misrecognized word before sending, Speech2Anywhere records the pair. A pair seen in two dictations applies on its own; single cases wait under tray, **Learned Words** (**Gelernte Wörter**), until you accept them. Rejected pairs are never learned again. Only German dictations are learned from.

The messages come from JSONL chat histories in the folders listed under `learning.sources` (one message per line, sent messages marked `"type": "user"`). Without sources Speech2Anywhere only writes the history; `learning.enabled: false` turns both off. Everything stays on your machine.

Learned pairs go three ways: unusual words join Whisper's vocabulary prompt, misrecognitions that are not real words become fixed replacements (whole words only), and misrecognitions that are real words only reach the cleanup model as a hint, because only the sentence tells which one was meant.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Tray icon never appears | Check `%LOCALAPPDATA%\Kira\speech2anywhere.log` for boot errors; native crashes land in `%LOCALAPPDATA%\Kira\speech2anywhere-faulthandler.log`. |
| F8 does nothing visible | Watch `speech2anywhere.log`: every press logs either `Recorder.stop` (success) or `WARNING kira.app: Hotkey press but input device unavailable` (microphone missing). The tray icon turns yellow for 3 seconds in the second case. If your tray icons are auto-hidden, pin Speech2Anywhere's icon. |
| `faster-whisper` cuDNN error | `py -3.12 -m uv pip install --python C:\Users\<user>\kira-venv\Scripts\python.exe --force-reinstall nvidia-cudnn-cu12` |
| "Ollama unreachable" toast | `curl http://127.0.0.1:11434/api/tags` from PowerShell. If it fails, restart `ollama app.exe` from `%LOCALAPPDATA%\Programs\Ollama\` or reinstall via `winget install Ollama.Ollama`. Use `127.0.0.1`, not `localhost`: Windows 11 24H2 and later resolve localhost to IPv6, Ollama binds IPv4. |
| Cleanup never runs, `speech2anywhere.log` shows `Styler failed (Failed to connect to Ollama)` while Ollama is up | Check `OLLAMA_HOST` in your user environment. `0.0.0.0:11434` lets other machines reach Ollama but is no valid target for a client. Since v0.4.0 Speech2Anywhere connects to `127.0.0.1` in that case and shows a tray notice after three failed attempts in a row. |
| Cleanup takes 5 to 15 seconds instead of staying near-instant | `ollama ps` shows the model as `100% CPU`. Known Ollama-on-Windows issue: the GPU discovery probe can time out at model load. Fix: disable hardware-accelerated GPU scheduling under Settings, System, Display, Graphics, add a Windows Defender exclusion for the Ollama processes (`ollama.exe`, `ollama app.exe`, `ollama_llama_server.exe`), update Ollama, reboot. |
| The "cleanup on CPU" toast names WSL or Docker as port owner | Since v0.3.3 Speech2Anywhere checks who holds port 11434. If `wslrelay.exe` or a Docker process holds it, an Ollama from WSL2 or a container answers and the Windows Ollama never gets the port. Stop the foreign Ollama or move it to another port (Docker Compose: `"127.0.0.1:11435:11434"`); the Windows tray app retries the bind and takes over. |
| Text lands in the wrong window | The foreground window at release time (in toggle mode: at the second press) is the target. Do not Alt+Tab while recording. |
| An admin-elevated app does not react to F8 | The keyboard hook cannot see events in elevated windows unless Speech2Anywhere itself runs elevated. Known trade-off. |
