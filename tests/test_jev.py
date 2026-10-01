import os
import pytest
from jarvis.semantic.intent_schema import SemanticDecision, SemanticIntent
from jarvis.semantic.jev_client import classify_intent
from jarvis.semantic.jev_router import evaluate_jev
from jarvis.router import RouteType

def test_intent_schema():
    decision = SemanticDecision(
        intent=SemanticIntent.APPLICATION_OPEN,
        confidence=0.9,
        application="chrome"
    )
    assert decision.intent == SemanticIntent.APPLICATION_OPEN
    assert decision.application == "chrome"

@pytest.fixture
def mock_typesafe(monkeypatch):
    class MockClient:
        def system_one(self, **kwargs):
            state = kwargs.get("state", "").lower()
            if "chrome" in state:
                return SemanticDecision(intent=SemanticIntent.APPLICATION_OPEN, confidence=0.9, application="chrome")
            if "youtube music" in state:
                return SemanticDecision(intent=SemanticIntent.YOUTUBE_MUSIC_PLAY, confidence=0.9, query="radhimma")
            if "youtube" in state:
                return SemanticDecision(intent=SemanticIntent.YOUTUBE_PLAY, confidence=0.9, query="radhimma")
            if "play" in state and "dexter" in state:
                return SemanticDecision(intent=SemanticIntent.LOCAL_MEDIA_PLAY, confidence=0.9, folder="movies", media="dexter")
            if "remember" in state:
                return SemanticDecision(intent=SemanticIntent.MEMORY_SET, confidence=0.9, target="test directory", value="tester")
            if "search" in state:
                return SemanticDecision(intent=SemanticIntent.BROWSER_SEARCH, confidence=0.9, query="python tutorials")
            
            # Return UNKNOWN if nothing matches explicitly for testing
            return SemanticDecision(intent=SemanticIntent.UNKNOWN, confidence=0.1)

    monkeypatch.setattr("typesafe_sdk.TypeSafeClient", lambda api_key: MockClient())

def test_classify_intent(mock_typesafe, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test_key")
    
    decision = classify_intent("hey jarvis, could you bring chrome up?")
    assert decision.intent == SemanticIntent.APPLICATION_OPEN
    assert decision.application == "chrome"
    
    decision = classify_intent("play radhimma in youtube music")
    assert decision.intent == SemanticIntent.YOUTUBE_MUSIC_PLAY

def test_evaluate_jev_active(mock_typesafe, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test_key")
    monkeypatch.setenv("JARVIS_JEV_MODE", "active")
    
    decision, route = evaluate_jev("hey jarvis, could you bring chrome up?")
    assert decision.intent == SemanticIntent.APPLICATION_OPEN
    assert route.route_type == RouteType.APPLICATION
    assert route.tool_name == "win_open_application"
    assert route.tool_args["app_name"] == "chrome"

def test_evaluate_jev_disabled(monkeypatch):
    monkeypatch.setenv("JARVIS_JEV_MODE", "disabled")
    decision, route = evaluate_jev("open chrome")
    assert decision is None
    assert route is None

def test_evaluate_jev_low_confidence(mock_typesafe, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test_key")
    monkeypatch.setenv("JARVIS_JEV_MODE", "active")
    
    # Should get UNKNOWN with 0.1 confidence based on mock
    decision, route = evaluate_jev("do something weird")
    assert route.route_type == RouteType.CHAT
    assert "clarify" in route.text

def test_evaluate_jev_agent_fallback(mock_typesafe, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test_key")
    monkeypatch.setenv("JARVIS_JEV_MODE", "active")
    monkeypatch.setenv("JARVIS_JEV_AUTO_EXECUTE_THRESHOLD", "0.99") # Make it fall back
    
    # The mock returns 0.9 confidence for this
    decision, route = evaluate_jev("open chrome")
    
    # Should fallback to agent because confidence 0.9 < 0.99
    assert route.route_type == RouteType.AGENT
