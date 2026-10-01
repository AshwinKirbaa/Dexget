"""
Model Configuration.
Supports FAST_MODEL, AGENT_MODEL, VISION_MODEL.
"""
import os
from dotenv import load_dotenv

load_dotenv()

def get_fast_model() -> str:
    """Returns the FAST_MODEL, typically a small fast model like qwen3:4b"""
    return os.getenv("JARVIS_FAST_MODEL", "qwen2.5:3b")

def get_agent_model() -> str:
    """Returns the AGENT_MODEL, typically a larger model for complex planning"""
    return os.getenv("JARVIS_AGENT_MODEL", "qwen2.5:7b")

def get_vision_model() -> str:
    """Returns the VISION_MODEL, typically a multimodal model like llava"""
    return os.getenv("JARVIS_VISION_MODEL", "llava:7b")

def get_model_timeout() -> int:
    return int(os.getenv("JARVIS_MODEL_TIMEOUT", "300"))

def get_agent_timeout() -> int:
    return int(os.getenv("JARVIS_AGENT_TIMEOUT", "20"))
