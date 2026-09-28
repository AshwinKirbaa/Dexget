"""
Top-level Agent: the single entry point voice, text, and terminal all
call into (per spec section 15 - "the same agent must work regardless of
whether the command originated from voice or text").

Routing:
  1. If a `fast_path_fn` is supplied (your existing detect_task/execute_task
     regex handlers) and it recognizes the command, use it directly - no
     need to burn an LLM call planning "open chrome".
  2. Otherwise, treat the input as a goal for the full agent loop
     (plan -> tool calls -> observe -> verify -> replan -> complete).
  3. If there's no LLM configured at all, fall back to the fast path only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from jarvis.agent.executor import Executor, ExecutorConfig, ExecutionOutcome
from jarvis.agent.planner import LLMFn
from jarvis.agent.task_state import TaskStatus
from jarvis.agent.tool_registry import ToolRegistry

FastPathFn = Callable[[str], Optional[str]]  # e.g. legacy run_pipeline-style handler


@dataclass
class AgentResponse:
    text: str
    used_agent_loop: bool
    outcome: Optional[ExecutionOutcome] = None


class Agent:
    def __init__(self, registry: ToolRegistry, llm_fn: Optional[LLMFn] = None,
                 fast_path_fn: Optional[FastPathFn] = None,
                 config: Optional[ExecutorConfig] = None,
                 on_progress: Optional[Callable[[str], None]] = None):
        self.registry = registry
        self.llm_fn = llm_fn
        self.fast_path_fn = fast_path_fn
        self.executor = Executor(registry, llm_fn, config=config, on_progress=on_progress)

    def handle(self, user_input: str) -> AgentResponse:
        user_input = (user_input or "").strip()
        if not user_input:
            return AgentResponse(text="I didn't catch a command.", used_agent_loop=False)

        if self.fast_path_fn is not None:
            fast_result = self.fast_path_fn(user_input)
            if fast_result:
                return AgentResponse(text=fast_result, used_agent_loop=False)

        if self.llm_fn is None:
            return AgentResponse(
                text="I don't have a language model configured, so I can only "
                     "handle direct commands right now.",
                used_agent_loop=False,
            )

        outcome = self.executor.run(user_input)
        return AgentResponse(text=outcome.final_message, used_agent_loop=True, outcome=outcome)
