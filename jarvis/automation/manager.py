from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from .base import AutomationBackend, Observation

@dataclass
class AutomationState:
    current_application: Optional[str] = None
    current_window: Optional[str] = None
    current_browser: Optional[str] = None
    current_tab: Optional[str] = None
    current_url: Optional[str] = None
    current_page: Optional[str] = None
    current_focus: Optional[str] = None
    current_task: Optional[str] = None
    current_subtask: Optional[str] = None
    current_step: int = 0
    failure_count: int = 0
    last_action: Optional[str] = None
    last_observation: Optional[Observation] = None
    last_verification: Optional[bool] = None
    recent_results: List[Dict[str, Any]] = field(default_factory=list)
    selected_element: Optional[str] = None

class AutomationManager:
    """
    Manages the automation backends and maintains state.
    Routes commands to the appropriate backend (Windows vs Browser).
    """
    def __init__(self):
        self.state = AutomationState()
        self.windows_backend: Optional[AutomationBackend] = None
        self.browser_backend: Optional[AutomationBackend] = None
        
    def register_windows_backend(self, backend: AutomationBackend):
        self.windows_backend = backend
        
    def register_browser_backend(self, backend: AutomationBackend):
        self.browser_backend = backend

    def get_backend(self, target_domain: str) -> AutomationBackend:
        if target_domain == "browser":
            if not self.browser_backend:
                from .browser_backend import BrowserUseBackend
                self.browser_backend = BrowserUseBackend()
            return self.browser_backend
        else:
            if not self.windows_backend:
                from .ufo_backend import UfoWindowsBackend
                self.windows_backend = UfoWindowsBackend()
            return self.windows_backend

    def update_state(self, updates: Dict[str, Any]):
        for key, val in updates.items():
            if hasattr(self.state, key):
                setattr(self.state, key, val)

    def execute_action(self, target_domain: str, action: str, **kwargs) -> bool:
        backend = self.get_backend(target_domain)
            
        self.update_state({"last_action": f"{action}({kwargs})"})
        
        # Execute
        func = getattr(backend, action, None)
        if not func:
            raise NotImplementedError(f"Action '{action}' not supported by {target_domain} backend")
            
        success = func(**kwargs)
        
        # Post-action update
        self.state.recent_results.append({"action": action, "success": success})
        return success
        
    def observe(self, target_domain: str, **kwargs) -> Observation:
        backend = self.get_backend(target_domain)
            
        obs = backend.observe(**kwargs)
        self.update_state({
            "last_observation": obs,
            "current_window": obs.active_window,
            "current_focus": obs.focused_element,
            "current_url": obs.url,
            "current_page": obs.page_title
        })
        return obs
        
    def cancel_all(self):
        if self.windows_backend:
            self.windows_backend.cancel()
        if self.browser_backend:
            self.browser_backend.cancel()

# Global singleton for JARVIS agent to use
automation_manager = AutomationManager()
