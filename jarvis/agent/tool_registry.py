"""
Central Tool Registry.

Every tool JARVIS can execute is registered here exactly once. The
agent/executor never imports selenium/pyautogui/os directly - it only
ever asks the registry to run a named tool. Calls are validated and
checked for cancellation and confirmation before touching the machine.
The shell tools provide broad control and therefore require approval.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional
from threading import Event

from jarvis.tools.base import RiskLevel, Tool, ToolResult


class ToolNotFoundError(Exception):
    pass


class ToolRegistry:
    def __init__(self, confirm_fn: Optional[Callable[[str], bool]] = None):
        self._tools: Dict[str, Tool] = {}
        # confirm_fn(prompt) -> bool. Defaults to auto-deny for safety if
        # nobody wires up a real confirmation channel (voice/GUI/terminal).
        self._confirm_fn = confirm_fn or (lambda prompt: False)
        self.cancel_event = Event()
        self.unavailable = {}

    def register(self, tool: Tool, overwrite: bool = False) -> None:
        if tool.name in self._tools and not overwrite:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolNotFoundError(
                f"No such tool: '{name}'. Available: {sorted(self._tools)}"
            )
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self, categories: Optional[List[str]] = None) -> List[Tool]:
        tools = list(self._tools.values())
        if categories:
            tools = [t for t in tools if t.category in categories]
        return sorted(tools, key=lambda t: t.name)

    def specs(self, categories: Optional[List[str]] = None) -> List[dict]:
        return [t.spec() for t in self.list_tools(categories)]

    def execute(self, name: str, **kwargs) -> ToolResult:
        """
        Validate risk level, request confirmation for HIGH/DESTRUCTIVE
        actions, then execute. This is the ONLY path anything (LLM plan,
        terminal, macro replay) should use to actually run a tool.
        """
        try:
            tool = self.get(name)
        except ToolNotFoundError as exc:
            return ToolResult(success=False, error=str(exc), observation=str(exc))

        error = tool.validate(kwargs)
        if error:
            return ToolResult(False, error=error, observation=error)
        if self.cancel_event.is_set():
            return ToolResult(False, error="cancelled", observation="Task stopped.")
        if tool.risk_level.requires_confirmation:
            prompt = (
                f"JARVIS wants to run '{tool.name}' "
                f"({tool.risk_level.value.upper()} risk) with arguments {kwargs}. Proceed?"
            )
            if not self._confirm_fn(prompt):
                msg = f"User declined to confirm '{tool.name}'; action cancelled."
                return ToolResult(success=False, error="confirmation_declined", observation=msg)

        if self.cancel_event.is_set():
            return ToolResult(False, error="cancelled", observation="Task stopped.")
        return tool.execute(**kwargs)


def build_default_registry(confirm_fn=None) -> ToolRegistry:
    """
    Wires up every tool module. Each tools/*.py module exposes a
    `register(registry)` function so this stays a one-line-per-module
    list instead of a giant import block. Optional dependencies
    (selenium, pyautogui, pywin32) register nothing if unavailable
    instead of raising at import time.
    """
    registry = ToolRegistry(confirm_fn=confirm_fn)

    from jarvis.tools import filesystem, terminal, process, windows, web_extract

    filesystem.register(registry)
    terminal.register(registry)
    process.register(registry)
    windows.register(registry)
    web_extract.register(registry)
    
    try:
        from jarvis.capabilities import windows_system
        windows_system.register(registry)
    except Exception as exc:
        registry.unavailable["windows_system"] = str(exc)

    try:
        from jarvis.tools import local_media
        local_media.register(registry)
    except Exception:
        pass

    # Legacy tools superseded by jarvis.tools.automation:
    # try:
    #     from jarvis.tools import browser
    #     browser.register(registry)
    # except Exception as exc:
    #     registry.unavailable["browser"] = str(exc)

    # try:
    #     from jarvis.tools import pyautogui_tool
    #     pyautogui_tool.register(registry)
    # except Exception as exc:
    #     registry.unavailable["desktop_input"] = str(exc)

    try:
        from jarvis.tools import desktop
        desktop.register(registry)
    except Exception as exc:
        registry.unavailable["desktop_accessibility"] = str(exc)
        
    try:
        from jarvis.tools import rag_tools
        rag_tools.register(registry)
    except Exception:
        pass
        
    try:
        from jarvis.tools import scheduler_tools
        scheduler_tools.register(registry)
    except Exception:
        pass
        
    try:
        from jarvis.automation import capabilities
        capabilities.register_capabilities(registry, confirm_fn)
    except Exception as exc:
        registry.unavailable["capabilities"] = str(exc)

    return registry
