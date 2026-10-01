import json
import os
import threading
from unittest.mock import Mock, patch

import pytest

from jarvis.agent.agent import Agent
from jarvis.agent.executor import Executor
from jarvis.agent.observer import observe
from jarvis.agent.planner import PlanParseError, parse_next_action
from jarvis.agent.tool_registry import ToolRegistry
from jarvis.tools.base import RiskLevel, Tool, ToolResult
from jarvis_integration import handle_command, _build_standalone_llm_fn, ModelUnavailable


def scripted(*responses):
    replies = iter(responses)
    return lambda prompt: next(replies)


def action(name, **parameters):
    return json.dumps({"action": name, "parameters": parameters})


def registry_with_tool(func=None, risk=RiskLevel.LOW, confirm=None):
    registry = ToolRegistry(confirm_fn=confirm)
    registry.register(Tool("test_tool", "Test observation", {}, risk,
                           func or (lambda: ToolResult(True, output="observed", observation="Done"))))
    return registry


def test_output_data_reaches_planner_even_with_summary():
    result = ToolResult(True, output=[{"href": "https://example.test/item"}],
                        observation="Found one link.")
    assert "https://example.test/item" in observe("browser_get_links", result)


@pytest.mark.parametrize("raw", [
    '{"action":[]}', '{"action":42}', '{"action":"TASK_COMPLETE","final_message":{}}',
    '{"action":"x","parameters":{"count":true}}',
    '{"action":"x","parameters":{"count":"2"}}',
])
def test_malformed_actions_never_escape_as_type_errors(raw):
    with pytest.raises(PlanParseError):
        parse_next_action(raw, [{"name": "x", "parameters": {"count": {"type": "int"}}}])


def test_stop_during_model_request_prevents_tool_execution():
    tool = Mock(return_value=ToolResult(True))
    registry = registry_with_tool(tool)
    count = 0

    def llm(prompt):
        nonlocal count
        count += 1
        if count == 1:
            return "Run a tool"
        registry.cancel_event.set()
        return action("test_tool")

    outcome = Executor(registry, llm).run("Run something")
    assert outcome.status.value == "cancelled"
    tool.assert_not_called()


def test_declining_confirmation_stops_the_entire_task():
    tool = Mock()
    registry = registry_with_tool(tool, RiskLevel.HIGH, lambda prompt: False)
    outcome = Executor(registry, scripted("Plan", action("test_tool"))).run("Run")
    assert outcome.status.value == "cancelled"
    tool.assert_not_called()


def test_failed_action_cannot_be_reported_as_completed():
    registry = registry_with_tool(lambda: ToolResult(False, error="no", observation="Failed"))
    llm = scripted("Plan", action("test_tool"), action("TASK_COMPLETE"))
    assert Executor(registry, llm).run("Run").status.value == "failed"

def test_no_tool_execution_cannot_be_reported_as_completed():
    executor = Executor(registry_with_tool(), scripted("Plan", action("TASK_COMPLETE")))
    assert executor.run("Do work").status.value == "failed"

def test_ui_action_is_followed_by_observation_before_next_model_call():
    registry = ToolRegistry()
    registry.register(Tool("browser_click", "Click test", {}, RiskLevel.LOW,
                           lambda: ToolResult(True, observation="Clicked")))
    registry.register(Tool("browser_observe", "Observe test", {}, RiskLevel.LOW,
                           lambda: ToolResult(True, output={"text": "Saved: Jarvis Test"})))
    prompts = []
    responses = iter(["Plan", action("browser_click"), action("TASK_COMPLETE")])

    def llm(prompt):
        prompts.append(prompt)
        return next(responses)

    outcome = Executor(registry, llm).run("Save")
    assert outcome.status.value == "completed"
    assert outcome.task_state.tool_history == ["browser_click", "browser_observe"]
    assert "Saved: Jarvis Test" in prompts[-1]


def test_parse_retry_count_resets_after_valid_actions():
    registry = registry_with_tool()
    llm = scripted("Plan", "bad", action("test_tool"), "bad", action("test_tool"),
                   "bad", action("test_tool"), action("TASK_COMPLETE"))
    assert Executor(registry, llm).run("Run").status.value == "completed"


def test_followup_resumes_existing_task_without_replanning():
    registry = registry_with_tool()
    prompts = []
    replies = iter(["Plan", action("test_tool"), json.dumps({
        "action": "USER_CONFIRMATION_REQUIRED", "final_message": "Which item?"
    }), action("test_tool"), action("TASK_COMPLETE")])

    def llm(prompt):
        prompts.append(prompt)
        return next(replies)

    executor = Executor(registry, llm)
    first = executor.run("Use an item")
    assert first.status.value == "needs_confirmation"
    final = executor.run("Use item two")
    assert final.status.value == "completed"
    assert len(final.task_state.completed_steps) == 2
    assert "Use item two" in prompts[-1]


def test_second_command_is_rejected_while_first_is_running():
    agent = Agent(registry_with_tool())
    with agent.command_lock:
        assert "task is running" in handle_command(agent, "do something").text
        assert handle_command(agent, "stop").text == "Task stopped."
        assert agent.registry.cancel_event.is_set()


def test_no_paid_fallback_in_default_local_mode():
    with patch.dict(os.environ, {"JARVIS_LLM_PROVIDER": "ollama"}), \
         patch("jarvis_integration._make_ollama_fn", return_value=Mock(side_effect=ModelUnavailable("offline"))), \
         patch("jarvis_integration._make_openai_fn") as make_cloud:
        with pytest.raises(ModelUnavailable):
            _build_standalone_llm_fn()("test")
        make_cloud.return_value.assert_not_called()


def test_ollama_action_request_uses_json_mode():
    from jarvis_integration import _make_ollama_fn
    response = Mock()
    response.read.return_value = b'{"response":"{\\"action\\":\\"TASK_COMPLETE\\"}"}'
    with patch("urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value = response
        _make_ollama_fn()("choose action\nJSON RESPONSE:")
        payload = json.loads(urlopen.call_args.args[0].data)
        assert payload["format"] == "json"
        assert payload["options"]["num_ctx"] >= 8192


def test_streamed_action_returns_before_trailing_generation():
    from jarvis_integration import _make_ollama_fn
    events = iter([
        json.dumps({"response": '{"action":'}),
        json.dumps({"response": '"TASK_COMPLETE","parameters":{}}'}),
        "must never be consumed after the complete action",
    ])
    with patch("urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value = events
        reply = _make_ollama_fn().structured("JSON RESPONSE:", {"type": "object"})
        assert json.loads(reply)["action"] == "TASK_COMPLETE"
        payload = json.loads(urlopen.call_args.args[0].data)
        assert payload["stream"] is True
        assert payload["format"] == {"type": "object"}
        assert next(events) == "must never be consumed after the complete action"


def test_large_page_history_is_bounded_and_prioritizes_latest_result():
    from jarvis.agent.task_state import TaskState
    state = TaskState("Inspect pages")
    state.observations = ["Old " + "x" * 20000] * 5 + ["LATEST " + "y" * 20000]
    context = state.recent_context()
    assert len(context) <= 14003
    assert "LATEST" in context
    assert "Old" not in context


def test_structured_actions_constrain_tool_arguments_at_generation():
    from jarvis.agent.planner import action_json_schema, next_action
    from jarvis.agent.task_state import TaskState
    from jarvis.tools.browser import register
    registry = ToolRegistry()
    register(registry)
    schema = action_json_schema(registry.specs())
    branch = next(b for b in schema["anyOf"] if b["properties"]["action"]["const"] == "browser_type")
    parameters = branch["properties"]["parameters"]
    assert "submit" not in parameters["required"]
    assert parameters["properties"]["submit"] == {"type": "boolean", "default": False}
    llm = Mock()
    llm.structured.return_value = action("browser_type", selector="#name", text="Hello")
    result = next_action(TaskState("Fill form"), registry.specs(), llm)
    assert result["action"] == "browser_type"
    llm.assert_not_called()
    assert "anyOf" in llm.structured.call_args.args[1]


def test_cancelling_voice_does_not_open_or_read_microphone():
    from jarvis.voice.stt import STTProvider
    provider = STTProvider.__new__(STTProvider)
    stream = Mock()
    provider.mic_stream = stream
    cancelled = threading.Event()
    cancelled.set()
    assert provider.listen(cancel_event=cancelled) is None
    stream.read.assert_not_called()
    stream.close.assert_called_once()


def test_blank_vosk_setting_uses_default_model_directory():
    from jarvis.voice.stt import get_vosk_path
    with patch.dict(os.environ, {"JARVIS_VOSK_MODEL": ""}):
        assert get_vosk_path().endswith("vosk-model-small-en-us-0.15")


def test_browser_adapter_and_engine_share_factory():
    from jarvis.tools.browser import _manager, browser_engine
    assert _manager.factory is browser_engine.factory

def test_literal_url_navigation_preserves_case_and_uses_direct_tool():
    from jarvis.router import route, RouteType
    result = route("Open https://example.org/CaseSensitive?q=AbC")
    assert result.route_type == RouteType.BROWSER
    assert result.tool_name == "browser_open"
    assert result.tool_args["url"] == "https://example.org/CaseSensitive?q=AbC"


def test_search_encodes_reserved_query_characters():
    from jarvis.router import _try_search
    result = _try_search("search R&D")
    assert result.tool_args["url"].endswith("q=R%26D")


def test_css_alias_and_submission_use_same_element():
    from jarvis.tools.browser_engine import ElementLocator, BrowserAutomationEngine
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    driver = Mock()
    ElementLocator.locate(driver, "#name", "css")
    driver.find_element.assert_called_with(By.CSS_SELECTOR, "#name")
    ElementLocator.locate(driver, '[data-jarvis-ref="observed-1"]')
    driver.find_element.assert_called_with(By.CSS_SELECTOR, '[data-jarvis-ref="observed-1"]')
    engine = BrowserAutomationEngine()
    engine.factory = Mock()
    engine.factory.get_context.return_value.driver = driver
    element = Mock()
    element.tag_name = "input"
    with patch.object(ElementLocator, "locate", return_value=element):
        assert engine.execute_task("type", "#name", {"text": "Alice", "submit": True})["success"]
    assert element.send_keys.call_args_list[-1].args == (Keys.ENTER,)


def test_browser_startup_error_is_a_failed_result():
    from jarvis.tools.browser_engine import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    engine.factory = Mock()
    engine.factory.get_context.side_effect = RuntimeError("profile locked")
    result = engine.execute_task("observe")
    assert not result["success"]
    assert "profile locked" in result["message"]

def test_typing_into_button_reports_control_mismatch_without_touching_it():
    from jarvis.tools.browser_engine import BrowserAutomationEngine, ElementLocator
    engine = BrowserAutomationEngine()
    engine.factory = Mock()
    button = Mock()
    button.tag_name = "button"
    button.text = "Save"
    button.get_attribute.return_value = "submit"
    with patch.object(ElementLocator, "locate", return_value=button):
        result = engine.execute_task("type", "#save", {"text": "Name"})
    assert not result["success"]
    assert "not a text field" in result["message"]
    button.clear.assert_not_called()
    button.send_keys.assert_not_called()


def test_filesystem_fast_delete_cannot_bypass_confirmation(tmp_path):
    from jarvis.filesystem_executor import execute_filesystem_route
    from jarvis.tools import filesystem
    path = tmp_path / "keep.txt"
    path.write_text("keep", encoding="utf-8")
    registry = ToolRegistry()
    filesystem.register(registry)
    result = execute_filesystem_route({
        "intent": "FILESYSTEM_DELETE", "target_name": "keep.txt",
        "location": str(tmp_path), "location_type": "ABSOLUTE_PATH",
    }, {"current_directory": str(tmp_path)}, None, registry=registry)
    assert not result["success"]
    assert path.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics")
def test_drive_root_and_case_insensitive_permissions():
    from jarvis.security.permissions import sanitize_path
    assert sanitize_path(r"C:\Users\Public", ["C:\\"]) is not None
    assert sanitize_path(r"C:\Users\Public", [r"c:\users"]) is not None
    assert sanitize_path(r"C:\UsersOther", [r"C:\Users"]) is None


def test_desktop_rejects_unobserved_control():
    from jarvis.tools.desktop import desktop_click
    assert desktop_click("not-in-snapshot").error == "stale_control"
