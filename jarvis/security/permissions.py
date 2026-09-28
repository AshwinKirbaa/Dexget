"""
Path sanitization and dangerous-command classification.

This mirrors and centralizes the security logic that already existed in
the monolithic jarvis.py (sanitize_path, DESTRUCTIVE_KEYWORDS) so both
the legacy regex command handlers and the new agent tools share exactly
one implementation - no second, competing safety system.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional

# Shell/terminal commands that must never run without explicit confirmation,
# regardless of which tool or code path invokes them.
DESTRUCTIVE_COMMAND_PATTERNS = [
    r"\bdel\b", r"\berase\b", r"\brmdir\b", r"\brm\s+-rf\b", r"\bformat\b",
    r"\bshutdown\b", r"\brestart-computer\b", r"\breg\s+(delete|add)\b",
    r"\bdiskpart\b", r"\bnet\s+user\b", r"\btaskkill\b.*\b/f\b",
    r"\bvssadmin\b", r"\bbcdedit\b", r"\bcipher\s+/w\b", r"\bwevtutil\s+cl\b",
]

# Command executables that should never be allowed via the terminal tool,
# no matter the arguments (registry / credential manipulation, etc).
BLOCKED_EXECUTABLES = {"reg.exe", "diskpart.exe", "vssadmin.exe", "bcdedit.exe"}


def classify_command_risk(command: str) -> str:
    """Returns 'destructive', 'high', 'medium', or 'low' for a shell command string."""
    lowered = command.lower()
    for pattern in DESTRUCTIVE_COMMAND_PATTERNS:
        if re.search(pattern, lowered):
            return "destructive"
    first_token = lowered.strip().split(" ")[0].split("\\")[-1]
    if first_token in BLOCKED_EXECUTABLES:
        return "destructive"
    if any(word in lowered for word in ("delete", "remove", "kill", "stop-process")):
        return "high"
    if any(word in lowered for word in ("move", "rename", "copy", "install", "uninstall")):
        return "medium"
    return "low"


def sanitize_path(path: Optional[str], allowed_roots: Optional[Iterable[str]] = None) -> Optional[str]:
    """
    Resolve `path` to an absolute, normalized path and reject anything that
    escapes the allowed roots (directory traversal guard). Identical
    behavior to the original jarvis.py implementation so both code paths
    agree on what is/isn't safe.
    """
    if path is None:
        return None

    real = os.path.realpath(os.path.abspath(path))

    if allowed_roots:
        allowed = False
        for root in allowed_roots:
            root_real = os.path.realpath(os.path.abspath(root))
            if real == root_real or real.startswith(root_real + os.sep):
                allowed = True
                break
        if not allowed:
            return None

    return real


def redact_secrets(text: str) -> str:
    """Redact obvious secret-looking values before they hit logs or prompts."""
    if not text:
        return text
    patterns = [
        (r"(?i)(api[_-]?key\s*[:=]\s*)([^\s\"']+)", r"\1********"),
        (r"(?i)(password\s*[:=]\s*)([^\s\"']+)", r"\1********"),
        (r"(?i)(token\s*[:=]\s*)([^\s\"']+)", r"\1********"),
        (r"(?i)(secret\s*[:=]\s*)([^\s\"']+)", r"\1********"),
    ]
    out = text
    for pattern, repl in patterns:
        out = re.sub(pattern, repl, out)
    return out
