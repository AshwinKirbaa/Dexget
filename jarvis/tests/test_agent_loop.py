import json
import os
import shutil
import tempfile
import unittest

from jarvis.agent.agent import Agent
from jarvis.agent.executor import Executor, ExecutorConfig
from jarvis.agent.tool_registry import build_default_registry
from jarvis.security.confirmation import always_allow_confirm_fn
from jarvis.tools import filesystem as fs_tools


class ScriptedLLM:
    """Feeds back pre-scripted responses in order; records every prompt it saw."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts_seen = []

    def __call__(self, prompt: str):
        self.prompts_seen.append(prompt)
        if not self.responses:
            return json.dumps({"action": "TASK_FAILED", "final_message": "ran out of script"})
        return self.responses.pop(0)


class ExecutorAgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jarvis_agent_test_")
        fs_tools.ALLOWED_ROOTS = [self.tmp]
        self.registry = build_default_registry(confirm_fn=always_allow_confirm_fn())

    def tearDown(self):
        fs_tools.ALLOWED_ROOTS = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_multi_step_create_folder_then_file_then_complete(self):
        """Mirrors acceptance Test 1+2 from the spec: create folder, create
        file inside it with content, verify, report completion."""
        folder = os.path.join(self.tmp, "TestAI")
        filepath = os.path.join(folder, "test.txt")

        llm = ScriptedLLM([
            "Create folder\nCreate file with content\nVerify",  # plan
            json.dumps({"thought": "make folder", "action": "fs_create_directory",
                        "parameters": {"path": folder}}),
            json.dumps({"thought": "write file", "action": "fs_create_file",
                        "parameters": {"path": filepath, "content": "Hello JARVIS"}}),
            json.dumps({"thought": "done", "action": "TASK_COMPLETE",
                        "final_message": "Created TestAI/test.txt with the requested content."}),
        ])

        executor = Executor(self.registry, llm_fn=llm, config=ExecutorConfig(max_steps=10))
        outcome = executor.run(f"Create a folder called TestAI and put test.txt with 'Hello JARVIS' inside it")

        self.assertEqual(outcome.status.value, "completed")
        self.assertTrue(os.path.isdir(folder))
        self.assertTrue(os.path.isfile(filepath))
        with open(filepath) as f:
            self.assertEqual(f.read(), "Hello JARVIS")
        self.assertEqual(len(outcome.task_state.completed_steps), 2)

    def test_hallucinated_tool_name_does_not_crash_and_is_recorded_as_failed(self):
        llm = ScriptedLLM([
            "Do the thing",
            json.dumps({"action": "totally_made_up_tool", "parameters": {}}),
            json.dumps({"action": "TASK_FAILED", "final_message": "gave up"}),
        ])
        executor = Executor(self.registry, llm_fn=llm)
        outcome = executor.run("do something impossible")
        self.assertEqual(outcome.status.value, "failed")
        self.assertEqual(outcome.task_state.failed_steps[0].error, "parse_error")

    def test_repeated_identical_failure_triggers_give_up_instead_of_infinite_loop(self):
        bad_call = json.dumps({"action": "fs_read_file", "parameters": {"path": "/nope/does/not/exist.txt"}})
        llm = ScriptedLLM(["single step"] + [bad_call] * 10)
        executor = Executor(self.registry, llm_fn=llm, config=ExecutorConfig(max_steps=30, max_retries_per_action=3))
        outcome = executor.run("read a file that will never exist")
        self.assertEqual(outcome.status.value, "failed")
        self.assertIn("Gave up after", outcome.final_message)
        # Must have stopped well before the 30-step ceiling, proving the
        # same-failure-signature circuit breaker fired, not the step cap.
        total_steps = len(outcome.task_state.completed_steps) + len(outcome.task_state.failed_steps)
        self.assertLessEqual(total_steps, 3)

    def test_max_step_limit_is_enforced(self):
        # Every response is a valid-but-non-terminal action, so the loop
        # must be stopped by the step cap, not run forever.
        step = json.dumps({"action": "fs_list_directory", "parameters": {"path": self.tmp}})
        llm = ScriptedLLM(["plan"] + [step] * 100)
        executor = Executor(self.registry, llm_fn=llm, config=ExecutorConfig(max_steps=5, max_retries_per_action=999))
        outcome = executor.run("list the directory forever")
        self.assertEqual(outcome.status.value, "failed")
        self.assertIn("maximum of 5 steps", outcome.final_message)

    def test_verifier_catches_false_positive_success(self):
        """A tool that *claims* success creating a file it never actually
        wrote must be caught by the verifier, not trusted blindly."""
        from jarvis.tools.base import RiskLevel, Tool, ToolResult

        def lying_create_file(path):
            return ToolResult(True, output=path, observation="pretend I created it")

        self.registry.unregister("fs_create_file")
        self.registry.register(Tool(
            "fs_create_file", "lying version for test", {"path": {"type": "str", "required": True}},
            RiskLevel.LOW, lying_create_file))

        bogus_path = os.path.join(self.tmp, "never_actually_written.txt")
        llm = ScriptedLLM([
            "plan",
            json.dumps({"action": "fs_create_file", "parameters": {"path": bogus_path}}),
            json.dumps({"action": "TASK_FAILED", "final_message": "should not have completed"}),
        ])
        executor = Executor(self.registry, llm_fn=llm)
        outcome = executor.run("create a file")
        self.assertFalse(outcome.task_state.completed_steps and
                          outcome.task_state.completed_steps[0].success)
        self.assertIn("VERIFICATION FAILED", outcome.task_state.observations[0])

    def test_user_confirmation_required_short_circuits_loop(self):
        llm = ScriptedLLM([
            "plan",
            json.dumps({"action": "USER_CONFIRMATION_REQUIRED",
                        "final_message": "Which file did you mean?"}),
        ])
        executor = Executor(self.registry, llm_fn=llm)
        outcome = executor.run("delete the file")
        self.assertEqual(outcome.status.value, "needs_confirmation")
        self.assertIn("Which file", outcome.final_message)


class AgentFastPathTests(unittest.TestCase):
    def test_fast_path_short_circuits_llm(self):
        registry = build_default_registry(confirm_fn=always_allow_confirm_fn())
        llm_calls = []

        def llm(prompt):
            llm_calls.append(prompt)
            return json.dumps({"action": "TASK_COMPLETE", "final_message": "should not reach here"})

        def fast_path(cmd):
            if cmd == "what time is it":
                return "It is 3:00 PM."
            return None

        agent = Agent(registry, llm_fn=llm, fast_path_fn=fast_path)
        response = agent.handle("what time is it")
        self.assertFalse(response.used_agent_loop)
        self.assertEqual(response.text, "It is 3:00 PM.")
        self.assertEqual(llm_calls, [])  # LLM must not have been invoked at all

    def test_falls_through_to_agent_loop_when_fast_path_misses(self):
        registry = build_default_registry(confirm_fn=always_allow_confirm_fn())
        llm = ScriptedLLM([
            "plan",
            json.dumps({"action": "TASK_COMPLETE", "final_message": "handled by agent loop"}),
        ])
        agent = Agent(registry, llm_fn=llm, fast_path_fn=lambda cmd: None)
        response = agent.handle("do something novel and multi-step")
        self.assertTrue(response.used_agent_loop)
        self.assertEqual(response.text, "handled by agent loop")

    def test_no_llm_configured_falls_back_gracefully(self):
        registry = build_default_registry(confirm_fn=always_allow_confirm_fn())
        agent = Agent(registry, llm_fn=None, fast_path_fn=lambda cmd: None)
        response = agent.handle("anything")
        self.assertFalse(response.used_agent_loop)
        self.assertIn("don't have a language model", response.text)


if __name__ == "__main__":
    unittest.main()
