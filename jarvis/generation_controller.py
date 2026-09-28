import threading
from typing import List, Callable, Optional, Any

class GenerationController:
    def __init__(self, on_gui_update: Optional[Callable[[str], None]] = None):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._partial_text: List[str] = []
        self._active_stream: Any = None
        self._is_active = False
        self.on_gui_update = on_gui_update

    def start(self):
        with self._lock:
            self._stop_event.clear()
            self._partial_text.clear()
            self._is_active = True
            
    def stop(self):
        with self._lock:
            self._stop_event.set()
            self._is_active = False
            if self._active_stream:
                try:
                    self._active_stream.close()
                except Exception:
                    pass
            if self.on_gui_update:
                try:
                    self.on_gui_update("Generation stopped.")
                except:
                    pass

    def finish(self):
        with self._lock:
            self._is_active = False
            if self._active_stream:
                try:
                    self._active_stream.close()
                except Exception:
                    pass

    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def attach_stream(self, stream: Any):
        with self._lock:
            self._active_stream = stream

    def detach_stream(self):
        with self._lock:
            self._active_stream = None

    def append(self, token: str):
        if self.should_stop():
            return
        with self._lock:
            self._partial_text.append(token)

    def partial_text(self) -> str:
        with self._lock:
            return "".join(self._partial_text)

# Global instance for easy import and usage
generation_controller = GenerationController()
