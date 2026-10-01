import os
import json
from unittest.mock import patch

def test_routing():
    from jarvis.router import route
    
    # Mock accounts
    os.environ["JARVIS_ACCOUNT_CONFIG"] = "test_accounts.json"
    with open("test_accounts.json", "w") as f:
        json.dump({
            "accounts": {"personal": {"browser": "chrome", "profile_path": "Default"}},
            "task_accounts": {"youtube": "personal"}
        }, f)
        
    # Reload accounts manager
    from jarvis.tasks.accounts import account_manager
    account_manager._load_config()

    from jarvis_integration import _handle_command
    class MockExecutor:
        on_progress = None
        pending_task = None
    class MockAgent:
        executor = MockExecutor()
        llm_fn = None
        def __init__(self):
            self.registry = __import__("jarvis.agent.tool_registry", fromlist=["ToolRegistry"]).ToolRegistry(None)
            self.command_lock = __import__("threading").Lock()
    agent = MockAgent()
    
    # Test 1: unknown account fails fast
    res = _handle_command(agent, "open gmail using my professional account")
    print("TEST 1:", res.text)
    assert "don't have a 'professional' account" in res.text
    
    # Test 2: explicit account extraction directly on route
    from jarvis.tasks.accounts import account_manager
    cmd, account = account_manager.extract_account_alias("play radhimma in youtube using my personal account")
    res = route(cmd, explicit_account=account)
    print("TEST 2:", res.tool_name, res.tool_args)
    assert res.tool_name == "youtube_play"
    assert res.tool_args["account_override"] == "personal"
    
    # Test 3: no local media fallback for radhimma
    cmd, account = account_manager.extract_account_alias("play radhimma on personal account")
    res = route(cmd, explicit_account=account)
    print("TEST 3:", res.tool_name, res.tool_args)
    assert res.tool_name == "youtube_play"
    assert res.tool_args["account_override"] == "personal"

    # Test 4: local media detection
    cmd, account = account_manager.extract_account_alias("play Dexter S07E02 from Movies")
    res = route(cmd, explicit_account=account)
    print("TEST 4:", res.tool_name, res.tool_args)
    assert res.tool_args["media_title"] == "dexter"
    assert res.tool_args["source"] == "movies"

    # Test 5: youtube music
    cmd, account = account_manager.extract_account_alias("play radhimma in youtube music")
    res = route(cmd, explicit_account=account)
    print("TEST 5:", res.tool_name, res.tool_args)
    assert res.tool_name == "youtube_music_play"
    assert res.tool_args["query"] == "radhimma"

test_routing()
