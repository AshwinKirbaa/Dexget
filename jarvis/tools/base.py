"""
Core Tool abstraction used by every capability in the agent.

Design rules (from the project spec):
  - The LLM never executes arbitrary Python. It only ever emits a
    structured {"action": <tool name>, "parameters": {...}} call.
  - Every tool declares a risk_level so the security layer can decide
    whether user confirmation is required before it runs.
  - execute() never raises: failures come back as a ToolResult so the
    agent loop can observe/recover instead of crashing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional
import time
import inspect


def validate_parameters(schema: Dict[str, dict], values: Dict[str, Any]) -> Optional[str]:
    types = {"str": str, "int": int, "float": (int, float), "bool": bool,
             "list": list, "dict": dict}
    for name, spec in schema.items():
        if spec.get("required") and name not in values:
            return f"Missing required parameter '{name}'"
        if name in values:
            value = values[name]
            expected = types.get(spec.get("type", "str"))
            if value is None and not spec.get("required"):
                continue
            if expected and (not isinstance(value, expected) or
                             (isinstance(value, bool) and spec.get("type") in ("int", "float"))):
                return f"Parameter '{name}' must have type {spec.get('type', 'str')}"
    unknown = set(values) - set(schema)
    if unknown:
        return f"Unknown parameter(s) {sorted(unknown)}"
    return None


def parameter_json_schema(parameters):
    """Convert registry metadata to a standard JSON Schema for local decoding."""
    types = {"str": "string", "int": "integer", "float": "number",
             "bool": "boolean", "list": "array", "dict": "object"}
    properties = {}
    for name, metadata in parameters.items():
        entry = {"type": types.get(metadata.get("type", "str"), "string")}
        if "default" in metadata:
            entry["default"] = metadata["default"]
            if metadata["default"] is None:
                entry["type"] = [entry["type"], "null"]
        if metadata.get("description"):
            entry["description"] = metadata["description"]
        properties[name] = entry
    return {"type": "object", "properties": properties,
            "required": [k for k, v in parameters.items() if v.get("required")],
            "additionalProperties": False}


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"

    @property
    def requires_confirmation(self) -> bool:
        return self in (RiskLevel.HIGH, RiskLevel.DESTRUCTIVE)


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    # A short natural-language observation the agent can reason over
    # (e.g. "File created at C:\\Users\\...\\test.txt (42 bytes)").
    observation: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "observation": self.observation,
            "duration_seconds": round(self.duration_seconds, 3),
        }


@dataclass
class Tool:
    name: str
    description: str
    # JSON-schema-ish dict: {"param_name": {"type": "str", "required": True, "description": "..."}}
    parameters: Dict[str, Dict[str, Any]]
    risk_level: RiskLevel
    func: Callable[..., ToolResult]
    # Optional: restrict which broad category this belongs to, useful for
    # tool-selection prompts (browser / filesystem / desktop / system / ...)
    category: str = "general"

    def validate(self, kwargs: Dict[str, Any]) -> Optional[str]:
        """Return an error string if kwargs don't satisfy the schema, else None."""
        return validate_parameters(self.parameters, kwargs)

    def execute(self, **kwargs) -> ToolResult:
        error = self.validate(kwargs)
        if error:
            return ToolResult(success=False, error=error, observation=error)
        start = time.time()
        try:
            result = self.func(**kwargs)
            if not isinstance(result, ToolResult):
                # Be forgiving: allow tool funcs to return plain values.
                result = ToolResult(success=True, output=result, observation=str(result))
        except Exception as exc:  # noqa: BLE001 - tools must never crash the agent
            result = ToolResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                observation=f"Tool '{self.name}' raised {type(exc).__name__}: {exc}",
            )
        result.duration_seconds = time.time() - start
        return result

    def spec(self) -> Dict[str, Any]:
        """Compact description handed to the LLM for tool selection."""
        defaults = {}
        try:
            defaults = {name: parameter.default for name, parameter in
                        inspect.signature(self.func).parameters.items()
                        if parameter.default is not inspect.Parameter.empty}
        except (TypeError, ValueError):
            pass
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                k: {"type": v.get("type", "str"), "required": v.get("required", False),
                    "description": v.get("description", ""),
                    **({"default": defaults[k]} if k in defaults else {})}
                for k, v in self.parameters.items()
            },
            "risk_level": self.risk_level.value,
            "category": self.category,
        }
