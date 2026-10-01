# JARVIS

JARVIS is a desktop-integrated AI assistant widget for Windows. It provides voice interaction, continuous listening, desktop automation, and intelligent task execution via local and remote LLMs.

## Local agent setup

The default planner uses Ollama only. No paid API key is required. Ollama is already
usable if `python main.py --doctor` reports `"local_model_ready": true`.

```powershell
python -m pip install -r requirements.txt
ollama pull gemma3:4b
python main.py --doctor
python start_app.py
```

Start Ollama first if it is not running. Copy `.env.example` to `.env` only if you
do not already have a configuration. Environment variables take precedence over `.env`.
The bundled launcher can also start a local `ollama.exe`.
CPU-only inference can take substantial time per step. `JARVIS_MODEL_TIMEOUT`
sets the model request timeout in seconds (default: 300). Simple direct commands
such as opening an explicit URL bypass the planner.

Describe a complete task in the widget, for example: “Open example.com and tell me
its page title,” or “Open Notepad and enter a shopping list.” Text input works
without the speech models. The widget runs one task at a time and shows tool
progress. **Stop** cancels subsequent actions; an in-flight model request or native
tool call must return before the worker exits. Moving the mouse to a screen corner
also triggers PyAutoGUI's fail-safe.

The planner can inspect webpages, fill fields, click controls, read results,
select dropdown options, switch tabs, and enter iframes. Chrome is the default;
set `JARVIS_BROWSER=edge` for Edge. Automation uses its own persistent profile
under `%LOCALAPPDATA%\JarvisAgent`, so it can coexist with your daily browser.
Sign in manually in that window when needed; existing daily-browser logins are
not imported. If the agent requests sign-in or missing information, your next
message resumes the pending task.

Windows apps are inspected through accessibility controls (`desktop_observe`,
`desktop_click`, `desktop_type`, `desktop_focus`), with mouse/keyboard tools and
PowerShell available for other tasks. File tools default to all paths accessible
to your Windows account. Set `JARVIS_FS_ROOT` to semicolon-separated directories
to restrict them. Shell and destructive file actions ask for approval inside the
widget by default. Set `JARVIS_REQUIRE_CONFIRMATION=false` to automatically
authorize those registered tools.

Use `JARVIS_LLM_PROVIDER=ollama` for local-only inference, `openai` for the existing
paid API connector, or `auto` to explicitly permit cloud fallback. Windows speech
is the free default; microphone input additionally needs a Vosk model. Set
`JARVIS_VOSK_MODEL` to its extracted directory. The default is
`~/.jarvis/vosk-model-small-en-us-0.15`. Faster Whisper is an optional enhancement,
enabled with `JARVIS_WHISPER_ENABLED=true` after installing `faster-whisper`.

This is best suited to apps exposing accessibility controls and pages exposing a
DOM. Custom-drawn interfaces, CAPTCHAs, administrator-only dialogs and site login
restrictions can still require your intervention. Small local models can choose
incorrect steps; tool results and failure limits do not guarantee every task.

## Verification

```powershell
python -m pytest jarvis/tests tests -q
python scripts/smoke_browser.py
python scripts/smoke_browser.py --live-model
python scripts/smoke_desktop.py
```

The browser smoke test uses a temporary local HTML form and headless Chrome,
checks the actual saved DOM value, exercises dropdowns and tab switching, and
closes its browser afterwards. `--live-model` lets Ollama plan and operate the form.
Selenium may download a matching driver on first use.
The desktop smoke test briefly opens its own disposable app, types into it,
clicks Save, checks the saved text, and closes that app.

Implementation references: [Selenium browser windows](https://www.selenium.dev/documentation/webdriver/interactions/windows/),
[Ollama generation and JSON output](https://docs.ollama.com/api/generate), and
[pywinauto accessibility controls](https://pywinauto.readthedocs.io/en/latest/code/pywinauto.controls.uiawrapper.html).

## Current Features

- **Desktop Widget**: A floating, always-on-top desktop interface.
- **Voice Pipeline**: Continuous speech-to-text (Vosk) and text-to-speech (Fish Audio / Windows native fallback).
- **Agentic Execution**: Capable of creating plans, executing actions, observing results, and verifying success.
- **Desktop Automation**: Performs filesystem operations, browser navigation, and application launching.
- **Hardware Integration**: Can be packaged as a Windows MSIX app and launched directly via the Copilot hardware key.

## Architecture

1. **Widget (`start_app.py` / `widget.py`)**: The PyQt6-based user interface.
2. **JARVIS Core (`jarvis/`)**: The core application logic.
3. **Agentic Layer (`jarvis/agent/`)**: The Tool Registry, Planner, Executor, Observer, and Verifier for robust task execution.
4. **Tools / Services (`jarvis/tools/`)**: The specific capabilities the agent can invoke (filesystem, Windows UI, web extract, terminal).

## Requirements

- **Windows 11** (or Windows 10 with Copilot key support if using hardware key mapping).
- **Python 3.10+**.
- **Dependencies**: Listed in `requirements.txt`. Requires PyQt6, PyAudioWpatch, Vosk, and other core libraries.

## Installation

1. Clone this repository.
2. Ensure you have Python installed.
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
4. Set up the environment variables (see below).

## Environment Variables

Copy `.env.example` to `.env` and fill in the necessary keys.

- `FISH_API_KEY`: API key for Fish Audio TTS.
- `FISH_VOICE_ID`: Custom voice ID for Fish Audio.
- `VOICE_PROVIDER`: Set to `fish` for cloud TTS or `windows` for local fallback.
- `VOICE_MODE`: Set to `CONTINUOUS` or `WAKE_WORD`.
- `WAKE_WORD`: The wake word to activate JARVIS (e.g., `jarvis`).
- `MIC_DEVICE_INDEX` / `SPEAKER_DEVICE_INDEX`: Leave blank to auto-detect default audio devices.

*Note: The `.env` file should never be committed to Git.*

## Voice Setup

- **STT (Speech-to-Text)**: Powered locally by Vosk. It requires a Vosk model (see Model Setup).
- **TTS (Text-to-Speech)**: Uses native Windows speech by default. Fish Audio is optional.

## Model Setup

- **Vosk STT Model**: You need to download a Vosk English model (e.g., `vosk-model-en-us-0.22`) and extract it. 
  *(Note: Model binaries should be kept locally and not committed to Git).*
- **Ollama**: JARVIS can utilize a local Ollama server for local LLM inference. If Ollama is not installed globally, `launcher.py` or the app can attempt to configure it locally.

## Running JARVIS

To run the JARVIS desktop widget from source:
```cmd
python start_app.py
```

To run JARVIS in CLI mode (without the GUI):
```cmd
python main.py
```

## Project Structure

```text
JARVIS/
│
├── jarvis/
│   ├── agent/       # Agentic reasoning, execution, planning
│   ├── config/      # Configuration
│   ├── memory/      # RAG, document intelligence
│   ├── perception/  # Input parsing
│   ├── security/    # Command confirmation, permissions
│   ├── tools/       # Filesystem, OS, Web, and Browser tools
│   ├── utils/       # Helpers
│   └── voice/       # STT/TTS pipeline
│
├── assets/          # Icons and UI assets
├── config/          # (if any external configuration)
├── tests/           # Unit tests
├── archive/         # Archived scratch/test files
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── start_app.py     # Main GUI entry point
```

## Development

To modify the code, run it from source via `python start_app.py`.
If you modify the UI or backend and want to update the Copilot hardware key version, you must rebuild the MSIX package.

To package the app for the Copilot key:
1. Run the `build_copilot_package.ps1` PowerShell script.
2. Install the resulting `.msix` file.

## Security

**Never commit API keys or private certificates to version control.** 
Always use `.env` for secrets. Any generated development certificates (`*.pfx`) for MSIX packaging are ignored by Git.

## Roadmap

- Extended memory and context persistence across sessions.
- Broader support for custom-drawn interfaces and complex web applications.
- Deeper Windows settings integration.
