"""
Deterministic fast-path command router.

Classifies a user command into one of three routing tiers:
  FAST  -- a known simple command: execute directly via tool registry, no LLM.
  CHAT  -- conversational input: send to LLM for a conversational reply only.
  AGENT -- complex/multi-step goal: hand to the full plan->tool->observe loop.

Rules:
  * NEVER calls an LLM to decide routing. This is intentional.
  * Uses regex + lookup tables only -- O(patterns) time.
  * Simple commands must be FAST, no matter what the LLM would say.
"""
from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from jarvis.command_parser import parse_compound_command
from jarvis.command_normalizer import CommandNormalizer
from jarvis.application_parser import ApplicationIntentParser
from jarvis.media_parser import MediaIntentParser
from jarvis.filesystem_parser import parse_filesystem_command


class RouteType(str, Enum):
    FAST  = "fast" # For backward compatibility with existing routes
    CHAT  = "chat"
    AGENT = "agent"
    MEMORY = "memory"
    WINDOWS = "windows"
    APPLICATION = "application"
    BROWSER = "browser"
    SEARCH = "search"
    CONVERSATION = "conversation"
    INFORMATION = "information"
    FILESYSTEM = "filesystem"
    TASK = "task"


@dataclass
class ToolCall:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None

@dataclass
class RouteResult:
    route_type: RouteType
    # For FAST routes -- single tool registry call
    tool_name:  Optional[str]            = None
    tool_args:  Dict[str, Any]           = field(default_factory=dict)
    label:      Optional[str]            = None
    # For composite FAST routes -- multiple tool calls
    tool_calls: List[ToolCall]           = field(default_factory=list)
    text:       Optional[str]            = None


# ---------------------------------------------------------------------------
# Static lookup tables
# ---------------------------------------------------------------------------

KNOWN_APPS: Dict[str, str] = {
    "notepad":              "notepad",
    "calculator":           "calculator",
    "calc":                 "calculator",
    "chrome":               "chrome",
    "google chrome":        "chrome",
    "edge":                 "msedge",
    "microsoft edge":       "msedge",
    "firefox":              "firefox",
    "brave":                "brave",
    "brave browser":        "brave",
    "vs code":              "code",
    "vscode":               "code",
    "visual studio code":   "code",
    "terminal":             "powershell",
    "powershell":           "powershell",
    "cmd":                  "cmd",
    "command prompt":       "cmd",
    "explorer":             "explorer",
    "file explorer":        "explorer",
    "paint":                "mspaint",
    "ms paint":             "mspaint",
    "word":                 "winword",
    "excel":                "excel",
    "powerpoint":           "powerpnt",
    "outlook":              "outlook",
    "teams":                "teams",
    "discord":              "discord",
    "spotify":              "spotify",
    "vlc":                  "vlc",
    "task manager":         "taskmgr",
    "control panel":        "control",
    "snipping tool":        "snippingtool",
    "wordpad":              "wordpad",
    "settings":             "ms-settings:",
    "steam":                "steam",
    "telegram":             "telegram",
    "whatsapp":             "whatsapp",
    "zoom":                 "zoom",
    "obs":                  "obs64",
    "blender":              "blender",
    "gimp":                 "gimp-2.10",
    "photoshop":            "photoshop",
    "premiere":             "premiere",
    "after effects":        "afterfx",
}

KNOWN_SITES: Dict[str, str] = {
    "youtube":              "https://www.youtube.com",
    "google":               "https://www.google.com",
    "github":               "https://www.github.com",
    "chatgpt":              "https://chat.openai.com",
    "gpt":                  "https://chat.openai.com",
    "gmail":                "https://mail.google.com",
    "twitter":              "https://twitter.com",
    "x":                    "https://twitter.com",
    "facebook":             "https://www.facebook.com",
    "reddit":               "https://www.reddit.com",
    "stackoverflow":        "https://stackoverflow.com",
    "stack overflow":       "https://stackoverflow.com",
    "linkedin":             "https://www.linkedin.com",
    "netflix":              "https://www.netflix.com",
    "amazon":               "https://www.amazon.com",
    "wikipedia":            "https://www.wikipedia.org",
    "instagram":            "https://www.instagram.com",
    "twitch":               "https://www.twitch.tv",
    "discord":              "https://discord.com",
    "notion":               "https://www.notion.so",
    "figma":                "https://www.figma.com",
    "vercel":               "https://vercel.com",
    "npm":                  "https://www.npmjs.com",
    "pypi":                 "https://pypi.org",
    "docker hub":           "https://hub.docker.com",
    "google maps":          "https://maps.google.com",
    "maps":                 "https://maps.google.com",
    "google drive":         "https://drive.google.com",
    "drive":                "https://drive.google.com",
    "google docs":          "https://docs.google.com",
    "google sheets":        "https://sheets.google.com",
    "claude":               "https://claude.ai",
    "gemini":               "https://gemini.google.com",
    "bard":                 "https://gemini.google.com",
    "bing":                 "https://www.bing.com",
    "duckduckgo":           "https://duckduckgo.com",
    "spotify":              "https://open.spotify.com",
    "whatsapp":             "https://web.whatsapp.com",
    "pinterest":            "https://www.pinterest.com",
    "medium":               "https://www.medium.com",
    "dev.to":               "https://dev.to",
    "hackernews":           "https://news.ycombinator.com",
    "hacker news":          "https://news.ycombinator.com",
    "hotstar":              "https://www.hotstar.com",
}

# Conversational inputs that should never trigger automation
_CHAT_PATTERNS = [
    r"^(hey|hi|hello|sup|yo|howdy|hiya)[\s!.]*$",
    r"^how are you[\s?!.]*$",
    r"^what('s| is) up[\s?!.]*$",
    r"^(thanks|thank you|thx|ty|cheers)[\s!.]*$",
    r"^(bye|goodbye|see ya|later|cya|so long)[\s!.]*$",
    r"^what can you do[\s?!.]*$",
    r"^who are you[\s?!.]*$",
    r"^help[\s?!.]*$",
    r"^good (morning|afternoon|evening|night)[\s!.]*$",
    r"^what('s| is) your name[\s?!.]*$",
    r"^are you (ai|a bot|a robot|an ai|intelligent|alive)[\s?!.]*$",
    r"^(nice|great|awesome|cool|okay|ok|got it|understood|perfect|sure|sounds good)[\s!.]*$",
    r"^(yes|no|nope|yep|yeah|nah|not really)[\s!.]*$",
    r"^tell me (a joke|something|about yourself)[\s.?]*$",
    r"^(nevermind|never mind|forget it|cancel|stop)[\s.!]*$",
    r"^do you (understand|know what i mean|hear me)[\s?!.]*$",
    r"^(interesting|really|wow|oh|hmm|haha|lol)[\s!.]*$",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(cmd: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", cmd.strip().lower())

LAST_FILESYSTEM_TARGETS = []


def resolve_path(location: str) -> str:
    """Resolve common location names to absolute paths."""
    loc_clean = location.lower().strip()
    if loc_clean.endswith(" folder"):
        loc_clean = loc_clean[:-7].strip()
    if loc_clean.endswith(" directory"):
        loc_clean = loc_clean[:-10].strip()
        
    home = os.path.expanduser("~")
    
    # Dynamically find drives
    import string
    available_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    
    # Try to find common folders across drives
    movies_path = os.path.join(home, "Videos")
    projects_path = os.path.join(home, "Projects") if os.path.exists(os.path.join(home, "Projects")) else os.path.join(home, "Documents", "Projects")
    
    for drive in reversed(available_drives): # Prioritize non-C drives for large files if they exist
        if os.path.exists(os.path.join(drive, "Movies")):
            movies_path = os.path.join(drive, "Movies")
        if os.path.exists(os.path.join(drive, "Projects")):
            projects_path = os.path.join(drive, "Projects")
            
    _map = {
        "desktop":   os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures":  os.path.join(home, "Pictures"),
        "music":     os.path.join(home, "Music"),
        "videos":    os.path.join(home, "Videos"),
        "movies":    movies_path,
        "projects":  projects_path,
        "home":      home,
        "~":         home,
    }
    
    if loc_clean in _map:
        return _map[loc_clean]
        
    if os.path.isabs(location):
        return location
        
    test_path = os.path.join(home, location.title())
    if os.path.exists(test_path):
        return test_path
        
    # Check if they just specified a drive letter without the colon
    if len(loc_clean) == 1 and loc_clean.isalpha():
        test_drive = f"{loc_clean.upper()}:\\"
        if os.path.exists(test_drive):
            return test_drive

    return os.path.join(home, "Desktop", location)


def _fast(tool: str, args: dict, label: str, route_type: RouteType = RouteType.FAST) -> RouteResult:
    return RouteResult(route_type, tool_name=tool, tool_args=args, label=label)

def _memory(action: str, key: str, value: Optional[str] = None, label: Optional[str] = None) -> RouteResult:
    return RouteResult(RouteType.MEMORY, tool_name=action, tool_args={"key": key, "value": value}, label=label)

def _windows(tool: str, args: dict, label: str) -> RouteResult:
    return _fast(tool, args, label, RouteType.WINDOWS)

def _application(tool: str, args: dict, label: str) -> RouteResult:
    return _fast(tool, args, label, RouteType.APPLICATION)

def _browser(tool: str, args: dict, label: str) -> RouteResult:
    return _fast(tool, args, label, RouteType.BROWSER)

def _search(tool: str, args: dict, label: str) -> RouteResult:
    return _fast(tool, args, label, RouteType.SEARCH)

def _fast_multi(calls: List[ToolCall], route_type: RouteType = RouteType.FAST) -> RouteResult:
    return RouteResult(route_type, tool_calls=calls)

def _information(tool: str, args: dict, label: str) -> RouteResult:
    return RouteResult(RouteType.INFORMATION, tool_name=tool, tool_args=args, label=label)


# ---------------------------------------------------------------------------
# Individual recognisers — return RouteResult or None
# ---------------------------------------------------------------------------

def _try_chat(cmd: str) -> Optional[RouteResult]:
    for pat in _CHAT_PATTERNS:
        if re.match(pat, cmd, re.IGNORECASE):
            return RouteResult(RouteType.CHAT)
    return None

def _try_conversation(cmd: str) -> Optional[RouteResult]:
    """'what is data', 'explain API', 'how does TCP work', 'give me python code' -> CONVERSATION"""
    if re.match(r"^(?:search|google|find\s+online)\b", cmd, re.IGNORECASE):
        return None
        
    patterns = [
        r"^(?:what|who|where|why|how)\s+(?:is|are|was|were|do|does|did|can|will|would|could)\b.*",
        r"^explain\b.*",
        r"^tell\s+me\s+(?:about|why|how)\b.*",
        r"^(?:give|show|write)\s+(?:me\s+)?(?:a\s+)?(?:simple\s+)?(?:python|javascript|java|c\+\+|code|program|script)\b.*",
        r"^(?:calculate|compute|solve)\b.*",
    ]
    for pat in patterns:
        if re.match(pat, cmd, re.IGNORECASE):
            return RouteResult(RouteType.CONVERSATION)
    return None

def _try_information_question(cmd: str) -> Optional[RouteResult]:
    """Intercept system, hardware, time, network, etc questions before CONVERSATION."""
    # TIME
    if re.match(r"^(?:what(?:'s| is)\s+the\s+time(?: \w+)?|what\s+time\s+is\s+it.*|current\s+time|tell\s+me\s+the\s+time)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_time", {}, "TIME")
    
    # DATE
    if re.match(r"^(?:what(?:'s| is)\s+today(?:'s)?\s+date|what\s+date\s+is\s+it.*|today(?:'s)?\s+date|what\s+day\s+is\s+today|what\s+day\s+is\s+it|what(?:'s| is)\s+the\s+current\s+date|what\s+day\s+of\s+the\s+week\s+is\s+it)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_date", {}, "DATE")
        
    # SYSTEM / LAPTOP SPECS
    if re.match(r"^(?:what\s+is\s+my\s+laptop\s+specification|what\s+are\s+my\s+(?:laptop\s+)?specs|tell\s+me\s+about\s+my\s+laptop|what\s+laptop\s+am\s+i\s+using|what\s+are\s+my\s+system\s+specifications|show\s+(?:my\s+)?(?:pc|system|computer)\s+(?:specs|specifications)|what\s+are\s+my\s+hardware\s+specifications)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_specs", {}, "SYSTEM_INFORMATION")

    # CPU
    if re.match(r"^(?:what\s+cpu\s+do\s+i\s+have|what\s+processor\s+do\s+i\s+have|what\s+is\s+my\s+processor|which\s+processor\s+is\s+in\s+my\s+laptop|how\s+many\s+cpu\s+cores\s+do\s+i\s+have|how\s+many\s+threads\s+does\s+my\s+cpu\s+have|what\s+is\s+my\s+cpu\s+usage|how\s+much\s+cpu\s+am\s+i\s+using|what\s+processor\s+am\s+i\s+using)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_cpu", {}, "CPU_INFORMATION")

    # RAM
    if re.match(r"^(?:what\s+ram\s+do\s+i\s+have|how\s+much\s+ram\s+(?:do\s+i\s+have|is\s+in\s+my\s+laptop)|what\s+is\s+my\s+(?:total\s+)?ram|how\s+much\s+ram\s+is\s+free|how\s+much\s+ram\s+am\s+i\s+using|what\s+percentage\s+of\s+ram\s+am\s+i\s+using|show\s+ram\s+usage|is\s+my\s+ram\s+full|tell\s+me\s+my\s+memory|what\s+is\s+the\s+memory\s+capacity)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_ram", {}, "RAM_INFORMATION")

    # STORAGE
    if re.match(r"^(?:what\s+is\s+my\s+laptop\s+total\s+storage\s+capacity|how\s+much\s+(?:storage|disk\s+space)\s+(?:do\s+i\s+have|have\s+i\s+got)|how\s+much\s+free\s+storage\s+do\s+i\s+have|how\s+much\s+space\s+(?:is\s+left|do\s+i\s+have)|show\s+my\s+(?:storage|disks|drives)|how\s+much\s+storage\s+is\s+available|what\s+drives\s+do\s+i\s+have|what\s+is\s+the\s+size\s+of\s+my\s+[a-z]\s+drive)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_storage", {}, "STORAGE_INFORMATION")
        
    if re.match(r"^how\s+much\s+space\s+is\s+left\s+on\s+([a-z])[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_storage", {}, "STORAGE_INFORMATION")

    # GPU
    if re.match(r"^(?:what\s+(?:gpu|graphics\s+card)\s+do\s+i\s+have|which\s+gpu\s+is\s+installed|what\s+is\s+my\s+(?:gpu|graphics\s+card)|what\s+is\s+my\s+gpu\s+usage|how\s+much\s+gpu\s+memory\s+do\s+i\s+have)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_gpu", {}, "GPU_INFORMATION")

    # BATTERY
    if re.match(r"^(?:what\s+is\s+my\s+battery\s+percentage|how\s+much\s+battery\s+do\s+i\s+have|is\s+my\s+laptop\s+charging|how\s+long\s+will\s+my\s+battery\s+last|what\s+is\s+my\s+battery\s+status|am\s+i\s+plugged\s+in|is\s+the\s+laptop\s+charging)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_battery", {}, "BATTERY_INFORMATION")

    # WINDOWS OS
    if re.match(r"^(?:what\s+(?:version\s+of\s+windows|windows|windows\s+version|windows\s+build|build)\s+(?:am\s+i\s+(?:using|running)|do\s+i\s+have)|is\s+this\s+windows\s+10\s+or\s+11|what\s+architecture\s+am\s+i\s+using)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_os", {}, "OS_INFORMATION")

    # NETWORK
    if re.match(r"^(?:what\s+is\s+my\s+(?:ip\s+address|local\s+ip|public\s+ip|mac\s+address|wifi\s+name|network\s+status|internet\s+status)|am\s+i\s+connected\s+to\s+wifi|what\s+network\s+am\s+i\s+connected\s+to)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_network", {}, "NETWORK_INFORMATION")

    # DISPLAY
    if re.match(r"^(?:what\s+is\s+my\s+(?:screen|display)\s+resolution|how\s+many\s+monitors\s+do\s+i\s+have|what\s+monitor\s+am\s+i\s+using|what\s+is\s+my\s+refresh\s+rate|what\s+displays\s+are\s+connected)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_display", {}, "DISPLAY_INFORMATION")

    # FILESYSTEM QUESTIONS
    if re.match(r"^(?:where\s+is|does)\s+(?:my\s+|the\s+)?(.+?)\s*(?:folder|directory|file)(?:\s+exist)?[\s?!.]*$", cmd, re.IGNORECASE):
        m = re.match(r"^(?:where\s+is|does)\s+(?:my\s+|the\s+)?(.+?)\s*(?:folder|directory|file)(?:\s+exist)?[\s?!.]*$", cmd, re.IGNORECASE)
        # Note: if it's "where is dexter stored", that doesn't use folder.
        return _information("fs_info", {"query": cmd}, "FILESYSTEM")
    if re.match(r"^(?:where\s+is\s+(.+)\s+stored|does\s+this\s+file\s+exist|what\s+files\s+are\s+in\s+my\s+(.+)|how\s+many\s+files\s+are\s+in\s+(.+)|what\s+is\s+the\s+size\s+of\s+my\s+(.+))[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("fs_info", {"query": cmd}, "FILESYSTEM")

    # PROCESS QUESTIONS
    if re.match(r"^(?:what\s+(?:programs|applications)\s+are\s+running|show\s+running\s+processes|what\s+is\s+using\s+my\s+ram|what\s+is\s+using\s+cpu|which\s+process\s+(?:uses|is\s+using)\s+the\s+most\s+(?:ram|cpu))[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_process", {}, "PROCESS_INFORMATION")
    if re.match(r"^is\s+(.+?)\s+(?:running|open|installed)[\s?!.]*$", cmd, re.IGNORECASE):
        m = re.match(r"^is\s+(.+?)\s+(?:running|open|installed)[\s?!.]*$", cmd, re.IGNORECASE)
        app = m.group(1).strip()
        return _information("sys_get_application", {"app_name": app}, "APPLICATION_INFORMATION")
    if re.match(r"^(?:what\s+(?:applications|programs)\s+are\s+(?:open|installed)|do\s+i\s+have\s+(.+)\s+installed)[\s?!.]*$", cmd, re.IGNORECASE):
        return _information("sys_get_application", {"query": cmd}, "APPLICATION_INFORMATION")

    return None


def _try_memory(cmd: str) -> Optional[RouteResult]:
    # Match "remember that ...", "from now on ...", "always ...", "my preference is ...", "i prefer ..."
    patterns = [
        r"^(?:remember|store|save)(?:\s+that)?\s+(.+)$",
        r"^(?:from\s+now\s+on|always)\s+(.+)$",
        r"^my\s+preference\s+is\s+(.+)$",
        r"^i\s+(?:prefer|like)\s+(.+)$"
    ]
    for pat in patterns:
        m = re.match(pat, cmd, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            
            # Extract "my X is Y" to store as key=X, value=Y
            sm = re.match(r"^my\s+(.+?)\s+(?:is|are|was|were)\s+(.+)$", val, re.IGNORECASE)
            if sm:
                key = sm.group(1).strip()
                value = sm.group(2).strip()
                key_formatted = key.replace(" ", "_").lower()
                return _memory("set", key_formatted, value, f"Remembering that your {key} is {value}")
                
            return _memory("set", "preference", val, f"Remembering your preference: {val}")

    # Set exact preferences based on old regexes (keep them for backward compatibility if needed, but the above catches most)
    m = re.match(r"^my\s+(.+?)\s+is\s+(.+)$", cmd, re.IGNORECASE)
    if m:
        key, value = m.group(1).strip(), m.group(2).strip()
        key_formatted = key.replace(" ", "_").lower()
        return _memory("set", key_formatted, value, f"Remembering that your {key} is {value}")

    # Get preferences
    # We require 'my' for generic preference lookups to avoid capturing 'what is RAG'
    m = re.match(r"^(?:what(?:'s| is)|tell me|do you know|who am i(?:\s+what is my name)?)\s+my\s+(.+?)[\s?!.]*$", cmd, re.IGNORECASE)
    if m:
        key = m.group(1).strip()
        key_formatted = key.replace(" ", "_").lower()
        return _memory("get", key_formatted, label=f"Looking up {key}")

    # Also handle specific identity questions without 'my'
    if cmd.lower().strip() in ("who am i", "what is my name", "whats my name", "tell me my name"):
        return _memory("get", "name", label="Looking up name")
        
    m = re.match(r"^(?:what|which)\s+(?:browser|editor|language)\s+(?:do i\s+)?(?:prefer|use|like)[\s?!.]*$", cmd, re.IGNORECASE)
    if m:
        if "browser" in cmd.lower():
            return _memory("get", "favorite_browser", label="Looking up favorite browser")
        if "editor" in cmd.lower():
            return _memory("get", "favorite_editor", label="Looking up favorite editor")
        if "language" in cmd.lower():
            return _memory("get", "favorite_language", label="Looking up favorite language")

    return None

def _try_schedule(cmd: str) -> Optional[RouteResult]:
    m = re.match(r"^(?:remind\s+me|schedule)\s+(?:to\s+)?(.+?)\s+in\s+(\d+)\s+(seconds?|minutes?|hours?)$", cmd, re.IGNORECASE)
    if m:
        action = m.group(1).strip()
        val = int(m.group(2))
        unit = m.group(3).lower()
        if "second" in unit: delay = val
        elif "minute" in unit: delay = val * 60
        elif "hour" in unit: delay = val * 3600
        else: delay = val
        
        return _fast("sys_schedule_delay", {"command": action, "delay_seconds": delay}, f"Scheduling '{action}' in {val} {unit}")
        
    m = re.match(r"^(?:every\s+morning\s+at|every\s+day\s+at)\s+(\d+)(am|pm)?\s+(?:say|run|do)?\s*(.+)$", cmd, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        ampm = (m.group(2) or "").lower()
        action = m.group(3).strip()
        if ampm == "pm" and hour < 12: hour += 12
        if ampm == "am" and hour == 12: hour = 0
        cron_expr = f"0 {hour} * * *"
        return _fast("sys_schedule_cron", {"command": action, "cron_expr": cron_expr}, f"Scheduling '{action}' daily at {hour:02d}:00")
        
    if re.match(r"^(?:cancel|clear|stop)\s+(?:all\s+)?(?:schedules?|alarms?|timers?|reminders?)[\s?!.]*$", cmd, re.IGNORECASE):
        return _fast("sys_schedule_cancel", {}, "Cancelling schedules")
        
    return None

def _try_document_ingestion(cmd: str) -> Optional[RouteResult]:
    # E.g., "read report.pdf", "ingest my data.csv"
    m = re.match(r"^(?:read|ingest|process|learn)\s+(?:the\s+|my\s+)?([\w\-\.\:\\]+\.(?:pdf|txt|docx|csv|md|xlsx|pptx|png|jpg|jpeg))$", cmd, re.IGNORECASE)
    if m:
        path = m.group(1).strip()
        return _fast("rag_ingest", {"file_path": path}, f"Reading {path}")
    return None

def _try_youtube(cmd: str) -> Optional[RouteResult]:
    """'play X on youtube', 'youtube X', 'search X on youtube'"""
    if "youtube music" in cmd.lower():
        return None
        
    patterns = [
        r"^play\s+(.+?)\s+(?:(?:on|in)\s+)?youtube$",
        r"^(?:search|find|look\s+up)\s+(.+?)\s+(?:(?:on|in)\s+)?youtube$",
        r"^(?:search|find|look\s+up)\s+youtube\s+for\s+(.+)$",
        r"^youtube\s+(?:search\s+for\s+|play\s+|search\s+)?(.+)$",
        r"^(?:watch|stream)\s+(.+?)\s+(?:(?:on|in)\s+)?youtube$",
        r"^(?:open\s+(?:\w+)[,\s]+)?search\s+(.+?)\s+(?:(?:on|in)\s+)?youtube\s+and\s+play(?:\s+it|\s+the\s+video(?:\s+song)?)?[\s.!]*$",
        r"^(?:open\s+(?:\w+)[,\s]+)?search\s+(.+?)\s+(?:(?:on|in)\s+youtube|and\s+play(?:\s+it|\s+the\s+video(?:\s+song)?)?)[\s.!]*$",
        r"^(?:go\s+to\s+youtube\s+and\s+)?play\s+(.+?)(?:\s+(?:on|in)\s+youtube)?[\s.!]*$",
    ]
    for pat in patterns:
        m = re.match(pat, cmd, re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            return RouteResult(RouteType.TASK, tool_name="youtube_play", tool_args={"query": query}, label=f"Playing '{query}' on YouTube")
    return None

def _try_youtube_music(cmd: str) -> Optional[RouteResult]:
    """'play X in youtube music', 'youtube music X', 'search X on youtube music'"""
    patterns = [
        r"^play\s+(.+?)\s+(?:in|on)\s+youtube\s+music$",
        r"^(?:search|find|look\s+up)\s+(.+?)\s+(?:in|on)\s+youtube\s+music$",
        r"^youtube\s+music\s+(?:search\s+for\s+|play\s+|search\s+)?(.+)$",
        r"^(?:listen\s+to|stream)\s+(.+?)\s+(?:in|on)\s+youtube\s+music$",
    ]
    for pat in patterns:
        m = re.match(pat, cmd, re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            return RouteResult(RouteType.TASK, tool_name="youtube_music_play", tool_args={"query": query}, label=f"Playing '{query}' on YouTube Music")
    return None


def _try_open_site(cmd: str) -> Optional[RouteResult]:
    """'open youtube', 'open google.com', 'go to github', 'open gmail in brave professional account'"""
    from jarvis.tasks.accounts import account_manager
    cmd_clean, account_override = account_manager.extract_account_alias(cmd)
    
    m = re.match(r"^(?:open|go\s+to|visit|browse|navigate\s+to|show\s+me)\s+(.+?)(?:\s+in\s+(?:the\s+)?(chrome|brave|edge|firefox|browser))?[\s.!]*$", cmd_clean, re.IGNORECASE)
    if not m:
        return None
    target = m.group(1).strip().lower()
    browser_override = m.group(2).strip().lower() if m.group(2) else None

    # Exact known site
    if target in KNOWN_SITES:
        url = KNOWN_SITES[target]
        return RouteResult(RouteType.TASK, tool_name="web_open", tool_args={"url": url, "site_name": target, "account_override": account_override, "browser_override": browser_override}, label=f"Opening {target.title()} in browser")

    # Looks like a URL (has a TLD)
    if re.match(r"^[\w.-]+\.(com|org|net|io|dev|ai|co|gov|edu|me|app|uk|in)(/.*)?$", target):
        url = target if target.startswith("http") else f"https://{target}"
        site_name = target.split(".")[0]
        return RouteResult(RouteType.TASK, tool_name="web_open", tool_args={"url": url, "site_name": site_name, "account_override": account_override, "browser_override": browser_override}, label=f"Opening {target} in browser")

    # If user explicitly requested "in browser" but it isn't a known site, it goes to search
    if "in browser" in cmd.lower() or browser_override:
        url = f"https://www.google.com/search?q={urllib.parse.quote(target)}"
        return _search("browser_open", {"url": url}, f"Searching {target} in browser")

    return None

def _try_open_and_type(cmd: str) -> Optional[RouteResult]:
    """'open notepad and type hello world', 'open new notepad and type my actual name'"""
    m = re.match(r"^(?:open|launch|start|run)\s+(?:new\s+)?(\w+)(?:,?|(?:\s+and)?)\s+(?:type|write|enter|put)\s+(.+)$", cmd, re.IGNORECASE)
    if m:
        app_key = m.group(1).strip().lower()
        text = m.group(2).strip()
        
        # Resolve 'my actual name' to the actual name via memory
        from jarvis.memory.store import resolve_user_reference
        text = resolve_user_reference(text)

        if app_key in KNOWN_APPS:
            app = KNOWN_APPS[app_key]
            return _fast_multi([
                ToolCall("win_open_application", {"app_name": app}, f"Opening {app_key.title()}..."),
                ToolCall("keyboard_type", {"text": text}, f"Typing {text!r}...")
            ], route_type=RouteType.WINDOWS)
    return None

def _try_open_app(cmd: str) -> Optional[RouteResult]:
    """'open notepad', 'launch calculator', 'start powershell'"""
    from jarvis.tasks.accounts import account_manager
    cmd_clean, account_override = account_manager.extract_account_alias(cmd)
    
    # Use the new ApplicationIntentParser
    intent = ApplicationIntentParser.parse(cmd_clean)
    if not intent:
        return None
        
    app_key = intent.application.lower()
    
    # Extract browser override if any
    browser_match = re.match(r"^(.+?)\s+in\s+(chrome|brave|edge|firefox|browser)$", app_key)
    browser_override = None
    if browser_match:
        app_key = browser_match.group(1)
        browser_override = browser_match.group(2)
        
    profile_match = re.match(r"^(.+?)\s+(?:in|with)\s+(.+?)(?:\s+profile)?$", app_key)
    if profile_match and profile_match.group(1) in ["brave", "chrome", "google chrome", "edge", "firefox", "browser"]:
        app_key = profile_match.group(1)

    if "in browser" in cmd.lower():
        return None

    # If it's a known site but NOT a known app, let _try_open_site handle it
    if app_key in KNOWN_SITES and app_key not in KNOWN_APPS:
        return None

    # Let the robust application resolver try to find it!
    # Even if it's not in KNOWN_APPS, the resolver can search Start Menu, Registry, etc.
    app = KNOWN_APPS.get(app_key, app_key)
    from jarvis.tools.application_resolver import find_installed_application
    app_info = find_installed_application(app)
    if not app_info["installed"] and not app_info.get("web_fallback"):
        # Check if this is EXPLICITLY meant to be an application.
        # If not explicit, return None so it can fall through to filesystem, browser, or agent.
        verb_match = re.match(r"^([a-zA-Z]+)", cmd)
        verb = verb_match.group(1).lower() if verb_match else "open"
        
        is_explicit = False
        if verb in ["launch", "start", "run", "execute"]:
            is_explicit = True
        elif "_" in app_key:
            is_explicit = True
        elif any(w in app_key.split() for w in ["application", "app", "program"]):
            is_explicit = True
            
        if not is_explicit:
            return None
        
    if intent.secondary_action:
        return _fast_multi([
            ToolCall("win_open_application", {"app_name": app}, f"Opening {app.title()}"),
            ToolCall("keyboard_type", {"text": intent.expression}, f"Executing {intent.secondary_action} {intent.expression}")
        ], route_type=RouteType.APPLICATION)
        
    return _application("win_open_application", {"app_name": app}, f"Opening {app.title()}")


def _try_close_app(cmd: str) -> Optional[RouteResult]:
    """'close notepad', 'kill chrome'"""
    m = re.match(r"^(?:close|kill|quit|exit|terminate)\s+(.+)$", cmd, re.IGNORECASE)
    if not m:
        return None
    app_name = m.group(1).strip()
    return _application("win_close_application", {"app_name": app_name}, f"Closing {app_name}")


def _try_search(cmd: str) -> Optional[RouteResult]:
    """'search Python', 'google neural networks', 'open brave and search google for AI'"""
    patterns = [
        r"^(?:open\s+(?:\w+)[,\s]+)?(?:and\s+)?search\s+google\s+for\s+(.+)$",
        r"^(?:open\s+(?:\w+)[,\s]+)?(?:and\s+)?(?:search(?:\s+for)?|google|bing|look\s+up|find\s+(?:info(?:rmation)?\s+(?:about|on)\s+)?|query)\s+(.+)$"
    ]
    for pat in patterns:
        m = re.match(pat, cmd, re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            return _search("browser_open", {"url": url}, f"Searching Google for '{query}'")
    return None


def _try_lock(cmd: str) -> Optional[RouteResult]:
    """'lock', 'lock my pc', 'lock the screen'"""
    pat = r"^lock(?:\s+(?:my\s+|the\s+)?(?:pc|computer|screen|workstation|windows|session))?[\s.!]*$"
    if re.match(pat, cmd, re.IGNORECASE):
        return _windows("win_lock_pc", {}, "Locking PC")
    return None


def _try_brightness(cmd: str) -> Optional[RouteResult]:
    """'set brightness to 50%', 'increase brightness'"""
    
    if re.match(r"^(?:increase|raise|brighten)\s+(?:my\s+|the\s+)?brightness[\s.!]*$", cmd, re.IGNORECASE):
        return _windows("win_brightness_up", {}, "Increasing brightness")
        
    if re.match(r"^(?:decrease|lower|dim)\s+(?:my\s+|the\s+)?brightness[\s.!]*$", cmd, re.IGNORECASE):
        return _windows("win_brightness_down", {}, "Decreasing brightness")
        
    patterns = [
        r"^(?:set|change|adjust)\s+(?:the\s+|screen\s+)?brightness\s+to\s+(\d+)\s*%?$",
        r"^(?:increase|decrease|dim|raise)\s+(?:my\s+|the\s+)?brightness\s+to\s+(\d+)\s*%?$",
        r"^brightness\s+(?:to\s+)?(\d+)\s*%?$",
        r"^(?:make|set)\s+(?:the\s+)?brightness\s+(?:to\s+)?(\d+)\s*(?:percent)?$",
        r"^(?:set|change)\s+brightness\s+(\d+)$",
    ]
    for pat in patterns:
        m = re.match(pat, cmd, re.IGNORECASE)
        if m:
            val = max(0, min(100, int(m.group(1))))
            return _windows("win_set_brightness", {"percent": val}, f"Setting brightness to {val}%")
    # get brightness
    if re.match(r"^(?:get|what(?:'s| is)(?: the)?|show(?: me)?(?:\s+the)?|current)\s+brightness[\s?!.]*$", cmd, re.IGNORECASE):
        return _windows("win_get_brightness", {}, "Getting current brightness")
    return None


def _try_volume(cmd: str) -> Optional[RouteResult]:
    """'mute', 'unmute', 'set volume to 60%', 'volume up'"""
    # Mute
    if re.match(r"^mute(?:\s+(?:audio|sound|volume|the\s+(?:audio|sound|volume)))?[\s.!]*$", cmd, re.IGNORECASE):
        return _windows("win_mute", {}, "Muting audio")
    # Unmute
    if re.match(r"^unmute(?:\s+(?:audio|sound|volume|the\s+(?:audio|sound|volume)))?[\s.!]*$", cmd, re.IGNORECASE):
        return _windows("win_unmute", {}, "Unmuting audio")
        
    # Up/Down
    if re.match(r"^(?:volume\s+up|increase\s+volume|louder)$", cmd, re.IGNORECASE):
        return _windows("win_volume_up", {}, "Increasing volume")
    if re.match(r"^(?:volume\s+down|decrease\s+volume|softer|quieter)$", cmd, re.IGNORECASE):
        return _windows("win_volume_down", {}, "Decreasing volume")

    # Set volume
    patterns = [
        r"^(?:set|change|adjust)\s+(?:the\s+)?(?:volume|audio)\s+to\s+(\d+)\s*%?$",
        r"^volume\s+(?:to\s+)?(\d+)\s*%?$",
        r"^(?:set|change)\s+volume\s+(\d+)$",
    ]
    for pat in patterns:
        m = re.match(pat, cmd, re.IGNORECASE)
        if m:
            val = max(0, min(100, int(m.group(1))))
            return _fast("win_volume_set", {"percent": val}, f"Setting volume to {val}%")
    return None


def _try_power(cmd: str) -> Optional[RouteResult]:
    """'shutdown', 'restart', 'sleep'"""
    if re.match(
        r"^(?:shut\s*down|shutdown|power\s*off|turn\s+off\s+(?:my\s+|the\s+)?(?:pc|computer|laptop))[\s.!]*$",
        cmd, re.IGNORECASE,
    ):
        return _windows("win_shutdown", {}, "Shutting down (30-second delay, run 'shutdown /a' to cancel)")
    if re.match(
        r"^restart(?:\s+(?:my\s+|the\s+)?(?:pc|computer|laptop))?[\s.!]*$",
        cmd, re.IGNORECASE,
    ):
        return _windows("win_restart", {}, "Restarting (30-second delay, run 'shutdown /a' to cancel)")
    if re.match(
        r"^sleep(?:\s+(?:my\s+|the\s+)?(?:pc|computer|laptop))?[\s.!]*$",
        cmd, re.IGNORECASE,
    ):
        return _windows("win_sleep", {}, "Putting PC to sleep")
    return None

def _try_system_info(cmd: str) -> Optional[RouteResult]:
    """'what is my cpu usage', 'system info', 'what time is it', 'how much ram do i have'"""
    if re.match(r"^(?:get\s+|show\s+|what(?:'s| is|)\s+(?:the\s+)?)?(?:time)(?:\s+is\s+it)?[\s?!.]*$", cmd, re.IGNORECASE):
        return _fast("sys_get_time", {}, "Getting current time")
        
    if re.match(r"^(?:get\s+|show\s+|what(?:'s| is)\s+(?:the\s+)?)?(?:date|today's date)(?:\s+today)?[\s?!.]*$", cmd, re.IGNORECASE):
        return _fast("sys_get_date", {}, "Getting current date")
        
    if re.match(r"^(?:get\s+|show\s+|what(?:'s| is)\s+(?:my\s+|the\s+)?)?(?:gpu|graphics card)(?:\s*(?:info(?:rmation)?|specs?|details?))?[\s?!.]*$", cmd, re.IGNORECASE):
        return _fast("sys_get_gpu", {}, "Getting GPU info")
        
    if re.match(r"^(?:get\s+|show\s+|what(?:'s| is)\s+(?:my\s+|the\s+)?)?(?:battery)(?:\s*(?:info(?:rmation)?|status|percent(?:age)?|level))?[\s?!.]*$", cmd, re.IGNORECASE):
        return _fast("sys_get_battery", {}, "Getting battery info")
        
    if re.match(r"^(?:get\s+|show\s+|what(?:'s| is)\s+(?:my\s+|the\s+)?)?(?:storage|disk space)(?:\s*(?:info(?:rmation)?|stats?))?[\s?!.]*$", cmd, re.IGNORECASE):
        return _fast("sys_get_storage", {}, "Getting storage info")
        
    if re.match(r"^(?:get\s+|show\s+|what(?:'s| is)\s+(?:my\s+|the\s+)?)?(?:network|ip)(?:\s*(?:info(?:rmation)?|address))?[\s?!.]*$", cmd, re.IGNORECASE):
        return _fast("sys_get_network", {}, "Getting network info")
        
    if re.match(r"^(?:get\s+|show\s+|what(?:'s| is)\s+(?:my\s+|the\s+)?)?(?:cpu|ram|memory|system|pc|specs?)(?:\s*(?:usage|info(?:rmation)?|stats?|specifications?))?[\s?!.]*$", cmd, re.IGNORECASE) or "how much ram" in cmd.lower() or "how much memory" in cmd.lower():
        return _fast("win_system_info", {}, "Getting system info")
        
    return None


from jarvis.filesystem_parser import parse_filesystem_command

def _try_filesystem(cmd: str) -> Optional[RouteResult]:
    intent = parse_filesystem_command(cmd)
    if not intent:
        return None
        
    return RouteResult(
        RouteType.FILESYSTEM,
        tool_args={
            "intent": intent.intent,
            "target_name": intent.target_name,
            "target_type": intent.target_type,
            "location": intent.location,
            "location_type": intent.location_type,
            "action": intent.action,
            "original_cmd": cmd
        },
        label=f"Filesystem: {intent.action} {intent.target_name or ''}"
    )


def _try_local_media(cmd: str) -> Optional[RouteResult]:
    """'play Dexter S07E02 from movies folder', 'play S07E02'"""
    intent = MediaIntentParser.parse(cmd)
    if not intent:
        return None
            
    args = {
        "media_title": intent.title,
        "season": intent.season,
        "episode": intent.episode,
        "source": intent.location or "movies folder"
    }
    
    return _windows("win_play_local_media", args, f"Playing local media")

def _try_browser_search_and_play(cmd: str) -> Optional[RouteResult]:
    """'open brave search radhimma and play'"""
    m = re.match(r"^(?:open|launch)?\s*(?:brave|chrome|browser|edge|firefox)?\s*search\s+(?:on\s+)?(?:youtube\s+)?(?:for\s+)?(.+?)\s+and\s+play$", cmd, re.IGNORECASE)
    if m:
        query = m.group(1).strip()
        return RouteResult(RouteType.TASK, tool_name="youtube_play", tool_args={"query": query}, label=f"Playing '{query}' on YouTube")
    return None

def _try_settings(cmd: str) -> Optional[RouteResult]:
    m = re.match(r"^open\s+(?:windows\s+)?settings(?:[\s.!]*)$", cmd, re.IGNORECASE)
    if m:
        return _application("win_open_application", {"app_name": "ms-settings:"}, "Opening Windows Settings")
    
    # If they say something like "open settings and go to sign in"
    m = re.match(r"^open\s+(?:windows\s+)?settings\s+(.*)$", cmd, re.IGNORECASE)
    if m:
        # Return a chat response directly bypassing agent
        return RouteResult(RouteType.CHAT, text="Which settings do you mean — Windows settings or an app's settings?")

    return None

def _try_compound_workflow(cmd: str) -> Optional[RouteResult]:
    parsed = parse_compound_command(cmd)
    if parsed.primary_intent == "unknown":
        return None
        
    if parsed.primary_intent == "browser_search":
        step = parsed.workflow_steps[0]
        query = step.parameters.get("query", "")
        profile = step.parameters.get("profile", "")
        return _fast("win_browser_search", {"browser": parsed.target_application, "profile": profile, "query": query}, f"Searching for '{query}' in {parsed.target_application}", RouteType.WINDOWS)

    if parsed.primary_intent == "application_workflow":
        if parsed.target_application == "Calculator":
            step = parsed.workflow_steps[1]
            expr = step.parameters.get("expression", "")
            return _fast_multi([
                ToolCall("win_open_application", {"app_name": "calculator"}, "Opening Calculator"),
                ToolCall("keyboard_type", {"text": expr + "\n"}, f"Calculating {expr}")
            ], route_type=RouteType.APPLICATION)
        
        # Build a structured representation to pass to the agent or workflow executor
        import json
        structure = {
            "workflow_type": parsed.primary_intent,
            "application": parsed.target_application,
            "environment": parsed.environment,
            "steps": [
                {
                    "action": s.action,
                    "target": s.target,
                    "parameters": s.parameters,
                    "raw_text": s.raw_text
                } for s in parsed.workflow_steps
            ]
        }
        
        return RouteResult(RouteType.AGENT, label="COMPOUND_WORKFLOW", text=json.dumps(structure))

    # Browser workflows etc go to Agent
    import json
    structure = {
        "workflow_type": parsed.primary_intent,
        "application": parsed.target_application,
        "website": parsed.target_website,
        "steps": [
            {
                "action": s.action,
                "target": s.target,
                "parameters": s.parameters,
                "raw_text": s.raw_text
            } for s in parsed.workflow_steps
        ]
    }
    return RouteResult(RouteType.AGENT, label="COMPOUND_WORKFLOW", text=json.dumps(structure))

def _try_unsupported_actions(cmd: str) -> Optional[RouteResult]:
    # System modes
    if re.match(r"^(?:switch|change|set)\s+(?:to\s+)?(?:performance|battery|power saving|balanced)\s+mode[\s.!]*$", cmd, re.IGNORECASE):
        return RouteResult(RouteType.AGENT, label="Windows workflow")
    
    # Discord actions that are unsupported
    if "discord" in cmd.lower() and ("join" in cmd.lower() or "call" in cmd.lower() or "camera" in cmd.lower() or "mute" in cmd.lower() or "server" in cmd.lower()):
        return RouteResult(RouteType.AGENT, label="Desktop workflow")
        
    return None

def _try_browser_advanced(cmd: str) -> Optional[RouteResult]:
    # 'open brave in default and search hotstar'
    m = re.match(r"^(?:open|launch)\s+(brave|chrome|firefox|edge|browser)(?:\s+in\s+([a-zA-Z0-9_]+)(?:\s+profile)?)?\s+and\s+search\s+(.+)$", cmd, re.IGNORECASE)
    if m:
        browser, profile, query = m.groups()
        return _fast("win_browser_search", {"browser": browser, "profile": profile or "default", "query": query}, f"Opening {browser.title()} to search '{query}'", RouteType.WINDOWS)
        
    # 'search hotstar in brave' or 'search github in brave in default'
    m = re.match(r"^search\s+(.+?)\s+in\s+(brave|chrome|firefox|edge|browser)(?:\s+(?:in|with)\s+([a-zA-Z0-9_]+)(?:\s+profile)?)?[\s.!]*$", cmd, re.IGNORECASE)
    if m:
        query, browser, profile = m.groups()
        return _fast("win_browser_search", {"browser": browser, "profile": profile or "default", "query": query}, f"Searching '{query}' in {browser.title()}", RouteType.WINDOWS)
        
    return None

def _try_system_control(cmd: str) -> Optional[RouteResult]:
    """'turn on wifi', 'turn off bluetooth', 'open quick settings', 'connect to Network123'"""
    # Wifi
    if re.match(r"^(?:turn|switch)\s+(?:on|off)\s+wi-?fi[\s.!]*$", cmd, re.IGNORECASE) or \
       re.match(r"^(?:enable|disable)\s+wi-?fi[\s.!]*$", cmd, re.IGNORECASE):
        if "on" in cmd.lower() or "enable" in cmd.lower():
            return _fast("sys_wifi_enable", {}, "Enabling Wi-Fi")
        else:
            return _fast("sys_wifi_disable", {}, "Disabling Wi-Fi")
            
    m = re.match(r"^connect\s+(?:to\s+)?(?:wi-?fi\s+)?(?:network\s+)?(.+)[\s.!]*$", cmd, re.IGNORECASE)
    if m and not "bluetooth" in cmd.lower():
        ssid = m.group(1).strip()
        return _fast("sys_wifi_connect", {"ssid": ssid}, f"Connecting to Wi-Fi {ssid}")

    # Bluetooth
    if re.match(r"^(?:turn|switch)\s+(?:on|off)\s+bluetooth[\s.!]*$", cmd, re.IGNORECASE) or \
       re.match(r"^(?:enable|disable)\s+bluetooth[\s.!]*$", cmd, re.IGNORECASE):
        if "on" in cmd.lower() or "enable" in cmd.lower():
            return _fast("sys_bluetooth_enable", {}, "Enabling Bluetooth")
        else:
            return _fast("sys_bluetooth_disable", {}, "Disabling Bluetooth")

    m = re.match(r"^connect\s+(?:my\s+|the\s+)?(?:bluetooth\s+)?device\s+(.+)[\s.!]*$", cmd, re.IGNORECASE)
    if not m:
        m = re.match(r"^connect\s+(?:my\s+|the\s+)?(.+)[\s.!]*$", cmd, re.IGNORECASE)
        # Avoid conflicting with wifi
        if m and "wifi" not in cmd.lower():
            dev = m.group(1).strip()
            return _fast("sys_bluetooth_connect", {"device_name": dev}, f"Connecting to Bluetooth device {dev}")

    # Airplane mode
    if re.match(r"^(?:turn|switch)\s+(?:on|off)\s+airplane\s+mode[\s.!]*$", cmd, re.IGNORECASE) or \
       re.match(r"^(?:enable|disable)\s+airplane\s+mode[\s.!]*$", cmd, re.IGNORECASE):
        if "on" in cmd.lower() or "enable" in cmd.lower():
            return _fast("sys_airplane_mode_enable", {}, "Enabling Airplane Mode")
        else:
            return _fast("sys_airplane_mode_disable", {}, "Disabling Airplane Mode")

    # Energy saver
    if re.match(r"^(?:turn|switch)\s+(?:on|off)\s+(?:energy|power)\s+saver[\s.!]*$", cmd, re.IGNORECASE) or \
       re.match(r"^(?:enable|disable)\s+(?:energy|power)\s+saver[\s.!]*$", cmd, re.IGNORECASE):
        if "on" in cmd.lower() or "enable" in cmd.lower():
            return _fast("sys_energy_saver_enable", {}, "Enabling Energy Saver")
        else:
            return _fast("sys_energy_saver_disable", {}, "Disabling Energy Saver")

    # Audio Output
    m = re.match(r"^(?:switch|change|set)\s+(?:audio|output|sound|playback)\s+(?:to\s+)?(.+)[\s.!]*$", cmd, re.IGNORECASE)
    if m:
        dev = m.group(1).strip()
        return _fast("sys_audio_output_set", {"device_name": dev}, f"Switching audio to {dev}")

    # Menus
    if re.match(r"^open\s+quick\s+settings[\s.!]*$", cmd, re.IGNORECASE):
        return _fast("sys_quick_settings_open", {}, "Opening Quick Settings")
    if re.match(r"^open\s+(?:accessibility|ease of access)[\s.!]*$", cmd, re.IGNORECASE):
        return _fast("sys_accessibility_open", {}, "Opening Accessibility Settings")

    return None

_CHAIN = [
    # 0. Unsupported actions
    _try_unsupported_actions,
    
    # 1. memory/preference/ingestion
    _try_memory,
    _try_document_ingestion,
    
    # 2. Advanced workflows/browsers (MUST be before filesystem)
    _try_compound_workflow,
    _try_browser_advanced,
    _try_open_and_type,
    _try_open_app,
    _try_close_app,
    
    # 3. browser routes (Check for sites before filesystem catches them as folders)
    _try_browser_search_and_play,
    _try_youtube_music,
    _try_youtube,
    _try_open_site,
    _try_search,
    
    # 4. filesystem
    _try_filesystem,
    
    # 5. local media
    _try_local_media,
    
    # 6. Windows/system
    _try_system_control,
    _try_lock,
    _try_settings,
    _try_brightness,
    _try_volume,
    _try_power,
    
    # 7. automation/scheduler
    _try_schedule,
    
    # 8. simple deterministic
    _try_information_question,
    _try_system_info,
    
    # Conversational shortcuts
    _try_chat,
    _try_conversation,
]

def route(command: str, explicit_account: Optional[str] = None) -> RouteResult:
    """
    Classify and route a user command.
    Returns a RouteResult — never raises.
    Caller is responsible for executing the route.
    """
    # Preserve literal URLs before normalization changes case-sensitive paths
    # and query values. A simple navigation needs no model request.
    literal_url = re.fullmatch(
        r"(?:open|go\s+to|visit|browse|navigate\s+to)\s+(https?://\S+)(?:\s+in\s+browser)?",
        command.strip(), re.IGNORECASE)
    if literal_url:
        return _browser("browser_open", {"url": literal_url.group(1)}, "Opening website")

    # Use Phase 1 CommandNormalizer
    command = CommandNormalizer.normalize(command)
    
    result = None
    for recogniser in _CHAIN:
        res = recogniser(command)
        if res is not None:
            result = res
            break
            
    if not result:
        # Nothing matched: let the agent decide
        result = RouteResult(RouteType.AGENT)
        
    if explicit_account and result.route_type == RouteType.TASK:
        result.tool_args["account_override"] = explicit_account
        
    return result
