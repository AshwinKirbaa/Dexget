"""
PyAutoGUI-based desktop automation - the fallback for apps that expose no
usable API/DOM (per spec section 7/20). Only registered if `pyautogui`
is importable. Like browser.py, this needs a real Windows desktop with a
display to smoke-test; it cannot run headless in this sandbox.
"""
from __future__ import annotations

import pyautogui  # noqa: F401 - import error here disables registration

from jarvis.tools.base import RiskLevel, Tool, ToolResult

pyautogui.FAILSAFE = True  # moving mouse to a screen corner aborts - safety net


def mouse_move(x: int, y: int, duration: float = 0.2) -> ToolResult:
    pyautogui.moveTo(x, y, duration=duration)
    return ToolResult(True, observation=f"Moved mouse to ({x}, {y})")


def mouse_click(x: int = None, y: int = None, button: str = "left") -> ToolResult:
    if x is not None and y is not None:
        pyautogui.click(x=x, y=y, button=button)
    else:
        pyautogui.click(button=button)
    return ToolResult(True, observation=f"Clicked {button} button at ({x}, {y})")


def mouse_double_click(x: int = None, y: int = None) -> ToolResult:
    if x is not None and y is not None:
        pyautogui.doubleClick(x=x, y=y)
    else:
        pyautogui.doubleClick()
    return ToolResult(True, observation=f"Double-clicked at ({x}, {y})")


def keyboard_type(text: str, interval: float = 0.02) -> ToolResult:
    pyautogui.write(text, interval=interval)
    return ToolResult(True, observation=f"Typed: {text!r}")


def keyboard_hotkey(keys: str) -> ToolResult:
    combo = [k.strip() for k in keys.split("+")]
    pyautogui.hotkey(*combo)
    return ToolResult(True, observation=f"Pressed hotkey {keys}")


def screen_screenshot(path: str) -> ToolResult:
    img = pyautogui.screenshot()
    img.save(path)
    return ToolResult(True, output=path, observation=f"Saved screenshot to {path}")


def register(registry) -> None:
    registry.register(Tool("mouse_move", "Move the mouse cursor to (x, y).",
                            {"x": {"type": "int", "required": True}, "y": {"type": "int", "required": True},
                             "duration": {"type": "float"}}, RiskLevel.MEDIUM, mouse_move, "desktop"))
    registry.register(Tool("mouse_click", "Click the mouse at (x, y) or the current position.",
                            {"x": {"type": "int"}, "y": {"type": "int"}, "button": {"type": "str"}},
                            RiskLevel.MEDIUM, mouse_click, "desktop"))
    registry.register(Tool("mouse_double_click", "Double-click at (x, y) or the current position.",
                            {"x": {"type": "int"}, "y": {"type": "int"}}, RiskLevel.MEDIUM, mouse_double_click, "desktop"))
    registry.register(Tool("keyboard_type", "Type a string of text at the current focus.",
                            {"text": {"type": "str", "required": True}, "interval": {"type": "float"}},
                            RiskLevel.MEDIUM, keyboard_type, "desktop"))
    registry.register(Tool("keyboard_hotkey", "Press a key combination, e.g. 'ctrl+s'.",
                            {"keys": {"type": "str", "required": True}}, RiskLevel.MEDIUM, keyboard_hotkey, "desktop"))
    registry.register(Tool("screen_screenshot", "Take a full-screen screenshot and save it to a path.",
                            {"path": {"type": "str", "required": True}}, RiskLevel.LOW, screen_screenshot, "desktop"))
