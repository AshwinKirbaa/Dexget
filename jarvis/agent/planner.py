"""
Planner: turns a user goal into a plan, and (via the executor) the plan
into one structured tool call at a time.

Strictly validates LLM JSON output against the tool schemas (per spec 15 & 16).
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from jarvis.agent.prompts import build_next_action_prompt, build_plan_prompt
from jarvis.agent.task_state import TaskState

LLMFn = Callable[[str], Optional[str]]


class PlanParseError(Exception):
    pass


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def make_plan(goal: str, tool_specs: List[dict], llm_fn: LLMFn) -> List[str]:
    """Ask the LLM for a plain-English step list. Falls back to a single
    generic step if the LLM is unavailable or returns nothing usable."""
    prompt = build_plan_prompt(goal, tool_specs)
    raw = llm_fn(prompt) if llm_fn else None
    if not raw or not raw.strip():
        return [goal]

    lines = []
    for line in raw.splitlines():
        line = line.strip(" -*\t")
        line = re.sub(r"^\d+[.)]\s*", "", line)
        if line:
            lines.append(line)
    return lines or [goal]


def parse_next_action(raw: str, tool_specs: List[dict]) -> Dict[str, Any]:
    """
    Parse the executor LLM's JSON response robustly AND strictly validate it
    against the actual tool schemas.
    """
    if not raw:
        raise PlanParseError("empty LLM response")
    text = _strip_code_fences(raw)

    # Try direct parse first, then fall back to extracting the first {...} block.
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise PlanParseError(f"could not find JSON object in: {raw!r}")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise PlanParseError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise PlanParseError("JSON must be an object")

    if "action" not in data:
        raise PlanParseError(f"response missing 'action' field: {data!r}")
    
    action = data["action"]
    params = data.get("parameters", {})
    
    if not isinstance(params, dict):
        raise PlanParseError(f"'parameters' must be an object, got {type(params).__name__}")
        
    data.setdefault("parameters", {})
    data.setdefault("thought", "")
    data.setdefault("final_message", "")
    
    # ---------------------------------------------------------
    # Schema validation (Spec requirement 15 & 16)
    # ---------------------------------------------------------
    special_actions = {"TASK_COMPLETE", "TASK_FAILED", "USER_CONFIRMATION_REQUIRED"}
    if action in special_actions:
        return data
        
    # Find tool spec
    spec = next((t for t in tool_specs if t["name"] == action), None)
    if not spec:
        raise PlanParseError(f"unknown tool: '{action}'. Available: {[t['name'] for t in tool_specs]}")
        
    # Validate required parameters and types
    tool_params = spec.get("parameters", {})
    for p_name, p_spec in tool_params.items():
        if p_spec.get("required", False) and p_name not in params:
            raise PlanParseError(f"tool '{action}' is missing required parameter '{p_name}'")
            
    # Validate unknown parameters
    unknown = set(params.keys()) - set(tool_params.keys())
    if unknown:
        raise PlanParseError(f"tool '{action}' does not accept parameters: {sorted(unknown)}")
        
    return data


def next_action(task_state: TaskState, tool_specs: List[dict], llm_fn: LLMFn) -> Dict[str, Any]:
    """
    Ask the LLM which single tool call to make next. Raises PlanParseError
    on unparseable output or schema validation failure so the executor
    can retry/recover rather than crashing.
    """
    prompt = build_next_action_prompt(task_state, tool_specs)
    raw = llm_fn(prompt) if llm_fn else None
    if raw is None:
        raise PlanParseError("LLM unavailable")
    
    data = parse_next_action(raw, tool_specs)
    action = data.get("action")
    
    # Environment Validation (e.g. Reject: Notepad + browser_type)
    spec = next((t for t in tool_specs if t["name"] == action), None)
    if spec and task_state.tool_history:
        last_tool = task_state.tool_history[-1]
        last_spec = next((t for t in tool_specs if t["name"] == last_tool), None)
        if last_spec:
            last_cat = last_spec.get("category", "")
            curr_cat = spec.get("category", "")
            
            # If we just opened a windows app, don't immediately use a browser tool
            if last_cat == "windows" and curr_cat == "browser" and "open_application" in last_tool:
                raise PlanParseError(f"Context mismatch: cannot use browser tool '{action}' immediately after desktop tool '{last_tool}'")
                
            # If we are locked, don't use filesystem tools
            if "lock" in last_tool and curr_cat == "filesystem":
                raise PlanParseError(f"Context mismatch: cannot use filesystem tool '{action}' while system is locked")

    return data
