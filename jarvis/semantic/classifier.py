import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time

class Intent(str, Enum):
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

def classify_intent(command: str, llm_fn) -> StructuredIntent:
    """
    Local semantic classifier (Tier 1) mapping natural language to structured intents.
    """
    prompt = f"""
You are a semantic intent classifier. Analyze the user command and extract the structured intent.
Return ONLY valid JSON matching this schema:
{{
    "intent": "YOUTUBE_PLAY|LOCAL_MEDIA_PLAY|OPEN_GMAIL|WINDOWS_APP_OPEN|BROWSER_SEARCH|SYSTEM_COMMAND|WINDOWS_WIFI|WINDOWS_BLUETOOTH|WINDOWS_BRIGHTNESS|WINDOWS_VOLUME|WINDOWS_AUDIO_OUTPUT|WINDOWS_AIRPLANE_MODE|WINDOWS_ENERGY_SAVER|WINDOWS_ACCESSIBILITY|WINDOWS_QUICK_SETTINGS|UNKNOWN",
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
            confidence=float(data.get("confidence", 0.0))
        )
    except Exception as e:
        print(f"[SEMANTIC CLASSIFIER ERROR or TIMEOUT] {e}")
        return StructuredIntent(Intent.UNKNOWN)
    finally:
        if original_timeout is not None:
            os.environ["JARVIS_MODEL_TIMEOUT"] = original_timeout
        else:
            del os.environ["JARVIS_MODEL_TIMEOUT"]
