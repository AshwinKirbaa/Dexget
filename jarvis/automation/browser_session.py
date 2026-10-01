from dataclasses import dataclass
from typing import Optional, Dict, Any
from jarvis.automation import automation_manager

@dataclass
class BrowserSessionRequest:
    logical_account: str
    browser: str
    profile: str

class BrowserSessionManager:
    """
    Manages explicit browser session requests for atomic capabilities.
    Sets the active browser and profile for the browser backend.
    """
    _instance = None
    
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = BrowserSessionManager()
        return cls._instance
        
    def __init__(self):
        self.active_request: Optional[BrowserSessionRequest] = None
        
    def set_active_session(self, request: BrowserSessionRequest):
        self.active_request = request
        
    def clear_session(self):
        self.active_request = None
        
    def get_browser_and_profile(self) -> tuple[Optional[str], Optional[str]]:
        if self.active_request:
            return self.active_request.browser, self.active_request.profile
        return None, None

browser_session_manager = BrowserSessionManager.get()
