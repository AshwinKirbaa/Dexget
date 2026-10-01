"""
Observation layer. After a tool runs, this turns the raw ToolResult into
the natural-language observation text stored in TaskState, and (for
screen/browser tools) can attach a follow-up screenshot/DOM check. Kept
deliberately thin: most tools already produce a good `observation`
string themselves; this module exists as the single place to enrich or
post-process that text before it goes into the agent's context.
"""
from __future__ import annotations

from jarvis.tools.base import ToolResult
import json


def observe(tool_name: str, result: ToolResult) -> str:
    prefix = "OK" if result.success else "FAILED"
    text = result.observation or (str(result.output) if result.success else str(result.error))
    if result.output is not None:
        data = json.dumps(result.output, ensure_ascii=False, default=str)
        if data not in text:
            text += f"\nTool data: {data}"
    return f"[{prefix}] {tool_name}: {text[:16000]}"
