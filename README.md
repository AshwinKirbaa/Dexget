# Dexget

Dexget is a Windows 11 Dynamic Island and local desktop assistant. It places a compact notch at the top of the screen and changes its interface for media, timers, notifications, charging, battery warnings, connected headsets, files, reminders, and assistant tasks.

The project is local-first. Deterministic Windows actions run without an LLM, while natural-language questions and complex automation can use a local Ollama model only when needed.

## Highlights

### Dynamic Island

- Compact clock and battery notch at the top of the screen.
- Contextual layouts for media, timers, notifications, charging, battery warnings, connected headsets, reminders, and phone transfers.
- Media artwork, title, artist, timeline, seeking, play/pause, previous, and next controls.
- Notification cards with application identity, timestamp, message preview, optional sound, and configurable persistence.
- Multiple activity pages so media, timers, and the default dashboard remain independently accessible.
- Configurable swipe, hover, auto-hide, dimensions, appearance, sound, and feature visibility in the separate Notch Settings app.

### Dashboard and productivity

- Quick Launch entries for applications, scripts, keyboard shortcuts, and recorded automations.
- Calendar-style reminders for events, tasks, and schedules.
- Clipboard history for copied text and screenshots, with Copy, Pin, and Clear controls. Pinned entries stay at the top.
- Local search for applications, files, folders, executables, and videos across available drives.
- Temporary multi-file shelf: drag files into the notch, navigate elsewhere, then drag them out at the destination.
- QR-based phone transfer with an Android companion app.

### Windows and AI controls

- Open applications, folders, files, URLs, and Windows Settings pages.
- List, create, copy, move, paste, and guarded-delete file operations.
- Volume, brightness, storage, battery, specifications, and power-plan controls.
- Lock, sign out, sleep, restart, and shutdown actions; disruptive power actions require confirmation.
- Browser and desktop automation using DOM, Windows accessibility, keyboard, and mouse tools.
- Screen Assist captures the current screen and lets you ask a question about it.
- Recorded automations replay with accessibility targets, keyboard navigation, visual matching, and guarded coordinate fallback.

## Requirements

- Windows 11.
- Python 3.10 or later when running from source.
- ARM64 or x64 Python matching the intended package architecture.
- Ollama for local natural-language planning (optional for deterministic controls).
- Dependencies from `requirements.txt`.

> `pyaudiowpatch` may not provide wheels for every Windows ARM64 Python version. Voice input is optional; the notch and text interface work without it.

## Quick start from source

```powershell
python -m pip install -r requirements.txt
ollama pull gemma3:4b
python main.py --doctor
python start_app.py
```

The launcher opens the Dynamic Island instead of the legacy chat window. The packaged application can be assigned to the Copilot hardware key.

If Ollama is unavailable, start it first or let the bundled launcher start `ollama.exe`. Dexget loads the model only for tasks that need it and releases it after the task to reduce idle CPU and memory use.

## Search syntax

Open Search in the expanded island and type a name to find local applications, files, folders, executables, or videos. Press Enter to open the first result or select a specific row.

| Query | Meaning |
| --- | --- |
| `brave` | Search indexed applications and files |
| `:D` | Browse or search the D drive first |
| `:C report` | Search the C drive for `report` |
| `:Movies` | Search a folder named Movies |
| `Movies:D` | Search the Movies folder on D |
| `D: Movies` | Alternative drive/folder form |
| `ask: your question` | Ask Dexget instead of local search |
| `web: your query` | Search the web explicitly |

Application results are deduplicated so an installed application is not followed by redundant shortcuts for the same app.

## Recording reliable automations

1. Expand the island and open **Quick Launch**.
2. Enter **Edit**, add an **Automation**, and start recording.
3. Perform the task at a normal pace. Click named controls when possible and use Tab/Shift+Tab for keyboard-accessible interfaces.
4. Stop recording only after the final visible result appears.
5. Name and save the automation, then run it from Quick Launch.

Replay waits for the target window and control rather than depending only on fixed delays. It tries accessibility metadata first, keyboard focus navigation second, visual matching third, and recorded coordinates only as a fallback. Avoid recording passwords, one-time codes, CAPTCHAs, administrator prompts, or actions depending on unpredictable content.

## Phone transfer

The Android companion is under `android/`. Open Phone Transfer in Dexget, keep the laptop transfer service open, and scan its QR code from the companion app. After pairing, select files from the phone or share files held in the notch shelf.

Local networking, hotspot behavior, Android permissions, and firewall policy can affect discovery. Pairing is private to the displayed session; never expose the transfer service directly to the public internet.

## Local model and voice configuration

The default planner uses Ollama, so no paid API key is required.

```env
JARVIS_LLM_PROVIDER=ollama
JARVIS_MODEL=gemma3:4b
JARVIS_MODEL_TIMEOUT=300
```

Optional providers can be configured in `.env`; environment variables take precedence. Never commit `.env` or API keys.

Windows speech is the free text-to-speech default. Microphone input can use a local Vosk model:

```env
VOICE_PROVIDER=windows
JARVIS_VOSK_MODEL=C:\path\to\vosk-model
```

Faster Whisper and cloud speech providers are optional enhancements.

## Safety boundaries

- Shell commands, destructive file operations, and power actions retain confirmation safeguards.
- Set `JARVIS_FS_ROOT` to semicolon-separated directories to restrict filesystem access.
- Do not disable confirmations unless the machine and commands are fully trusted.
- Custom-drawn apps, CAPTCHAs, protected video, administrator dialogs, and login challenges may need manual intervention.
- Dexget is intended for normal desktop use and must not bypass exam, kiosk, access-control, or security restrictions.

## Build the Windows package

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_copilot_package.ps1
Add-AppxPackage -Path .\dist\JarvisCopilot.msix
```

The build creates the executable, compiles the native Rust search helper, prepares assets, packages the MSIX, and signs it with the configured development certificate.

## Verification

```powershell
python -m pytest jarvis/tests tests -q
python scripts/smoke_browser.py
python scripts/smoke_desktop.py
```

Use `python scripts/smoke_browser.py --live-model` to include live Ollama planning.

## Architecture

```text
widget.py                    PyQt6 Dynamic Island and dashboard
notch_settings.py            Separate customization application
jarvis/                      Agent, tools, configuration, voice, and services
rust/crates/dexget-search/   Native low-latency search helper
android/                     Dexget Android companion
scripts/                     Smoke tests and maintenance utilities
tests/ and jarvis/tests/     Automated test suites
build_copilot_package.ps1    Windows MSIX build and signing pipeline
```

## Development

Run `python start_app.py` while modifying the project. Before packaging a change:

1. Run the relevant tests.
2. Build the MSIX.
3. Install and test the package because packaged paths and permissions differ from source runs.
4. Keep generated output, certificates, secrets, and local model files out of Git.

## License

No license has been declared yet. Add a license file before distributing or accepting third-party contributions.
