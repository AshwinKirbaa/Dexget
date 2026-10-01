import os
import logging
from typing import Optional, Tuple
from jarvis.semantic.intent_schema import SemanticIntent, SemanticDecision
from jarvis.semantic.jev_client import classify_intent
from jarvis.semantic.context import context
from jarvis.router import RouteResult, RouteType, ToolCall

logger = logging.getLogger(__name__)

def evaluate_jev(command: str) -> Tuple[Optional[SemanticDecision], Optional[RouteResult]]:
    """Classifies with Jev and returns (Decision, RouteResult)."""
    jev_mode = os.environ.get("JARVIS_JEV_MODE", "shadow").lower()
    if jev_mode == "disabled":
        return None, None
        
    timeout = float(os.environ.get("JARVIS_SEMANTIC_TIMEOUT_SECONDS", "2.0"))
    
    import threading
    result_container = []
    
    def target():
        try:
            res = classify_intent(command, context.format_for_prompt())
            result_container.append(res)
        except Exception as e:
            result_container.append(e)
            
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout)
    
    if t.is_alive():
        logger.error(f"Jev classification timed out after {timeout} seconds.")
        return None, None
        
    if not result_container:
        return None, None
        
    res = result_container[0]
    if isinstance(res, Exception):
        logger.error(f"Jev classification error: {res}")
        return None, None
        
    decision = res
        
    auto_execute_threshold = float(os.environ.get("JARVIS_JEV_AUTO_EXECUTE_THRESHOLD", "0.85"))
    agent_threshold = float(os.environ.get("JARVIS_JEV_AGENT_THRESHOLD", "0.60"))
    
    if decision.confidence < agent_threshold:
        return decision, RouteResult(RouteType.CHAT, text="I'm not completely sure what you mean. Could you clarify?")
        
    if decision.confidence < auto_execute_threshold and decision.intent != SemanticIntent.AGENT_TASK:
        return decision, RouteResult(RouteType.AGENT)
        
    route_res = map_decision_to_route(decision, command)
    return decision, route_res

def map_decision_to_route(decision: SemanticDecision, original_cmd: str) -> Optional[RouteResult]:
    intent = decision.intent
    
    if intent == SemanticIntent.APPLICATION_OPEN or intent == SemanticIntent.APPLICATION_FOCUS:
        if decision.application:
            return RouteResult(RouteType.APPLICATION, tool_name="win_open_application", tool_args={"app_name": decision.application}, label=f"Opening {decision.application}")
        return RouteResult(RouteType.CHAT, text="Which application should I open?")
            
    elif intent == SemanticIntent.APPLICATION_WORKFLOW:
        if decision.application and decision.workflow:
            return RouteResult(
                RouteType.APPLICATION, 
                tool_calls=[
                    ToolCall("win_open_application", {"app_name": decision.application}, f"Opening {decision.application}"),
                    ToolCall("keyboard_type", {"text": decision.workflow}, f"Typing {decision.workflow}")
                ],
                label=f"Workflow in {decision.application}"
            )
        elif not decision.application:
            return RouteResult(RouteType.CHAT, text="Which application should I open?")
        else:
            return RouteResult(RouteType.CHAT, text=f"What would you like me to do in {decision.application}?")
            
    elif intent == SemanticIntent.YOUTUBE_PLAY or intent == SemanticIntent.YOUTUBE_SEARCH:
        if decision.query:
            return RouteResult(RouteType.BROWSER, tool_name="youtube_play", tool_args={"query": decision.query}, label=f"Playing {decision.query} on YouTube")
        return RouteResult(RouteType.CHAT, text="What would you like me to search for on YouTube?")
            
    elif intent == SemanticIntent.YOUTUBE_MUSIC_PLAY or intent == SemanticIntent.YOUTUBE_MUSIC_SEARCH:
        if decision.query:
            return RouteResult(RouteType.BROWSER, tool_name="youtube_music_play", tool_args={"query": decision.query}, label=f"Playing {decision.query} on YouTube Music")
        return RouteResult(RouteType.CHAT, text="Which song should I play on YouTube Music?")
            
    elif intent == SemanticIntent.LOCAL_MEDIA_PLAY:
        if decision.media:
            return RouteResult(RouteType.WINDOWS, tool_name="win_play_local_media", tool_args={"media_title": decision.media, "source": decision.folder or ""}, label=f"Playing {decision.media}")
        return RouteResult(RouteType.CHAT, text="Which media file or episode should I play?")
            
    elif intent == SemanticIntent.MEMORY_SET:
        if decision.target and decision.value:
            return RouteResult(RouteType.MEMORY, tool_name="set", tool_args={"key": decision.target, "value": decision.value}, label=f"Remembering {decision.target} is {decision.value}")
        return RouteResult(RouteType.CHAT, text="What exactly would you like me to remember?")
            
    elif intent == SemanticIntent.MEMORY_GET or intent == SemanticIntent.MEMORY_RECALL:
        if decision.target:
            return RouteResult(RouteType.MEMORY, tool_name="get", tool_args={"key": decision.target}, label=f"Recalling {decision.target}")
        return RouteResult(RouteType.CHAT, text="What would you like me to recall?")
            
    elif intent == SemanticIntent.BROWSER_OPEN or intent == SemanticIntent.BROWSER_NAVIGATE:
        if decision.url:
            return RouteResult(RouteType.BROWSER, tool_name="browser_open", tool_args={"url": decision.url}, label=f"Opening {decision.url}")
        elif decision.target:
            return RouteResult(RouteType.BROWSER, tool_name="browser_open", tool_args={"url": f"https://{decision.target}"}, label=f"Opening {decision.target}")
        return RouteResult(RouteType.CHAT, text="Which website should I open?")
            
    elif intent == SemanticIntent.BROWSER_SEARCH or intent == SemanticIntent.BROWSER_WORKFLOW:
        if decision.query:
            import urllib.parse
            url = f"https://www.google.com/search?q={urllib.parse.quote_plus(decision.query)}"
            return RouteResult(RouteType.SEARCH, tool_name="browser_open", tool_args={"url": url}, label=f"Searching {decision.query}")
        # Missing topic
        browser_name = decision.application or "the browser"
        return RouteResult(RouteType.CHAT, text=f"Sure. What would you like me to research in {browser_name.capitalize()}?")
        
    elif intent == SemanticIntent.SYSTEM_ACTION or intent == SemanticIntent.WINDOWS_ACTION:
        return RouteResult(RouteType.CHAT, text="I'm not exactly sure which system action you want me to perform.")
        
    elif intent == SemanticIntent.UNKNOWN:
        return RouteResult(RouteType.CHAT, text="I'm not sure what you want me to do. Could you rephrase that?")

    elif intent == SemanticIntent.AGENT_TASK:
        return RouteResult(RouteType.AGENT, text=original_cmd)

    return RouteResult(RouteType.AGENT)
