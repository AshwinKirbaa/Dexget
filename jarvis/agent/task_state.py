"""Task state tracked across one agent run, so it knows what it has already done."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_CONFIRMATION = "needs_confirmation"
    CANCELLED = "cancelled"


@dataclass
class StepRecord:
    index: int
    description: str
    tool: str
    parameters: Dict[str, Any]
    success: bool
    observation: str
    error: Optional[str] = None


@dataclass
class TaskState:
    goal: str
    plan: List[str] = field(default_factory=list)
    current_step: int = 0
    completed_steps: List[StepRecord] = field(default_factory=list)
    failed_steps: List[StepRecord] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    tool_history: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING

    def record(self, record: StepRecord) -> None:
        self.tool_history.append(record.tool)
        self.observations.append(record.observation)
        if record.success:
            self.completed_steps.append(record)
        else:
            self.failed_steps.append(record)

    def recent_context(self, n: int = 6) -> str:
        """Short textual summary of the last n observations, for the planner/LLM."""
        # Bound total history, including large DOM snapshots, so tool specs
        # and the user's goal remain inside a local model's context window.
        remaining = 14000
        selected = []
        for observation in reversed(self.observations[-n:]):
            if remaining <= 0:
                break
            clipped = observation[:remaining]
            selected.append(f"- {clipped}")
            remaining -= len(clipped) + 3
        return "\n".join(reversed(selected)) or "(no actions taken yet)"

    def is_step_limit_reached(self, max_steps: int) -> bool:
        return (len(self.completed_steps) + len(self.failed_steps)) >= max_steps

    def summary(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status.value,
            "plan": self.plan,
            "current_step": self.current_step,
            "completed": len(self.completed_steps),
            "failed": len(self.failed_steps),
        }
