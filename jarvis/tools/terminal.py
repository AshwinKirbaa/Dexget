"""
Controlled terminal/shell tool. The LLM never gets raw shell access - every
command passes through classify_command_risk() first, and destructive
commands are blocked from this tool entirely (they must go through a
dedicated, explicitly-confirmed tool if ever needed - not ad hoc shell text).
"""
from __future__ import annotations

import subprocess
from typing import Optional

from jarvis.security.permissions import classify_command_risk, redact_secrets
from jarvis.tools.base import RiskLevel, Tool, ToolResult

TIMEOUT_SECONDS = 20


def run_command(command: str) -> ToolResult:
    risk = classify_command_risk(command)
    if risk == "destructive":
        return ToolResult(
            False, error="blocked_destructive",
            observation=f"Refused to run destructive command via terminal tool: {redact_secrets(command)}",
        )
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
        out = redact_secrets((proc.stdout or "").strip())
        err = redact_secrets((proc.stderr or "").strip())
        success = proc.returncode == 0
        observation = f"exit={proc.returncode}"
        if out:
            observation += f" stdout={out[:400]}"
        if err:
            observation += f" stderr={err[:400]}"
        return ToolResult(success, output={"stdout": out, "stderr": err, "returncode": proc.returncode},
                           error=None if success else f"exit code {proc.returncode}", observation=observation)
    except subprocess.TimeoutExpired:
        return ToolResult(False, error="timeout", observation=f"Command timed out after {TIMEOUT_SECONDS}s")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(False, error=str(exc), observation=f"Failed to run command: {exc}")


def register(registry) -> None:
    registry.register(Tool(
        name="terminal_run", description=(
            "Run a single non-destructive shell command and return stdout/stderr. "
            "Destructive commands (delete, format, shutdown, registry edits, etc.) "
            "are refused outright by this tool."
        ),
        parameters={"command": {"type": "str", "required": True}},
        risk_level=RiskLevel.MEDIUM, func=run_command, category="terminal"))
