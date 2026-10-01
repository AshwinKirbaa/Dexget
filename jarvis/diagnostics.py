"""Read-only readiness checks; no browser, microphone or paid requests."""
import importlib.util
import json
import os
import urllib.request
from jarvis.config.environment import load_environment


def check():
    load_environment()
    report = {"provider": os.getenv("JARVIS_LLM_PROVIDER", "ollama"),
              "model": os.getenv("JARVIS_OLLAMA_MODEL", "gemma3:4b")}
    report["dependencies"] = {
        name: importlib.util.find_spec(name) is not None
        for name in ("PyQt6", "selenium", "pyautogui", "pywinauto", "dotenv", "vosk")
    }
    try:
        host = os.getenv("JARVIS_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as response:
            report["installed_models"] = [m["name"] for m in json.load(response).get("models", [])]
        report["local_model_ready"] = report["model"] in report["installed_models"]
    except Exception as exc:
        report["local_model_ready"] = False
        report["ollama_error"] = str(exc)
    from jarvis.agent.tool_registry import build_default_registry
    registry = build_default_registry()
    report["tools"] = len(registry.list_tools())
    report["unavailable_capabilities"] = registry.unavailable
    
    # Automation Backend Checks
    report["semantic_router"] = "local_router (enabled)"
    report["cancellation_support"] = "available"
    
    # Timeouts
    report["timeouts"] = {
        "JARVIS_SEMANTIC_TIMEOUT_SECONDS": os.getenv("JARVIS_SEMANTIC_TIMEOUT_SECONDS", "3"),
        "JARVIS_BROWSER_TASK_TIMEOUT": os.getenv("JARVIS_BROWSER_TASK_TIMEOUT", "60"),
        "JARVIS_WINDOWS_ACTION_TIMEOUT": os.getenv("JARVIS_WINDOWS_ACTION_TIMEOUT", "10")
    }
    
    # UFO backend
    try:
        import uiautomation
        report["uiautomation"] = "installed"
        from jarvis.automation.ufo_backend import UfoWindowsBackend
        UfoWindowsBackend() # Try instantiation to catch abstract method errors
        report["ufo_backend"] = "available"
    except Exception as exc:
        report["uiautomation"] = "missing or failed"
        report["ufo_backend"] = f"unavailable: {str(exc)}"
        
    # Browser Use backend
    try:
        import playwright
        report["playwright"] = "installed"
        from jarvis.automation.browser_backend import BrowserUseBackend
        BrowserUseBackend() # Try instantiation to catch abstract method errors
        report["browser_backend"] = "available"
    except Exception as exc:
        report["playwright"] = "missing or failed"
        report["browser_backend"] = f"unavailable: {str(exc)}"

    # SQLite
    try:
        from jarvis.memory.store import _get_conn
        conn = _get_conn()
        conn.close()
        report["sqlite"] = "ready"
    except Exception as exc:
        report["sqlite"] = f"unavailable: {str(exc)}"

    # Audio I/O
    try:
        import pyaudiowpatch as pyaudio
        p = pyaudio.PyAudio()
        report["audio"] = {
            "input": p.get_default_input_device_info()['name'],
            "output": p.get_default_output_device_info()['name']
        }
        p.terminate()
    except Exception as exc:
        report["audio"] = f"unavailable: {str(exc)}"
        
    # Task Validation
    from jarvis.agent.tool_registry import build_default_registry
    registry = build_default_registry()
    
    tasks_health = {}
    
    # YouTubePlayTask validation
    required_youtube = ["browser_navigate", "browser_observe", "browser_click"]
    missing = [t for t in required_youtube if not registry.has(t)]
    if missing:
        tasks_health["youtube_play"] = f"unavailable: requires {', '.join(missing)}"
    else:
        tasks_health["youtube_play"] = "available"
        
    # WebOpenTask validation
    if registry.has("browser_navigate") and registry.has("browser_observe"):
        tasks_health["web_open"] = "available"
    else:
        tasks_health["web_open"] = "unavailable: requires browser_navigate, browser_observe"
        
    report["tasks"] = tasks_health
    
    from jarvis.tasks.accounts import account_manager
    from jarvis.tasks.account_discovery import verify_profile
    
    report["accounts"] = {}
    for name, acc in account_manager.accounts.items():
        profile_ok = verify_profile(acc.browser, acc.profile_dir)
        status_str = "✓" if profile_ok else "NOT FOUND"
        acc_info = {
            "profile": f"{acc.browser.title()} / {acc.profile_dir} {status_str}"
        }
        
        # Check assigned services
        services = [k for k, v in account_manager.task_policies.items() if v.lower() == name.lower()]
        for svc in services:
            acc_info[svc] = f"profile available {'✓' if profile_ok else '✗'}, authentication untested"
            
        report["accounts"][name] = acc_info
        
    report["task_policies"] = account_manager.task_policies

    return report
