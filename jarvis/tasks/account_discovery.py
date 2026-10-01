import os
import json
from typing import Dict, List, Optional

def get_browser_user_data_dir(browser: str) -> Optional[str]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        
    if browser == "chrome":
        path = os.path.join(local_app_data, "Google", "Chrome", "User Data")
    elif browser == "brave":
        path = os.path.join(local_app_data, "BraveSoftware", "Brave-Browser", "User Data")
    else:
        return None
        
    return path if os.path.exists(path) else None

def discover_profiles(browser: str) -> List[Dict[str, str]]:
    """
    Returns a list of discovered profiles for the given browser.
    Each profile is a dict: {"dir": "Default", "name": "Person 1", "email": "user@example.com"}
    """
    user_data_dir = get_browser_user_data_dir(browser)
    if not user_data_dir:
        return []
        
    local_state_path = os.path.join(user_data_dir, "Local State")
    profiles = []
    
    if os.path.exists(local_state_path):
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
                
            info_cache = local_state.get("profile", {}).get("info_cache", {})
            for profile_dir, info in info_cache.items():
                name = info.get("name", "")
                email = info.get("user_name", "")
                profiles.append({
                    "dir": profile_dir,
                    "name": name,
                    "email": email
                })
        except Exception:
            pass
            
    # Fallback if Local State fails or is empty: just look for directories
    if not profiles:
        for item in os.listdir(user_data_dir):
            if item == "Default" or item.startswith("Profile "):
                if os.path.isdir(os.path.join(user_data_dir, item)):
                    profiles.append({
                        "dir": item,
                        "name": item,
                        "email": ""
                    })
                    
    return profiles

def verify_profile(browser: str, profile_dir: str) -> bool:
    user_data_dir = get_browser_user_data_dir(browser)
    if not user_data_dir:
        return False
    return os.path.isdir(os.path.join(user_data_dir, profile_dir))
