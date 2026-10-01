"""Load local configuration consistently for the widget and CLI."""
from pathlib import Path
import sys
from dotenv import load_dotenv


def load_environment():
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    load_dotenv(base / ".env", override=False)
