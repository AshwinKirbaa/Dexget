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
from jarvis.tools.base import validate_parameters, parameter_json_schema

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
    if not isinstance(action, str) or not action:
        raise PlanParseError("'action' must be a nonempty string")
    params = data.get("parameters", {})
    
    if not isinstance(params, dict):
        raise PlanParseError(f"'parameters' must be an object, got {type(params).__name__}")
        
    data.setdefault("parameters", {})
    data.setdefault("thought", "")
    data.setdefault("final_message", "")
    for key in ("thought", "final_message"):
        if not isinstance(data[key], str):
            raise PlanParseError(f"'{key}' must be a string")
    
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
    error = validate_parameters(tool_params, params)
    if error:
        raise PlanParseError(f"tool '{action}': {error}")
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
    import os
    original_timeout = os.environ.get("JARVIS_MODEL_TIMEOUT")
    agent_timeout = int(os.environ.get("JARVIS_AGENT_TIMEOUT", "20"))
    os.environ["JARVIS_MODEL_TIMEOUT"] = str(agent_timeout)

    try:
        prompt = build_next_action_prompt(task_state, tool_specs)
        structured = getattr(llm_fn, "structured", None)
        if callable(structured):
            raw = structured(prompt, action_json_schema(tool_specs))
        else:
            raw = llm_fn(prompt) if llm_fn else None
        if raw is None:
            raise PlanParseError("LLM unavailable")
        
        data = parse_next_action(raw, tool_specs)
        return data
    finally:
        if original_timeout is not None:
            os.environ["JARVIS_MODEL_TIMEOUT"] = original_timeout
        else:
            del os.environ["JARVIS_MODEL_TIMEOUT"]

def action_json_schema(tool_specs):
    branches = []
    specs = list(tool_specs) + [
        {"name": name, "parameters": {}} for name in
        ("TASK_COMPLETE", "TASK_FAILED", "USER_CONFIRMATION_REQUIRED")
    ]
    for spec in specs:
        branches.append({
            "type": "object",
            "properties": {
                "action": {"const": spec["name"]},
                "parameters": parameter_json_schema(spec["parameters"]),
                "thought": {"type": "string"},
                "final_message": {"type": "string"},
            },
            "required": ["action", "parameters"],
            "additionalProperties": False,
        })
    return {"anyOf": branches}
