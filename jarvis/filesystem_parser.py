import re
import os
import string
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class FilesystemIntent:
    intent: str
    target_name: Optional[str]
    target_type: str  # "DIRECTORY", "FILE", "DRIVE", "UNSPECIFIED"
    location: Optional[str] # usually an absolute path or drive letter
    location_type: str # "DRIVE", "DIRECTORY", "UNSPECIFIED"
    action: str

def get_available_drives() -> List[str]:
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]

def parse_filesystem_command(cmd: str) -> Optional[FilesystemIntent]:
    """Parse natural language filesystem commands."""
    cmd_clean = cmd.strip()
    
    # Check if it's a basic action
    action_match = re.match(r"^(open|go\s+to|list|search|find|create|make|mkdir|delete|remove|move|copy)\s+(.+)$", cmd_clean, re.IGNORECASE)
    if not action_match:
        # Check for pure path like "open D:\Anime"
        if re.match(r"^[a-zA-Z]:\\.*", cmd_clean):
            return FilesystemIntent(
                intent="FILESYSTEM_OPEN", target_name=os.path.basename(cmd_clean),
                target_type="UNSPECIFIED", location=os.path.dirname(cmd_clean) + "\\", location_type="DIRECTORY", action="open"
            )
        return None
        
    action_raw = action_match.group(1).lower()
    rest = action_match.group(2).strip()
    
    # Normalize action
    action = action_raw
    if action in ["go to"]: action = "open"
    if action in ["make", "mkdir"]: action = "create"
    if action in ["remove"]: action = "delete"
    
    intent_map = {
        "open": "FILESYSTEM_OPEN",
        "search": "FILESYSTEM_SEARCH",
        "find": "FILESYSTEM_SEARCH",
        "list": "FILESYSTEM_LIST",
        "create": "FILESYSTEM_CREATE",
        "delete": "FILESYSTEM_DELETE",
        "move": "FILESYSTEM_MOVE",
        "copy": "FILESYSTEM_COPY"
    }
    intent = intent_map.get(action, "FILESYSTEM_OPEN")
    
    # Check for direct drive access: "open D drive" or "go to D:"
    drive_match = re.match(r"^(?:the\s+)?(?:local\s+disk\s+|drive\s+)?([a-z])(?:[:\\]+)?(?:\s+drive)?$", rest, re.IGNORECASE)
    if drive_match:
        drive = drive_match.group(1).upper() + ":\\"
        if action == "open":
            final_intent = "DRIVE_OPEN"
        else:
            final_intent = intent
            
        return FilesystemIntent(
            intent=final_intent,
            target_name=None, target_type="DRIVE",
            location=drive, location_type="DRIVE",
            action=action
        )
        
    # Check for "in", "on", "inside", "at"
    # Example: "anime folder in D drive"
    loc_match = re.search(r"\s+(in|on|inside|at)\s+(.+)$", rest, re.IGNORECASE)
    location = None
    location_type = "UNSPECIFIED"
    target_raw = rest
    
    if loc_match:
        target_raw = rest[:loc_match.start()].strip()
        loc_str = loc_match.group(2).strip()
        
        # Parse location
        # Check for drive
        drive_m = re.match(r"^(?:the\s+)?(?:local\s+disk\s+|drive\s+)?([a-z])(?:[:\\]+)?(?:\s+drive)?$", loc_str, re.IGNORECASE)
        if drive_m:
            location = drive_m.group(1).upper() + ":\\"
            location_type = "DRIVE"
        elif re.match(r"^[a-zA-Z]:\\", loc_str):
            location = loc_str
            if not location.endswith("\\"): location += "\\"
            location_type = "DIRECTORY"
        else:
            # Maybe it's a special folder like Desktop, Documents etc.
            # We'll resolve it later
            location = loc_str
            location_type = "DIRECTORY"
            
    # Parse target
    target_type = "UNSPECIFIED"
    target_name = target_raw
    
    def clean_target_name(tname: str) -> str:
        tname = tname.strip()
        while True:
            if tname.lower().startswith("the "):
                tname = tname[4:].strip()
            elif tname.lower().startswith("a "):
                tname = tname[2:].strip()
            elif tname.lower().startswith("new "):
                tname = tname[4:].strip()
            else:
                break
        return tname

    # Check if target_raw is an absolute path
    if re.match(r"^[a-zA-Z]:\\[^\\]", target_raw):
        # Target is something like D:\Anime
        target_name = os.path.basename(target_raw)
        location = os.path.dirname(target_raw)
        if not location.endswith("\\"): location += "\\"
        location_type = "DIRECTORY"
    else:
        # Clean up "the ... folder", "folder named ...", etc.
        if re.match(r"^(?:the\s+|a\s+)?(?:folder|directory)\s+(?:named|called)\s+['\"]?(.+?)['\"]?$", target_raw, re.IGNORECASE):
            target_name = re.match(r"^(?:the\s+|a\s+)?(?:folder|directory)\s+(?:named|called)\s+['\"]?(.+?)['\"]?$", target_raw, re.IGNORECASE).group(1)
            target_type = "DIRECTORY"
        elif re.match(r"^(?:the\s+|a\s+)?(?:folder|directory)\s+['\"]?(.+?)['\"]?$", target_raw, re.IGNORECASE):
            target_name = re.match(r"^(?:the\s+|a\s+)?(?:folder|directory)\s+['\"]?(.+?)['\"]?$", target_raw, re.IGNORECASE).group(1)
            target_type = "DIRECTORY"
        elif target_raw.lower().endswith(" folder"):
            target_name = target_raw[:-7]
            target_type = "DIRECTORY"
        elif target_raw.lower().endswith(" directory"):
            target_name = target_raw[:-10]
            target_type = "DIRECTORY"
        elif target_raw.lower().endswith(" file"):
            target_name = target_raw[:-5]
            target_type = "FILE"
        else:
            # Guess based on extension
            if re.search(r"\.[a-zA-Z0-9]{2,4}$", target_name):
                target_type = "FILE"
                
        target_name = clean_target_name(target_name)
        
    # If the user just said "open calculator", is it explicit?
    if intent == "FILESYSTEM_OPEN" and target_type == "UNSPECIFIED" and location_type == "UNSPECIFIED":
        # It's not explicitly a filesystem command. Don't claim it.
        return None
        
    return FilesystemIntent(
        intent=intent,
        target_name=target_name,
        target_type=target_type,
        location=location,
        location_type=location_type,
        action=action
    )
