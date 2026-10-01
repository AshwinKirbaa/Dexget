import os
import json
import pytest
from unittest.mock import patch, mock_open

from jarvis.tasks.accounts import AccountManager, AccountProfile
from jarvis.tasks.account_discovery import get_browser_user_data_dir, discover_profiles, verify_profile

def test_account_config_loading(tmp_path):
    config_file = tmp_path / "accounts.json"
    data = {
        "accounts": {
            "college": {"browser": "chrome", "profile_path": "Profile 1"},
            "developer": {"browser": "brave", "profile_path": "Default"}
        },
        "task_accounts": {
            "gmail": "college",
            "github": "developer"
        }
    }
    config_file.write_text(json.dumps(data))
    
    with patch.dict(os.environ, {"JARVIS_ACCOUNT_CONFIG": str(config_file)}):
        manager = AccountManager()
        
        assert "college" in manager.accounts
        assert manager.accounts["college"].browser == "chrome"
        assert manager.accounts["college"].profile_dir == "Profile 1"
        
        assert manager.task_policies["gmail"] == "college"
        assert manager.task_policies["github"] == "developer"

def test_account_resolution_and_task_policy(tmp_path):
    config_file = tmp_path / "accounts.json"
    data = {
        "accounts": {
            "personal": {"browser": "chrome", "profile_path": "Default"},
            "college": {"browser": "chrome", "profile_path": "Profile 1"}
        },
        "task_accounts": {
            "youtube": "personal",
            "gmail": "college"
        }
    }
    config_file.write_text(json.dumps(data))
    
    with patch.dict(os.environ, {"JARVIS_ACCOUNT_CONFIG": str(config_file)}):
        manager = AccountManager()
        
        # Task policy resolution
        youtube_acc = manager.get_account_for_task("youtube")
        assert youtube_acc.name == "personal"
        assert youtube_acc.profile_dir == "Default"
        
        gmail_acc = manager.get_account_for_task("gmail")
        assert gmail_acc.name == "college"
        
        # Explicit override
        override_acc = manager.get_account_for_task("gmail", explicit_override="personal")
        assert override_acc.name == "personal"
        
        # Fallback to default
        unknown_acc = manager.get_account_for_task("unknown_task")
        assert unknown_acc.name == "personal"

def test_profile_discovery_missing():
    # Test missing profile
    assert not verify_profile("chrome", "NonExistentProfileXYZ123")

def test_doctor_output():
    from jarvis.diagnostics import check
    report = check()
    assert "accounts" in report
    assert "task_policies" in report
    
    # Check that youtube maps to something in the default fallback
    if "youtube" in report["task_policies"]:
        assert isinstance(report["task_policies"]["youtube"], str)
