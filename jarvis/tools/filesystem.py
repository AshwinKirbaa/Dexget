"""Safe filesystem tools. All paths pass through security.permissions.sanitize_path."""
from __future__ import annotations

import os
import shutil
from typing import List, Optional

from jarvis.security.permissions import sanitize_path
from jarvis.tools.base import RiskLevel, Tool, ToolResult

# Configure allowed roots at import time from env, defaulting to the user's
# home directory so a runaway plan can't touch arbitrary system paths.
# main.py can override this via jarvis.tools.filesystem.ALLOWED_ROOTS.
ALLOWED_ROOTS: Optional[List[str]] = None  # None = allow any real path (still traversal-safe)


def _safe(path: str) -> Optional[str]:
    # Reject placeholders
    lower_path = path.lower().replace('\\', '/')
    placeholders = ['/username/', '[username]', '<username>', '{username}', '/path/to/']
    # If "username" is literally just a placeholder, e.g. C:\Users\username
    if lower_path.endswith('/username'):
        return None
    for p in placeholders:
        if p in lower_path:
            return None
    return sanitize_path(path, ALLOWED_ROOTS)


def create_file(path: str, content: str = "") -> ToolResult:
    real = _safe(path)
    if not real:
        return ToolResult(False, error="path_rejected", observation=f"Path rejected: {path}")
    if os.path.exists(real):
        return ToolResult(False, error="already_exists", observation=f"{real} already exists")
    os.makedirs(os.path.dirname(real) or ".", exist_ok=True)
    with open(real, "w", encoding="utf-8") as f:
        f.write(content)
    return ToolResult(True, output=real, observation=f"Created file {real} ({len(content)} bytes)")


def read_file(path: str) -> ToolResult:
    real = _safe(path)
    if not real or not os.path.isfile(real):
        return ToolResult(False, error="not_found", observation=f"File not found: {path}")
    with open(real, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return ToolResult(True, output=content, observation=f"Read {len(content)} chars from {real}")


def write_file(path: str, content: str = "") -> ToolResult:
    real = _safe(path)
    if not real:
        return ToolResult(False, error="path_rejected", observation=f"Path rejected: {path}")
    os.makedirs(os.path.dirname(real) or ".", exist_ok=True)
    with open(real, "w", encoding="utf-8") as f:
        f.write(content)
    return ToolResult(True, output=real, observation=f"Wrote {len(content)} bytes to {real}")


def append_file(path: str, content: str = "") -> ToolResult:
    real = _safe(path)
    if not real:
        return ToolResult(False, error="path_rejected", observation=f"Path rejected: {path}")
    if not os.path.exists(real):
        return ToolResult(False, error="not_found", observation=f"File not found: {path}")
    with open(real, "a", encoding="utf-8") as f:
        f.write(content)
    return ToolResult(True, output=real, observation=f"Appended {len(content)} bytes to {real}")


def copy_file(source: str, destination: str) -> ToolResult:
    src, dst = _safe(source), _safe(destination)
    if not src or not os.path.exists(src) or not dst:
        return ToolResult(False, error="invalid_path", observation=f"Cannot copy {source} -> {destination}")
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return ToolResult(True, output=dst, observation=f"Copied {src} to {dst}")


def move_file(source: str, destination: str) -> ToolResult:
    src, dst = _safe(source), _safe(destination)
    if not src or not os.path.exists(src) or not dst:
        return ToolResult(False, error="invalid_path", observation=f"Cannot move {source} -> {destination}")
    shutil.move(src, dst)
    return ToolResult(True, output=dst, observation=f"Moved {src} to {dst}")


def rename_file(path: str, new_name: str) -> ToolResult:
    real = _safe(path)
    if not real or not os.path.exists(real):
        return ToolResult(False, error="not_found", observation=f"Not found: {path}")
    new_path = os.path.join(os.path.dirname(real), new_name)
    os.rename(real, new_path)
    return ToolResult(True, output=new_path, observation=f"Renamed {real} to {new_path}")


def create_directory(path: str) -> ToolResult:
    real = _safe(path)
    if not real:
        return ToolResult(False, error="path_rejected", observation=f"Path rejected: {path}")
    os.makedirs(real, exist_ok=True)
    return ToolResult(True, output=real, observation=f"Created directory {real}")


def list_directory(path: str) -> ToolResult:
    real = _safe(path)
    if not real or not os.path.isdir(real):
        return ToolResult(False, error="not_found", observation=f"Directory not found: {path}")
    entries = sorted(os.listdir(real))
    return ToolResult(True, output=entries, observation=f"{len(entries)} entries in {real}: {entries[:20]}")


def search_files(root: str, name_contains: str) -> ToolResult:
    real = _safe(root)
    if not real or not os.path.isdir(real):
        return ToolResult(False, error="not_found", observation=f"Directory not found: {root}")
    matches = []
    needle = name_contains.lower()
    for dirpath, _dirs, files in os.walk(real):
        for f in files:
            if needle in f.lower():
                matches.append(os.path.join(dirpath, f))
        if len(matches) >= 200:
            break
    return ToolResult(True, output=matches, observation=f"Found {len(matches)} match(es) for '{name_contains}'")


def delete_file(path: str) -> ToolResult:
    real = _safe(path)
    if not real or not os.path.exists(real):
        return ToolResult(False, error="not_found", observation=f"Not found: {path}")
    if os.path.isdir(real):
        shutil.rmtree(real)
    else:
        os.remove(real)
    return ToolResult(True, output=real, observation=f"Deleted {real}")


def get_fs_info(query: str = "") -> ToolResult:
    # A generic tool to retrieve info about a file or directory for information queries
    # e.g., 'where is my Projects folder', 'does my tester folder exist', 'what files are in Movies'
    from jarvis.router import resolve_path
    import re
    # Try to extract the target from the query
    m = re.search(r"(?:where\s+is|does\s+(?:my\s+|the\s+)?|what\s+files\s+are\s+in\s+(?:my\s+)?|how\s+many\s+files\s+are\s+in\s+(?:my\s+)?|what\s+is\s+the\s+size\s+of\s+(?:my\s+)?|where\s+is\s+(?:my\s+|the\s+)?)(.+?)(?:\s+stored|\s*folder|\s*directory|\s*file|\s+exist|\?|$)[\s?!.]*", query, re.IGNORECASE)
    
    if m:
        target = m.group(1).strip()
    else:
        target = query.replace("where is ", "").replace("does ", "").replace(" exist", "").strip()
        
    resolved = resolve_path(target)
    if not os.path.exists(resolved):
        return ToolResult(False, error="not_found", observation=f"The path for '{target}' ({resolved}) does not exist.")
        
    info = {"path": resolved, "exists": True}
    if os.path.isdir(resolved):
        info["type"] = "directory"
        try:
            items = os.listdir(resolved)
            info["item_count"] = len(items)
            info["items"] = items[:50] # Limit to 50 items
        except Exception as e:
            info["error"] = str(e)
    else:
        info["type"] = "file"
        info["size_bytes"] = os.path.getsize(resolved)
        
    return ToolResult(True, output=info, observation=f"Information for {target} retrieved successfully.")

def register(registry) -> None:
    registry.register(Tool(
        name="fs_create_file", description="Create a new file with optional text content.",
        parameters={"path": {"type": "str", "required": True}, "content": {"type": "str"}},
        risk_level=RiskLevel.LOW, func=create_file, category="filesystem"))
    registry.register(Tool(
        name="fs_read_file", description="Read the text content of a file.",
        parameters={"path": {"type": "str", "required": True}},
        risk_level=RiskLevel.LOW, func=read_file, category="filesystem"))
    registry.register(Tool(
        name="fs_write_file", description="Overwrite a file with the given text content.",
        parameters={"path": {"type": "str", "required": True}, "content": {"type": "str"}},
        risk_level=RiskLevel.LOW, func=write_file, category="filesystem"))
    registry.register(Tool(
        name="fs_append_file", description="Append text content to an existing file.",
        parameters={"path": {"type": "str", "required": True}, "content": {"type": "str"}},
        risk_level=RiskLevel.LOW, func=append_file, category="filesystem"))
    registry.register(Tool(
        name="fs_copy_file", description="Copy a file or directory to a destination path.",
        parameters={"source": {"type": "str", "required": True}, "destination": {"type": "str", "required": True}},
        risk_level=RiskLevel.MEDIUM, func=copy_file, category="filesystem"))
    registry.register(Tool(
        name="fs_move_file", description="Move a file or directory to a destination path.",
        parameters={"source": {"type": "str", "required": True}, "destination": {"type": "str", "required": True}},
        risk_level=RiskLevel.MEDIUM, func=move_file, category="filesystem"))
    registry.register(Tool(
        name="fs_rename_file", description="Rename a file or directory in place.",
        parameters={"path": {"type": "str", "required": True}, "new_name": {"type": "str", "required": True}},
        risk_level=RiskLevel.LOW, func=rename_file, category="filesystem"))
    registry.register(Tool(
        name="fs_create_directory", description="Create a directory (and parents as needed).",
        parameters={"path": {"type": "str", "required": True}},
        risk_level=RiskLevel.LOW, func=create_directory, category="filesystem"))
    registry.register(Tool(
        name="fs_list_directory", description="List the contents of a directory.",
        parameters={"path": {"type": "str", "required": True}},
        risk_level=RiskLevel.LOW, func=list_directory, category="filesystem"))
    registry.register(Tool(
        name="fs_search_files", description="Recursively search a directory for filenames containing a substring.",
        parameters={"root": {"type": "str", "required": True}, "name_contains": {"type": "str", "required": True}},
        risk_level=RiskLevel.LOW, func=search_files, category="filesystem"))
    registry.register(Tool(
        name="fs_delete_file", description="Permanently delete a file or directory.",
        parameters={"path": {"type": "str", "required": True}},
        risk_level=RiskLevel.HIGH, func=delete_file, category="filesystem"))
    registry.register(Tool("fs_info", "Get information about a file or folder.", {"query": {"type": "str"}}, RiskLevel.LOW, get_fs_info, "filesystem"))
