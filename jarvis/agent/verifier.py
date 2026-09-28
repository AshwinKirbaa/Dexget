"""
Verification layer. For actions that make a specific, checkable claim
(a file was created, a folder now exists) we double-check reality
instead of trusting the tool's self-reported success blindly. This is
what lets the agent notice "the click didn't actually do anything" style
failures instead of barrelling ahead.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from jarvis.tools.base import ToolResult

# Tools whose success we can independently verify by checking the filesystem.
_PATH_CHECK_TOOLS = {
    "fs_create_file": "path",
    "fs_write_file": "path",
    "fs_create_directory": "path",
    "fs_copy_file": "destination",
    "fs_move_file": "destination",
}


def verify(tool_name: str, parameters: Dict[str, Any], result: ToolResult) -> Optional[str]:
    """
    Returns None if verification passed or doesn't apply to this tool.
    Returns a human-readable problem description if verification failed,
    so the executor can treat a "successful" tool call as actually failed.
    """
    if not result.success:
        return None  # already failed, nothing extra to verify

    path_param = _PATH_CHECK_TOOLS.get(tool_name)
    if path_param:
        path = parameters.get(path_param)
        if path and not os.path.exists(path):
            return f"Tool reported success but '{path}' does not exist on disk."

    if tool_name == "fs_delete_file":
        path = parameters.get("path")
        if path and os.path.exists(path):
            return f"Tool reported deletion but '{path}' still exists."

    return None
