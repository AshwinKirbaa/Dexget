import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# When frozen by PyInstaller, __file__ resolves into the temp _MEI extraction
# directory. The .env lives next to the actual .exe, so we check there first.
if getattr(sys, 'frozen', False):
    # Running as packaged .exe — .env sits beside JarvisAgent.exe
    _base = Path(sys.executable).parent
else:
    # Running from source — .env is at the repo root
    _base = Path(__file__).resolve().parent.parent.parent

env_path = _base / ".env"
load_dotenv(dotenv_path=env_path, override=False)

WAKE_WORD = os.getenv("WAKE_WORD", "jarvis").lower()
VOICE_MODE = os.getenv("VOICE_MODE", "CONTINUOUS") # or PUSH_TO_TALK

FISH_API_KEY = os.getenv("FISH_API_KEY", "")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID", "14129c3e320149449d6bada6862f7338")
FISH_MODEL = os.getenv("FISH_MODEL", "s2.1-pro-free")

VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "windows") # fish, piper, windows

mic_idx_str = os.getenv("MIC_DEVICE_INDEX", "")
MIC_DEVICE_INDEX = int(mic_idx_str) if mic_idx_str.isdigit() else None

speaker_idx_str = os.getenv("SPEAKER_DEVICE_INDEX", "")
SPEAKER_DEVICE_INDEX = int(speaker_idx_str) if speaker_idx_str.isdigit() else None
