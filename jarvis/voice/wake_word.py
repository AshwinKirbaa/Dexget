import re
from jarvis.voice.voice_config import WAKE_WORD

def strip_wake_word(text: str) -> str:
    """Strips the wake word from the beginning of the command if present."""
    if not text:
        return text
    
    # e.g., "Jarvis, open Discord" -> "open Discord"
    # "hey Jarvis open Discord" -> "open Discord"
    # "Hey, Jarvis." -> ""
    
    # We must require the wake word.
    # First, handle punctuation
    text_clean = re.sub(r"[^\w\s]", " ", text)  # Replace punctuation with space
    text_clean = re.sub(r"\s+", " ", text_clean).strip()
    
    # Check if wake word is anywhere in the text or just at the beginning
    # For now, require it at the beginning.
    pattern = rf"^(?:hey\s+|hi\s+)?(?:{WAKE_WORD})(?:\s+)?(.*)"
    match = re.match(pattern, text_clean, re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    
    # If the wake word wasn't found at all, return None so it ignores the speech.
    return None
