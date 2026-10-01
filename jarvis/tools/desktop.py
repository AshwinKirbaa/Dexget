"""Windows accessibility observations and actions on observed controls."""
from contextlib import contextmanager
from importlib.util import find_spec
import os
import uuid

from jarvis.tools.base import RiskLevel, Tool, ToolResult

_snapshot = {}


@contextmanager
def _desktop():
    import pythoncom
    pythoncom.CoInitialize()
    try:
        from pywinauto import Desktop
        yield Desktop(backend="uia")
    finally:
        pythoncom.CoUninitialize()


def desktop_observe(window: int = 0) -> ToolResult:
    """Return an accessibility snapshot, without stealing keyboard focus."""
    import win32gui
    _snapshot.clear()
    with _desktop() as desktop:
        windows = [w for w in desktop.windows()
                   if w.is_visible() and w.process_id() != os.getpid()]
        data = {"windows": [{"handle": w.handle, "title": w.window_text()[:200]}
                            for w in windows], "controls": []}
        handle = window or win32gui.GetForegroundWindow()
        target = next((w for w in windows if w.handle == handle), None)
        if target is None:
            return ToolResult(True, output=data,
                              observation="Choose a window handle from this list and observe it.")
        data["window"] = handle
        data["title"] = target.window_text()
        prefix = uuid.uuid4().hex[:8]
        for control in target.descendants(depth=6):
            if len(data["controls"]) >= 80:
                data["truncated"] = True
                break
            try:
                if not control.is_visible():
                    continue
                info = control.element_info
                control_id = f"{prefix}-{len(data['controls'])}"
                rect = control.rectangle()
                _snapshot[control_id] = (handle, tuple(info.runtime_id))
                data["controls"].append({
                    "control_id": control_id, "name": info.name[:200],
                    "type": info.control_type, "automation_id": info.automation_id,
                    "enabled": control.is_enabled(),
                    "rect": [rect.left, rect.top, rect.right, rect.bottom],
                })
            except Exception:
                continue
        return ToolResult(True, output=data, observation=f"Observed desktop window {handle}.")


def desktop_focus(window: int) -> ToolResult:
    with _desktop() as desktop:
        target = desktop.window(handle=window).wrapper_object()
        if target.is_minimized():
            target.restore()
        target.set_focus()
    return ToolResult(True, observation=f"Focused window {window}. Observe it before interacting.")


def _control_action(control_id: str, text=None) -> ToolResult:
    if control_id not in _snapshot:
        return ToolResult(False, error="stale_control",
                          observation="Control snapshot expired. Use desktop_observe again.")
    handle, runtime_id = _snapshot[control_id]
    with _desktop() as desktop:
        target = desktop.window(handle=handle).wrapper_object()
        for control in target.descendants(depth=6):
            if tuple(control.element_info.runtime_id) != runtime_id:
                continue
            if not control.is_visible() or not control.is_enabled():
                return ToolResult(False, error="unavailable_control",
                                  observation="Control is hidden or disabled. Observe again.")
            try:
                target.set_focus()
                if text is None:
                    control.click_input()
                else:
                    control.set_edit_text(text)
            finally:
                _snapshot.clear()
            return ToolResult(True, observation="Control action executed. Observe the window to verify.")
    _snapshot.clear()
    return ToolResult(False, error="stale_control", observation="Control disappeared. Observe again.")


def desktop_click(control_id: str) -> ToolResult:
    return _control_action(control_id)


def desktop_type(control_id: str, text: str) -> ToolResult:
    return _control_action(control_id, text)


def register(registry):
    if os.name != "nt" or find_spec("pywinauto") is None:
        raise ImportError("Windows desktop controls require: pip install pywinauto")
    registry.register(Tool("desktop_observe", "List desktop windows; inspect controls in a window by handle.",
                           {"window": {"type": "int"}}, RiskLevel.LOW, desktop_observe, "desktop"))
    registry.register(Tool("desktop_focus", "Bring an observed window to the foreground.",
                           {"window": {"type": "int", "required": True}},
                           RiskLevel.MEDIUM, desktop_focus, "desktop"))
    selector = {"control_id": {"type": "str", "required": True}}
    registry.register(Tool("desktop_click", "Click a control_id from the latest desktop_observe snapshot.",
                           selector, RiskLevel.MEDIUM, desktop_click, "desktop"))
    registry.register(Tool("desktop_type", "Replace an edit control's text, including Unicode.",
                           {**selector, "text": {"type": "str", "required": True}},
                           RiskLevel.MEDIUM, desktop_type, "desktop"))
