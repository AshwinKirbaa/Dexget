import unittest

from jarvis.tools.base import RiskLevel, Tool, ToolResult
from jarvis.agent.tool_registry import ToolRegistry, ToolNotFoundError


def _echo(value: str) -> ToolResult:
    return ToolResult(True, output=value, observation=f"echoed {value}")


def _boom() -> ToolResult:
    raise RuntimeError("kaboom")


class ToolRegistryTests(unittest.TestCase):
    def _echo_tool(self, risk=RiskLevel.LOW):
        return Tool(
            name="echo", description="echo a value",
            parameters={"value": {"type": "str", "required": True}},
            risk_level=risk, func=_echo,
        )

    def test_register_and_execute(self):
        reg = ToolRegistry()
        reg.register(self._echo_tool())
        result = reg.execute("echo", value="hi")
        self.assertTrue(result.success)
        self.assertEqual(result.output, "hi")

    def test_duplicate_registration_raises(self):
        reg = ToolRegistry()
        reg.register(self._echo_tool())
        with self.assertRaises(ValueError):
            reg.register(self._echo_tool())

    def test_unknown_tool_returns_failed_result_not_exception(self):
        reg = ToolRegistry()
        result = reg.execute("does_not_exist", value="x")
        self.assertFalse(result.success)
        self.assertIn("No such tool", result.error)

    def test_get_missing_tool_raises_typed_error(self):
        reg = ToolRegistry()
        with self.assertRaises(ToolNotFoundError):
            reg.get("nope")

    def test_missing_required_parameter_fails_cleanly(self):
        reg = ToolRegistry()
        reg.register(self._echo_tool())
        result = reg.execute("echo")
        self.assertFalse(result.success)
        self.assertIn("Missing required parameter", result.error)

    def test_unknown_parameter_fails_cleanly(self):
        reg = ToolRegistry()
        reg.register(self._echo_tool())
        result = reg.execute("echo", value="x", bogus="y")
        self.assertFalse(result.success)
        self.assertIn("Unknown parameter", result.error)

    def test_tool_exception_becomes_failed_result(self):
        reg = ToolRegistry()
        reg.register(Tool("boom", "always raises", {}, RiskLevel.LOW, _boom))
        result = reg.execute("boom")
        self.assertFalse(result.success)
        self.assertIn("kaboom", result.error)

    def test_high_risk_tool_blocked_without_confirmation(self):
        reg = ToolRegistry(confirm_fn=lambda prompt: False)
        reg.register(self._echo_tool(risk=RiskLevel.HIGH))
        result = reg.execute("echo", value="danger")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "confirmation_declined")

    def test_high_risk_tool_runs_when_confirmed(self):
        reg = ToolRegistry(confirm_fn=lambda prompt: True)
        reg.register(self._echo_tool(risk=RiskLevel.HIGH))
        result = reg.execute("echo", value="danger")
        self.assertTrue(result.success)

    def test_low_risk_tool_never_prompts(self):
        calls = []
        reg = ToolRegistry(confirm_fn=lambda p: calls.append(p) or False)
        reg.register(self._echo_tool(risk=RiskLevel.LOW))
        result = reg.execute("echo", value="fine")
        self.assertTrue(result.success)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
