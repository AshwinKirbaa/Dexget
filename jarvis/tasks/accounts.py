import os
import json
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class AccountProfile:
    name: str
    browser: str
    profile_dir: str

class AccountManager:
    def __init__(self):
        self.accounts: Dict[str, AccountProfile] = {}
        self.task_policies: Dict[str, str] = {}
        self.config_path = os.environ.get("JARVIS_ACCOUNT_CONFIG", os.path.join(os.path.expanduser("~"), ".jarvis", "accounts.json"))
        self._load_config()

    def _load_config(self):
        self.accounts.clear()
        self.task_policies.clear()
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    
                for acc_name, acc_data in data.get("accounts", {}).items():
                    self.accounts[acc_name] = AccountProfile(
                        name=acc_name,
                        browser=acc_data.get("browser", "chrome"),
                        profile_dir=acc_data.get("profile_path", "Default") # using profile_path per prompt
                    )
                    
                for task, acc_name in data.get("task_accounts", {}).items():
                    self.task_policies[task] = acc_name
            except Exception as e:
                print(f"Error loading accounts config: {e}")

        # Provide sensible defaults ONLY if no config exists
        if not self.accounts:
            self.accounts["personal"] = AccountProfile("personal", "chrome", "Default")
            self.task_policies["youtube"] = "personal"
            self.task_policies["youtube_music"] = "personal"
            self.task_policies["gmail"] = "personal"
            self.task_policies["general_web"] = "personal"

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = {
            "accounts": {
                name: {"browser": acc.browser, "profile_path": acc.profile_dir}
                for name, acc in self.accounts.items()
            },
            "task_accounts": self.task_policies
        }
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def resolve_account_name(self, name: str) -> Optional[str]:
        if not name: return None
        lower_name = name.lower()
        for k in self.accounts.keys():
            if k.lower() == lower_name:
                return k
        return None

    def get_account_for_task(self, task_name: str, explicit_override: Optional[str] = None) -> AccountProfile:
        # Priority:
        # 1. Explicit override
        if explicit_override:
            actual_name = self.resolve_account_name(explicit_override)
            if actual_name:
                return self.accounts[actual_name]
            
        # 2. Task-specific account
        if task_name in self.task_policies:
            acc_name = self.task_policies[task_name]
            actual_name = self.resolve_account_name(acc_name)
            if actual_name:
                return self.accounts[actual_name]
                
        # 3. Fallback to default/first account
        if self.resolve_account_name("personal"):
            return self.accounts[self.resolve_account_name("personal")]
        elif self.accounts:
            return list(self.accounts.values())[0]
            
        return AccountProfile("default", "chrome", "Default")

    def extract_account_alias(self, command: str) -> tuple[str, Optional[str]]:
        import re
        
        m = re.search(r'\b(?:using|with|in|on)\s+(?:my\s+)?([a-zA-Z0-9_\.@]+)\s+(?:account|profile)\b', command, re.IGNORECASE)
        if m:
            acc_candidate = m.group(1).lower()
            clean_cmd = command[:m.start()] + command[m.end():]
            return clean_cmd.strip(), self.resolve_account_name(acc_candidate) or acc_candidate
                
        m = re.search(r'\b([a-zA-Z0-9_\.@]+)\s+(?:account|profile)\b', command, re.IGNORECASE)
        if m:
            acc_candidate = m.group(1).lower()
            clean_cmd = command[:m.start()] + command[m.end():]
            return clean_cmd.strip(), self.resolve_account_name(acc_candidate) or acc_candidate

        return command, None

account_manager = AccountManager()
