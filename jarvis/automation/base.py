from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class Observation:
    text_representation: str
    ui_elements: List[Dict[str, Any]]
    active_window: Optional[str] = None
    focused_element: Optional[str] = None
    url: Optional[str] = None
    page_title: Optional[str] = None

class AutomationBackend(ABC):
    """
    Abstract interface for automation backends.
    Allows JARVIS to control Windows and Browser without being coupled
    to a specific implementation like UFO or Browser Use.
    """
    
    @abstractmethod
    def observe(self, **kwargs) -> Observation:
        """Observe the current state of the application/desktop."""
        pass

    @abstractmethod
    def click(self, target: str, **kwargs) -> bool:
        """Click on an element."""
        pass

    @abstractmethod
    def type(self, target: str, text: str, **kwargs) -> bool:
        """Type text into an element."""
        pass

    @abstractmethod
    def press(self, key_combo: str, **kwargs) -> bool:
        """Press a keyboard combination."""
        pass
        
    @abstractmethod
    def scroll(self, direction: str, amount: int = 1, **kwargs) -> bool:
        """Scroll the current view."""
        pass

    @abstractmethod
    def launch_application(self, app_name: str, **kwargs) -> bool:
        """Launch an application."""
        pass
        
    @abstractmethod
    def focus_application(self, app_name: str, **kwargs) -> bool:
        """Bring an application to the foreground."""
        pass
        
    @abstractmethod
    def verify_action(self, expected_condition: str, **kwargs) -> bool:
        """Verify that an action had the desired effect."""
        pass
        
    @abstractmethod
    def cancel(self):
        """Cancel any ongoing automation."""
        pass
