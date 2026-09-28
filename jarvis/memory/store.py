"""
SQLite-based memory and preference storage for JARVIS.
Used for remembering personal facts and conversation history.
"""
import os
import sqlite3
from typing import Optional, Dict

DB_PATH = os.path.expanduser("~/.jarvis/memory.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def set_preference(key: str, value: str) -> None:
    """Store a personal preference or fact."""
    key = key.lower().strip()
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
            (key, value)
        )


def get_preference(key: str) -> Optional[str]:
    """Retrieve a stored preference or fact."""
    key = key.lower().strip()
    with _get_conn() as conn:
        cursor = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None


def resolve_user_reference(text: str) -> str:
    """
    Resolve phrases like 'my name', 'my actual name', 'my favorite browser'
    into their stored values, or return the original text if not found.
    """
    text_lower = text.lower().strip()
    
    # Map common phrases to memory keys
    key_map = {
        "my name": "name",
        "my actual name": "name",
        "my college": "college",
        "my university": "college",
        "my course": "course",
        "my email": "email",
        "my phone number": "phone",
        "my phone": "phone",
        "my city": "city",
        "my birthday": "birthday",
        "my favorite browser": "favorite_browser",
        "my preferred browser": "favorite_browser",
        "my favorite language": "favorite_language",
        "my age": "age",
    }
    
    for phrase, key in key_map.items():
        if text_lower == phrase or text_lower.startswith(phrase + " "):
            val = get_preference(key)
            if val:
                return text.lower().replace(phrase, val, 1)
    
    return text
