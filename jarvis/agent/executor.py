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

    def _report(self, message: str) -> None:
        self.on_progress(message)

    def run(self, goal: str) -> ExecutionOutcome:
        task_state = TaskState(goal=goal, status=TaskStatus.RUNNING)
        task_state.plan = planner.make_plan(goal, self.registry.specs(), self.llm_fn)
        self._report(f"[PLAN] {len(task_state.plan)} step(s) identified")
        for i, step in enumerate(task_state.plan, 1):
            self._report(f"  {i}. {step}")

        consecutive_same_failure = 0
        last_failed_signature: Optional[str] = None

        while not task_state.is_step_limit_reached(self.config.max_steps):
            try:
                decision = planner.next_action(task_state, self.registry.specs(), self.llm_fn)
            except PlanParseError as exc:
                step_no = len(task_state.completed_steps) + len(task_state.failed_steps) + 1
                record = StepRecord(
                    index=step_no, description="Planning/Parsing Error",
                    tool="system", parameters={}, success=False,
                    observation=f"[PARSE ERROR] {exc}. Please fix the JSON and try again.",
                    error="parse_error",
                )
                task_state.record(record)
                
                # Check if we've had 3 consecutive parse errors
                parse_errors = [s.error == "parse_error" for s in task_state.failed_steps[-3:]]
                if len(parse_errors) == 3 and all(parse_errors):
                    task_state.status = TaskStatus.FAILED
                    msg = "Planning failed: 3 consecutive JSON parsing or schema validation errors."
                    self._report(f"[\u2717] {msg}")
                    return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)
                continue

            action = decision["action"]
            params = decision.get("parameters", {})
            step_no = len(task_state.completed_steps) + len(task_state.failed_steps) + 1

            if action == "TASK_COMPLETE":
                task_state.status = TaskStatus.COMPLETED
                msg = decision.get("final_message") or "Task completed."
                self._report(f"[\u2713] {msg}")
                return ExecutionOutcome(TaskStatus.COMPLETED, msg, task_state)

            if action == "TASK_FAILED":
                task_state.status = TaskStatus.FAILED
                msg = decision.get("final_message") or "Task could not be completed."
                self._report(f"[\u2717] {msg}")
                return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)

            if action == "USER_CONFIRMATION_REQUIRED":
                task_state.status = TaskStatus.NEEDS_CONFIRMATION
                msg = decision.get("final_message") or "I need more information to continue."
                return ExecutionOutcome(TaskStatus.NEEDS_CONFIRMATION, msg, task_state)

            if not self.registry.has(action):
                # The model hallucinated a tool name - treat as a failed step
                # and let the loop try again with that feedback instead of crashing.
                record = StepRecord(
                    index=step_no, description=decision.get("thought", ""),
                    tool=action, parameters=params, success=False,
                    observation=f"[FAILED] '{action}' is not a registered tool.",
                    error="unknown_tool",
                )
                task_state.record(record)
                continue

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

            # Failure-recovery bookkeeping: stop hammering the same broken
            # action forever, per the spec's retry/backoff requirement.
            signature = f"{action}:{sorted(params.items())}"
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
                    self._report(f"[\u2717] {msg}")
                    return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)
            else:
                consecutive_same_failure = 0
                last_failed_signature = None

        task_state.status = TaskStatus.FAILED
        msg = f"Reached the maximum of {self.config.max_steps} steps without completing the task."
        return ExecutionOutcome(TaskStatus.FAILED, msg, task_state)
