# JARVIS

JARVIS is a desktop-integrated AI assistant widget for Windows. It provides voice interaction, continuous listening, desktop automation, and intelligent task execution via local and remote LLMs.

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
- **TTS (Text-to-Speech)**: Powered by Fish Audio by default, with a fallback to native `WindowsTTS` if the API key fails or lacks credits.

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
- Enhanced browser automation routines.
- Deeper Windows settings integration.
