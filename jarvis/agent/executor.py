"""
Executor: runs the plan-execute-observe-verify-replan loop until the
task is completed, fails, or needs the user.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from jarvis.agent import planner
from jarvis.agent import observer
from jarvis.agent import verifier
from jarvis.agent.planner import LLMFn, PlanParseError
from jarvis.agent.task_state import StepRecord, TaskStatus, TaskState
from jarvis.agent.tool_registry import ToolRegistry

ProgressCallback = Callable[[str], None]  # e.g. print("[1/4] Opening browser")

_FOLLOW_UP_OBSERVATIONS = {
    **{name: "browser_observe" for name in (
        "browser_open", "browser_navigate", "browser_back", "browser_refresh",
        "browser_click", "browser_type", "browser_select", "browser_scroll")},
    **{name: "desktop_observe" for name in (
        "desktop_click", "desktop_type", "desktop_focus", "win_open_application",
        "mouse_click", "mouse_double_click", "keyboard_type", "keyboard_hotkey")},
}


@dataclass
class ExecutorConfig:
    max_steps: int = 30
    max_retries_per_action: int = 3


@dataclass
class ExecutionOutcome:
    status: TaskStatus
    final_message: str
    task_state: TaskState


class Executor:
    def __init__(self, registry: ToolRegistry, llm_fn: LLMFn,
                 config: Optional[ExecutorConfig] = None,
                 on_progress: Optional[ProgressCallback] = None):
        self.registry = registry
        self.llm_fn = llm_fn
        self.config = config or ExecutorConfig()
        self.on_progress = on_progress or (lambda msg: None)
        self.pending_task = None

    def _report(self, message: str) -> None:
        self.on_progress(message)

    def run(self, goal: str) -> ExecutionOutcome:
        task_state = self.pending_task or TaskState(goal=goal, status=TaskStatus.RUNNING)
        if self.pending_task:
            task_state.goal += f"\nUser follow-up: {goal}"
            task_state.observations.append(f"User follow-up: {goal}")
        self.pending_task = None
        task_state.status = TaskStatus.RUNNING
        categories = ["system"]
        goal_lower = task_state.goal.lower()
        if "browser" in goal_lower or "chrome" in goal_lower or "web" in goal_lower or "search" in goal_lower or "online" in goal_lower:
            categories.extend(["browser", "web_extract"])
        if "windows" in goal_lower or "application" in goal_lower or "app" in goal_lower or "click" in goal_lower or "type" in goal_lower or "open" in goal_lower:
            categories.extend(["windows", "desktop_input", "desktop_accessibility"])
        if "file" in goal_lower or "folder" in goal_lower or "directory" in goal_lower or "path" in goal_lower or "drive" in goal_lower:
            categories.extend(["filesystem"])
        if "media" in goal_lower or "music" in goal_lower or "song" in goal_lower or "play" in goal_lower:
            categories.extend(["media"])
            
        task_state.allowed_categories = list(set(categories))
        
        if not task_state.plan and not self.registry.cancel_event.is_set():
            specs = self.registry.specs(categories=task_state.allowed_categories) if task_state.allowed_categories else self.registry.specs()
            task_state.plan = planner.make_plan(goal, specs, self.llm_fn)
        self._report(f"[PLAN] {len(task_state.plan)} step(s) identified")
        for i, step in enumerate(task_state.plan, 1):
            self._report(f"  {i}. {step}")

        consecutive_same_failure = 0
        last_failed_signature: Optional[str] = None
        consecutive_parse_errors = 0

        while not task_state.is_step_limit_reached(self.config.max_steps):
            if self.registry.cancel_event.is_set():
                task_state.status = TaskStatus.CANCELLED
                return ExecutionOutcome(TaskStatus.CANCELLED, "Task stopped.", task_state)
            try:
                specs = self.registry.specs(categories=task_state.allowed_categories) if hasattr(task_state, 'allowed_categories') and task_state.allowed_categories else self.registry.specs()
                decision = planner.next_action(task_state, specs, self.llm_fn)
            except PlanParseError as exc:
                consecutive_parse_errors += 1
                step_no = len(task_state.completed_steps) + len(task_state.failed_steps) + 1
                record = StepRecord(
                    index=step_no, description="Planning/Parsing Error",
                    tool="system", parameters={}, success=False,
                    observation=f"[PARSE ERROR] {exc}. Please fix the JSON and try again.",
                    error="parse_error",
                )
                task_state.record(record)
                
                # Check if we've had 3 consecutive parse errors
                if consecutive_parse_errors >= self.config.max_retries_per_action:
                    task_state.status = TaskStatus.FAILED
                    msg = "Planning failed: 3 consecutive JSON parsing or schema validation errors."
                    self._report(f"[FAILED] {msg}")
                    return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)
                continue

            consecutive_parse_errors = 0
            if self.registry.cancel_event.is_set():
                task_state.status = TaskStatus.CANCELLED
                return ExecutionOutcome(TaskStatus.CANCELLED, "Task stopped.", task_state)
            action = decision["action"]
            params = decision.get("parameters", {})
            step_no = len(task_state.completed_steps) + len(task_state.failed_steps) + 1

            if action == "TASK_COMPLETE":
                if not task_state.completed_steps:
                    task_state.status = TaskStatus.FAILED
                    return ExecutionOutcome(TaskStatus.FAILED,
                        "No successful tool action or observation supports completion.", task_state)
                if task_state.failed_steps and (
                    not task_state.completed_steps or
                    task_state.failed_steps[-1].index > task_state.completed_steps[-1].index
                ):
                    task_state.status = TaskStatus.FAILED
                    msg = "The last action failed; completion could not be verified. " + task_state.failed_steps[-1].observation
                    return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)
                task_state.status = TaskStatus.COMPLETED
                msg = decision.get("final_message") or "Task completed."
                self._report(f"[DONE] {msg}")
                return ExecutionOutcome(TaskStatus.COMPLETED, msg, task_state)

            if action == "TASK_FAILED":
                task_state.status = TaskStatus.FAILED
                msg = decision.get("final_message") or "Task could not be completed."
                self._report(f"[FAILED] {msg}")
                return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)

            if action == "USER_CONFIRMATION_REQUIRED":
                task_state.status = TaskStatus.NEEDS_CONFIRMATION
                msg = decision.get("final_message") or "I need more information to continue."
                self.pending_task = task_state
                return ExecutionOutcome(TaskStatus.NEEDS_CONFIRMATION, msg, task_state)

            if not self.registry.has(action):
                # User Requirement 20: UNKNOWN TOOL FAILURE
                # Return immediately. Do NOT retry. The error must contain available capabilities.
                available = ", ".join(t.name for t in self.registry.list_tools(categories=task_state.allowed_categories))
                error_msg = f"[FAILED] No such tool: '{action}'. Available relevant capabilities: {available}. Task intent mapping failed."
                
                record = StepRecord(
                    index=step_no, description=decision.get("thought", ""),
                    tool=action, parameters=params, success=False,
                    observation=error_msg,
                    error="unknown_tool",
                )
                task_state.record(record)
                task_state.status = TaskStatus.FAILED
                self._report(error_msg)
                return ExecutionOutcome(TaskStatus.FAILED, error_msg, task_state)

            self._report(f"[{step_no}/{max(len(task_state.plan), step_no)}] {decision.get('thought') or action}")

            result = self.registry.execute(action, **params)
            problem = verifier.verify(action, params, result)
            if problem:
                result.success = False
                result.error = result.error or "verification_failed"
                result.observation = f"{result.observation} | VERIFICATION FAILED: {problem}"

            obs_text = observer.observe(action, result)
            record = StepRecord(
                index=step_no, description=decision.get("thought", ""),
                tool=action, parameters=params, success=result.success,
                observation=obs_text, error=result.error,
            )
            task_state.record(record)
            self._report(obs_text)
            if result.error in ("confirmation_declined", "cancelled") or self.registry.cancel_event.is_set():
                task_state.status = TaskStatus.CANCELLED
                return ExecutionOutcome(TaskStatus.CANCELLED, "Task stopped. " + result.observation, task_state)

            follow_up = _FOLLOW_UP_OBSERVATIONS.get(action)
            if (result.success and follow_up and self.registry.has(follow_up)
                    and not task_state.is_step_limit_reached(self.config.max_steps)):
                snapshot = self.registry.execute(follow_up)
                snapshot_text = observer.observe(follow_up, snapshot)
                task_state.record(StepRecord(
                    index=step_no + 1, description="Observe the result",
                    tool=follow_up, parameters={}, success=snapshot.success,
                    observation=snapshot_text, error=snapshot.error,
                ))
                self._report(snapshot_text)
                if self.registry.cancel_event.is_set():
                    task_state.status = TaskStatus.CANCELLED
                    return ExecutionOutcome(TaskStatus.CANCELLED, "Task stopped.", task_state)

            # Infinite loop detection: Repeated identical actions or observations
            signature = f"{action}:{sorted(params.items())}"
            obs_hash = hash(obs_text)
            
            if not hasattr(task_state, 'recent_history'):
                task_state.recent_history = []
            
            task_state.recent_history.append((signature, obs_hash))
            if len(task_state.recent_history) > 6:
                task_state.recent_history.pop(0)
                
            # If the last 3 steps are identical (action + observation)
            if len(task_state.recent_history) >= 3:
                last_3 = task_state.recent_history[-3:]
                if all(item == last_3[0] for item in last_3):
                    task_state.status = TaskStatus.FAILED
                    msg = f"Detected infinite loop: repeated '{action}' without state change."
                    self._report(f"[FAILED] {msg}")
                    return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)

            # Failure-recovery bookkeeping: stop hammering the same broken
            # action forever, per the spec's retry/backoff requirement.
            if not result.success:
                if signature == last_failed_signature:
                    consecutive_same_failure += 1
                else:
                    consecutive_same_failure = 1
                last_failed_signature = signature
                if consecutive_same_failure >= self.config.max_retries_per_action:
                    task_state.status = TaskStatus.FAILED
                    msg = (
                        f"Gave up after {consecutive_same_failure} failed attempts "
                        f"at '{action}' with the same arguments."
                    )
                    self._report(f"[FAILED] {msg}")
                    return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)
            else:
                consecutive_same_failure = 0
                last_failed_signature = None

        task_state.status = TaskStatus.FAILED
        msg = f"Reached the maximum of {self.config.max_steps} steps without completing the task."
        return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)
