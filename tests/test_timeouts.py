import os
import time
from unittest.mock import patch, MagicMock
import pytest

from jarvis.semantic.intent_schema import SemanticDecision, SemanticIntent
from jarvis.semantic.jev_router import evaluate_jev, map_decision_to_route
from jarvis.router import RouteType
from jarvis_integration import handle_command, build_agent

def mock_classify_intent_slow(command, context_str):
    time.sleep(5)
    return SemanticDecision(intent=SemanticIntent.UNKNOWN, confidence=0.0)

def mock_classify_intent_fast(command, context_str):
    return SemanticDecision(intent=SemanticIntent.UNKNOWN, confidence=1.0)

class TestTimeouts:

    @patch("jarvis.semantic.jev_router.classify_intent", side_effect=mock_classify_intent_slow)
    def test_semantic_timeout(self, mock_classify):
        # Temporarily set timeout to 0.1s
        os.environ["JARVIS_SEMANTIC_TIMEOUT_SECONDS"] = "0.1"
        os.environ["JARVIS_JEV_MODE"] = "active"
        
        start = time.time()
        decision, route_res = evaluate_jev("i need do some research in chrome")
        duration = time.time() - start
        
        assert duration < 0.5, "Semantic evaluation took too long, timeout failed"
        assert decision is None
        assert route_res is None

    @patch("jarvis.semantic.jev_router.classify_intent", side_effect=mock_classify_intent_fast)
    def test_unknown_intent_fast_failure(self, mock_classify):
        start = time.time()
        decision, route_res = evaluate_jev("i dont know do something")
        duration = time.time() - start
        
        assert duration < 0.5, "Unknown intent evaluation took too long"
        assert decision.intent == SemanticIntent.UNKNOWN
        assert route_res.route_type == RouteType.CHAT

    def test_missing_entity_fast_failure(self):
        decision = SemanticDecision(
            intent=SemanticIntent.BROWSER_SEARCH,
            confidence=0.9,
            application="chrome"
        )
        start = time.time()
        route_res = map_decision_to_route(decision, "i need do some research in chrome")
        duration = time.time() - start
        
        assert duration < 0.1
        assert route_res.route_type == RouteType.CHAT
        assert "research in Chrome" in route_res.text

    def test_agent_timeout(self):
        # Build an agent and restrict max steps to 1 to simulate a fast agent timeout
        os.environ["JARVIS_MAX_STEPS"] = "1"
        os.environ["JARVIS_JEV_MODE"] = "disabled" # Disable jev to fall through to agent if we use a complex prompt
        agent = build_agent()
        
        # Mock LLM to return dummy plans endlessly
        def dummy_llm(prompt, schema=None):
            if schema is not None:
                import json
                return json.dumps({"action": "win_open_application", "parameters": {"app_name": "notepad"}, "thought": "dummy"})
            return "dummy"
            
        agent.llm_fn = dummy_llm
        agent.llm_fn.structured = dummy_llm
        agent.executor.llm_fn = dummy_llm
        
        # Mock registry to avoid opening real apps
        original_execute = agent.registry.execute
        def mock_exec(*args, **kwargs):
            from jarvis.agent.tool_registry import ToolResult
            return ToolResult(True, "opened notepad")
        agent.registry.execute = mock_exec
        
        print("Starting agent handle_command...")
        start = time.time()
        try:
            res = handle_command(agent, "some really complex unknown task requiring the agent")
        except Exception as e:
            print("Exception in handle_command:", e)
            raise e
        duration = time.time() - start
        print("handle_command finished in", duration, "seconds")
        
        assert duration < 5.0, f"Agent loop took too long: {duration}"
        assert "Reached the maximum of 1 steps" in res.text

    def test_unavailable_handler(self):
        # Create a fast mock for agent
        agent = build_agent()
        # Create a dummy tool in the registry
        from jarvis.tools.base import Tool, RiskLevel
        agent.registry.register(Tool("dummy_tool", "Dummy", {}, RiskLevel.LOW, lambda: None, "test"))
        
        # Route a simple command directly to it, wait, it's not possible to do directly through handle_command without Jev or Router, 
        # so let's mock the execution itself
        start = time.time()
        res = agent.registry.execute("unavailable_tool_xyz", some_arg="test")
        duration = time.time() - start
        
        assert duration < 0.1
        assert res.success is False
        assert "no such tool" in res.observation.lower()
