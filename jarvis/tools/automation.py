import time
from typing import Dict, Any, Callable, List
from jarvis.agent.tool_registry import ToolRegistry

def register_automation_tools(registry: ToolRegistry, confirm_fn: Callable[[str], bool]):
    from jarvis.automation import automation_manager

    from jarvis.tools.base import Tool, RiskLevel, ToolResult
    from jarvis.automation.verifier import verify_application_open

    # --- Windows Tools ---
    def windows_observe(**kwargs):
        obs = automation_manager.observe("windows")
        return ToolResult(True, observation=obs.text_representation)

    def windows_click(target: str, **kwargs):
        success = automation_manager.execute_action("windows", "click", target=target)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=f"Clicked {target}. Action success: {success}. New state:\n{obs.text_representation}")

    def windows_type(target: str, text: str, **kwargs):
        success = automation_manager.execute_action("windows", "type", target=target, text=text)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=f"Typed into {target}. Action success: {success}. New state:\n{obs.text_representation}")

    def windows_press(key_combo: str, **kwargs):
        success = automation_manager.execute_action("windows", "press", key_combo=key_combo)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=f"Pressed {key_combo}. Action success: {success}. New state:\n{obs.text_representation}")
        
    def windows_launch(app_name: str, **kwargs):
        action_success = automation_manager.execute_action("windows", "launch_application", app_name=app_name)
        obs = automation_manager.observe("windows")
        if not verify_application_open(automation_manager, app_name):
            return ToolResult(False, observation=f"Failed to verify {app_name} launched. State:\n{obs.text_representation}")
        return ToolResult(True, observation=f"Successfully verified {app_name} launched.\n{obs.text_representation}")

    def windows_focus(app_name: str, **kwargs):
        from jarvis.automation.verifier import verify_window_focused
        action_success = automation_manager.execute_action("windows", "focus_application", app_name=app_name)
        obs = automation_manager.observe("windows")
        if not verify_window_focused(automation_manager, app_name):
            return ToolResult(False, observation=f"Failed to focus {app_name}. State:\n{obs.text_representation}")
        return ToolResult(True, observation=f"Successfully focused {app_name}.\n{obs.text_representation}")

    registry.register(Tool(
        name="windows_observe",
        description="Observe the current Windows desktop and active application UI tree. Call this before clicking or typing.",
        parameters={},
        func=windows_observe,
        category="windows",
        risk_level=RiskLevel.LOW
    ))
    registry.register(Tool(
        name="windows_focus",
        description="Bring a desktop application to the foreground.",
        parameters={"app_name": "Name of the application"},
        func=windows_focus,
        category="windows",
        risk_level=RiskLevel.MEDIUM
    ))
    registry.register(Tool(
        name="windows_click",
        description="Click an element on the Windows UI.",
        parameters={"target": {"type": "str", "description": "ID of the element to click (from windows_observe)"}},
        func=windows_click,
        category="windows",
        risk_level=RiskLevel.MEDIUM
    ))
    registry.register(Tool(
        name="windows_type",
        description="Type text into an element on the Windows UI.",
        parameters={
            "target": {"type": "str", "description": "ID of the element"},
            "text": {"type": "str", "description": "Text to type"}
        },
        func=windows_type,
        category="windows",
        risk_level=RiskLevel.MEDIUM
    ))
    registry.register(Tool(
        name="windows_press",
        description="Press a keyboard combination (e.g., '{Enter}', 'Ctrl+C').",
        parameters={"key_combo": {"type": "str", "description": "Key combination to press"}},
        func=windows_press,
        category="windows",
        risk_level=RiskLevel.MEDIUM
    ))
    registry.register(Tool(
        name="windows_launch",
        description="Launch a desktop application.",
        parameters={
            "app_name": {"type": "str", "description": "Name of the application"},
            "browser": {"type": "str", "description": "Browser to use (optional)", "required": False},
            "profile": {"type": "str", "description": "Browser profile to use (optional)", "required": False}
        },
        func=windows_launch,
        category="windows",
        risk_level=RiskLevel.MEDIUM
    ))
    
    # --- Browser Tools ---
    def browser_observe(**kwargs):
        obs = automation_manager.observe("browser")
        return ToolResult(True, observation=obs.text_representation)

    def browser_navigate(url: str, **kwargs):
        success = automation_manager.execute_action("browser", "launch_application", url=url, app_name="browser")
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Navigated to {url}.\n{obs.text_representation}")

    def browser_click(target: str, **kwargs):
        success = automation_manager.execute_action("browser", "click", target=target)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Clicked {target}.\n{obs.text_representation}")

    def browser_type(target: str, text: str, **kwargs):
        success = automation_manager.execute_action("browser", "type", target=target, text=text)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Typed '{text}' into {target}.\n{obs.text_representation}")

    def browser_press(key_combo: str, **kwargs):
        success = automation_manager.execute_action("browser", "press", key_combo=key_combo)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Pressed {key_combo}.\n{obs.text_representation}")

    registry.register(Tool(
        name="browser_observe",
        description="Observe the current browser page, URL, title, and interactive DOM elements.",
        parameters={},
        func=browser_observe,
        category="browser",
        risk_level=RiskLevel.LOW
    ))
    registry.register(Tool(
        name="browser_navigate",
        description="Navigate the browser to a URL.",
        parameters={
            "url": {"type": "str", "description": "The full URL to navigate to"},
            "browser": {"type": "str", "description": "Browser to use (optional)", "required": False},
            "profile": {"type": "str", "description": "Browser profile to use (optional)", "required": False}
        },
        func=browser_navigate,
        category="browser",
        risk_level=RiskLevel.MEDIUM
    ))
    registry.register(Tool(
        name="browser_click",
        description="Click an element on the browser page.",
        parameters={"target": {"type": "str", "description": "ID or text of the element to click (from browser_observe)"}},
        func=browser_click,
        category="browser",
        risk_level=RiskLevel.MEDIUM
    ))
    registry.register(Tool(
        name="browser_type",
        description="Type text into an input field on the browser page.",
        parameters={
            "target": {"type": "str", "description": "ID of the element"},
            "text": {"type": "str", "description": "Text to type"}
        },
        func=browser_type,
        category="browser",
        risk_level=RiskLevel.MEDIUM
    ))
    registry.register(Tool(
        name="browser_press",
        description="Press a keyboard key in the browser (e.g., 'Enter').",
        parameters={"key_combo": {"type": "str", "description": "Key to press"}},
        func=browser_press,
        category="browser",
        risk_level=RiskLevel.MEDIUM
    ))
