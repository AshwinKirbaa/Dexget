import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time
import re

class Intent(str, Enum):
    APPLICATION_OPEN = "APPLICATION_OPEN"
    BROWSER_OPEN = "BROWSER_OPEN"
    BROWSER_RESEARCH = "BROWSER_RESEARCH"
    MUSIC_PLAY = "MUSIC_PLAY"
    YOUTUBE_PLAY = "YOUTUBE_PLAY"
    LOCAL_MEDIA_PLAY = "LOCAL_MEDIA_PLAY"
    OPEN_GMAIL = "OPEN_GMAIL"
    WINDOWS_APP_OPEN = "WINDOWS_APP_OPEN"
    BROWSER_SEARCH = "BROWSER_SEARCH"
    SYSTEM_COMMAND = "SYSTEM_COMMAND"
    WINDOWS_WIFI = "WINDOWS_WIFI"
    WINDOWS_BLUETOOTH = "WINDOWS_BLUETOOTH"
    WINDOWS_BRIGHTNESS = "WINDOWS_BRIGHTNESS"
    WINDOWS_VOLUME = "WINDOWS_VOLUME"
    WINDOWS_AUDIO_OUTPUT = "WINDOWS_AUDIO_OUTPUT"
    WINDOWS_AIRPLANE_MODE = "WINDOWS_AIRPLANE_MODE"
    WINDOWS_ENERGY_SAVER = "WINDOWS_ENERGY_SAVER"
    WINDOWS_ACCESSIBILITY = "WINDOWS_ACCESSIBILITY"
    WINDOWS_QUICK_SETTINGS = "WINDOWS_QUICK_SETTINGS"
    UNKNOWN = "UNKNOWN"

@dataclass
class StructuredIntent:
    intent: Intent
    query: Optional[str] = None
    account: Optional[str] = None
    source: Optional[str] = None
    action: Optional[str] = None
    value: Optional[Any] = None
    confidence: float = 0.0
    application: Optional[str] = None
    browser: Optional[str] = None
    topic: Optional[str] = None


def _classify_common_phrasing(command: str) -> Optional[StructuredIntent]:
    """Zero-latency semantic shortcuts for frequent indirect requests."""
    text = " ".join(command.strip().lower().split())
    browsers = r"chrome|brave|edge|firefox|browser"

    research = re.search(r"(?:research|investigate|look\s+up|search(?:\s+for)?)\s*(.*?)[?.!]*$", text)
    if research:
        remainder = research.group(1).strip(" ?.!")
        browser_match = re.search(r"(?:\s+|^)(?:in|using|with)\s+(chrome|brave|edge|firefox|browser)$", remainder)
        browser = browser_match.group(1) if browser_match else next((b for b in ("chrome", "brave", "edge", "firefox") if b in text), None)
        if browser_match:
            remainder = remainder[:browser_match.start()].strip()
        topic = re.sub(r"^(?:do\s+)?(?:some\s+)?", "", remainder).strip() or None
        return StructuredIntent(Intent.BROWSER_RESEARCH, topic=topic, query=topic, browser=browser or "chrome", confidence=0.93)

    app = re.search(rf"(?:open|launch|start|get|getting|bring)\s+(?:the\s+)?({browsers})(?:\s+(?:ready|up|running|to\s+the\s+front))?", text)
    if app or ("browser" in text and any(p in text for p in ("get the browser ready", "bring the browser"))):
        name = app.group(1) if app else "browser"
        return StructuredIntent(Intent.BROWSER_OPEN, query=name, application=name, browser=name, confidence=0.95)

    browsing = re.search(r"(?:i\s+(?:need|want|would\s+like)\s+to\s+|let\s+me\s+)?browse(?:\s+(?:the\s+web|something))?(?:\s+(?:in|using|with)\s+(chrome|brave|edge|firefox|browser))?", text)
    if browsing:
        name = browsing.group(1) or "browser"
        return StructuredIntent(Intent.BROWSER_OPEN, query=name, application=name, browser=name, confidence=0.94)

    music = re.search(r"(?:listen(?:ing)?\s+to|hearing|hear|play)\s+(?:the\s+)?(.+?)(?:\s+(?:track|song|on youtube(?: music)?))?[?.!]*$", text)
    if music:
        query = re.sub(r"\s+(?:track|song)$", "", music.group(1)).strip()
        return StructuredIntent(Intent.MUSIC_PLAY, query=query, confidence=0.90)
    return None

def classify_intent(command: str, llm_fn) -> StructuredIntent:
    """
    Local semantic classifier (Tier 1) mapping natural language to structured intents.
    """
    common = _classify_common_phrasing(command)
    if common is not None:
        return common
    if llm_fn is None:
        return StructuredIntent(Intent.UNKNOWN)

    prompt = f"""
You are a semantic intent classifier. Analyze the user command and extract the structured intent.
Return ONLY valid JSON matching this schema:
{{
    "intent": "APPLICATION_OPEN|BROWSER_OPEN|BROWSER_RESEARCH|MUSIC_PLAY|YOUTUBE_PLAY|LOCAL_MEDIA_PLAY|OPEN_GMAIL|WINDOWS_APP_OPEN|BROWSER_SEARCH|SYSTEM_COMMAND|WINDOWS_WIFI|WINDOWS_BLUETOOTH|WINDOWS_BRIGHTNESS|WINDOWS_VOLUME|WINDOWS_AUDIO_OUTPUT|WINDOWS_AIRPLANE_MODE|WINDOWS_ENERGY_SAVER|WINDOWS_ACCESSIBILITY|WINDOWS_QUICK_SETTINGS|UNKNOWN",
    "query": "search query, app name, or media title",
    "account": "personal or professional if specified, else null",
    "source": "youtube, youtube music, movies folder, etc if specified",
    "action": "ENABLE|DISABLE|SET|CONNECT|MUTE|UNMUTE, etc. (for system commands)",
    "value": "Value for setting (e.g., 70 for brightness), else null",
    "confidence": 0.0 to 1.0 indicating your confidence in this classification
}}

User command: "{command}"
JSON:
"""
    
    # Enforce short semantic timeout
    original_timeout = os.environ.get("JARVIS_MODEL_TIMEOUT")
    semantic_timeout = int(os.environ.get("JARVIS_SEMANTIC_TIMEOUT", "8"))
    os.environ["JARVIS_MODEL_TIMEOUT"] = str(semantic_timeout)
    
    try:
        response = llm_fn(prompt, schema="json")
        if not response:
            return StructuredIntent(Intent.UNKNOWN)
            
        data = json.loads(response)
        
        intent_str = data.get("intent", "UNKNOWN")
        try:
            intent = Intent(intent_str)
        except ValueError:
            intent = Intent.UNKNOWN
            
        return StructuredIntent(
            intent=intent,
            query=data.get("query"),
            account=data.get("account"),
            source=data.get("source"),
            action=data.get("action"),
            value=data.get("value"),
            confidence=float(data.get("confidence", 0.0)),
            application=data.get("application"),
            browser=data.get("browser"),
            topic=data.get("topic")
        )
    except Exception as e:
        print(f"[SEMANTIC CLASSIFIER ERROR or TIMEOUT] {e}")
        return StructuredIntent(Intent.UNKNOWN)
    finally:
        if original_timeout is not None:
            os.environ["JARVIS_MODEL_TIMEOUT"] = original_timeout
        else:
            del os.environ["JARVIS_MODEL_TIMEOUT"]
