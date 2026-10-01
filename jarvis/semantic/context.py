class ConversationalContext:
    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.history = []
        self.current_app = None
        self.current_url = None

    def add_interaction(self, user_text: str, action_taken: str):
        self.history.append({"user": user_text, "action": action_taken})
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def set_current_app(self, app_name: str):
        self.current_app = app_name

    def set_current_url(self, url: str):
        self.current_url = url

    def clear(self):
        self.history.clear()
        self.current_app = None
        self.current_url = None

    def format_for_prompt(self) -> str:
        lines = []
        if self.current_app:
            lines.append(f"Current Application: {self.current_app}")
        if self.current_url:
            lines.append(f"Current URL: {self.current_url}")
        
        if self.history:
            lines.append("Recent History:")
            for item in self.history:
                lines.append(f"  User: {item['user']}")
                lines.append(f"  Jarvis: {item['action']}")
                
        return "\n".join(lines)

# Global singleton for simplicity
context = ConversationalContext()
