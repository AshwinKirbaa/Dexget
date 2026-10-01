import os
import sys
import time
from typing import Dict, Any, List, Optional
from .base import AutomationBackend, Observation

# We will import uiautomation inside methods to avoid startup lag
# and allow graceful failure if it's missing.

class UfoWindowsBackend(AutomationBackend):
    """
    Implements Windows desktop automation using the Microsoft UFO²
    philosophy (UIAutomation as primary, Win32 as fallback).
    """
    def __init__(self):
        self._last_snapshot: Dict[str, Any] = {}
        self._current_window: Optional[Any] = None
        
    def observe(self, **kwargs) -> Observation:
        import uiautomation as auto
        timeout_sec = float(os.environ.get("JARVIS_WINDOWS_ACTION_TIMEOUT", "10"))
        auto.SetGlobalSearchTimeout(timeout_sec)
        
        # Get active window
        active_win = auto.GetForegroundControl()
        if not active_win:
            return Observation("No active window found.", [])
            
        win_title = active_win.Name
        elements = []
        
        # Build UI tree (simplified UFO-style extraction)
        # Limit depth to avoid massive hangs
        self._last_snapshot.clear()
        
        text_lines = []
        text_lines.append(f"Window: {win_title}")
        
        def traverse(control, depth=0, max_depth=5):
            if depth > max_depth or not control:
                return
            try:
                if not control.IsOffscreen:
                    ctrl_id = f"ctrl_{len(elements)}"
                    ctrl_type = control.ControlTypeName
                    ctrl_name = control.Name
                    if ctrl_name or ctrl_type in ["ButtonControl", "EditControl", "ListItemControl", "MenuItemControl"]:
                        element_info = {
                            "id": ctrl_id,
                            "type": ctrl_type,
                            "name": ctrl_name,
                            "enabled": control.IsEnabled,
                            "control": control # Store reference
                        }
                        elements.append(element_info)
                        self._last_snapshot[ctrl_id] = control
                        text_lines.append(f"{'  ' * depth}[{ctrl_id}] {ctrl_type}: '{ctrl_name}' {'(disabled)' if not control.IsEnabled else ''}")
                        
                child = control.GetFirstChildControl()
                while child:
                    traverse(child, depth + 1, max_depth)
                    child = child.GetNextSiblingControl()
            except Exception:
                pass
                
        traverse(active_win)
        self._current_window = active_win
        
        return Observation(
            text_representation="\n".join(text_lines),
            ui_elements=elements,
            active_window=win_title
        )

    def click(self, target: str, **kwargs) -> bool:
        if target not in self._last_snapshot:
            print(f"Target {target} not found in last snapshot.")
            return False
            
        control = self._last_snapshot[target]
        try:
            control.SetFocus()
            # Try Invoke pattern first, fallback to Click
            if hasattr(control, 'Invoke'):
                control.Invoke()
            else:
                control.Click()
            return True
        except Exception as e:
            print(f"Click failed: {e}")
            return False

    def type(self, target: str, text: str, **kwargs) -> bool:
        if target not in self._last_snapshot:
            return False
            
        control = self._last_snapshot[target]
        try:
            control.SetFocus()
            import uiautomation as auto
            if hasattr(control, 'SetValue'):
                control.SetValue(text)
            else:
                auto.SendKeys(text)
            return True
        except Exception as e:
            print(f"Type failed: {e}")
            return False

    def press(self, key_combo: str, **kwargs) -> bool:
        import uiautomation as auto
        auto.SendKeys(key_combo)
        return True
        
    def scroll(self, direction: str, amount: int = 1, **kwargs) -> bool:
        import uiautomation as auto
        if direction == "down":
            auto.WheelDown(wheelTimes=amount)
        elif direction == "up":
            auto.WheelUp(wheelTimes=amount)
        return True

    def launch_application(self, app_name: str, **kwargs) -> bool:
        import subprocess
        try:
            # We can use our existing tool or just subprocess
            from jarvis.tools.application_resolver import find_installed_application
            info = find_installed_application(app_name)
            if info["installed"] and info["executable_path"]:
                subprocess.Popen([info["executable_path"]])
                time.sleep(2) # Wait for launch
                return True
            else:
                # Try shell
                os.startfile(app_name)
                time.sleep(2)
                return True
        except Exception:
            return False
            
    def focus_application(self, app_name: str, **kwargs) -> bool:
        import uiautomation as auto
        # Find window by title containing app_name
        for win in auto.GetRootControl().GetChildren():
            if win.ControlTypeName == "WindowControl" and app_name.lower() in win.Name.lower():
                win.SetFocus()
                return True
        return False
        
    def verify_action(self, expected_condition: str, **kwargs) -> bool:
        # Simple string-based expected condition for now
        obs = self.observe()
        return expected_condition.lower() in obs.text_representation.lower()
        
    def cancel(self):
        # UIAutomation doesn't strictly have a cancel, but we could interrupt waits
        pass
