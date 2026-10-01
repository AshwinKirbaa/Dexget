import re
from typing import Optional, Tuple
from jarvis.router import RouteResult, RouteType, ToolCall, _browser, _windows, _fast, _search, _fast_multi
from jarvis.semantic.classifier import classify_intent, Intent

def route_natural_language(command: str, llm_fn) -> Optional[RouteResult]:
    """
    Fast, local natural language semantic router.
    Calls Tier 1 local model via classify_intent to produce a structured JSON intent.
    Routes that intent to a specific task handler.
    """
    structured = classify_intent(command, llm_fn)
    
    if structured.intent == Intent.YOUTUBE_PLAY:
        return RouteResult(
            route_type=RouteType.TASK, 
            tool_name="youtube_play", 
            tool_args={"query": structured.query, "account_override": structured.account},
            label=f"Playing '{structured.query}' on YouTube"
        )
        
    elif structured.intent == Intent.LOCAL_MEDIA_PLAY:
        return RouteResult(
            route_type=RouteType.WINDOWS, 
            tool_name="local_media_play", 
            tool_args={"media_title": structured.query, "source": structured.source or "movies folder"},
            label=f"Playing '{structured.query}' locally"
        )
        
    elif structured.intent == Intent.OPEN_GMAIL:
        return RouteResult(
            route_type=RouteType.TASK,
            tool_name="web_open",
            tool_args={"url": "https://mail.google.com", "site_name": "gmail", "account_override": structured.account},
            label="Opening Gmail"
        )
        
    elif structured.intent == Intent.WINDOWS_APP_OPEN:
        app = structured.query or "chrome"
        return RouteResult(
            route_type=RouteType.WINDOWS,
            tool_name="windows_open_app",
            tool_args={"app_name": app},
            label=f"Opening {app}"
        )
        
    elif structured.intent == Intent.BROWSER_SEARCH:
        query = structured.query or ""
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return RouteResult(
            route_type=RouteType.BROWSER,
            tool_name="browser_open",
            tool_args={"url": url},
            label=f"Searching for '{query}'"
        )
        
    elif structured.intent == Intent.SYSTEM_COMMAND:
        # Fallback to general agent for system commands if deterministic missed it
        return None

    # New system intents:
    elif structured.intent == Intent.WINDOWS_WIFI:
        if structured.action == "ENABLE": return _fast("sys_wifi_enable", {}, "Enabling Wi-Fi")
        elif structured.action == "DISABLE": return _fast("sys_wifi_disable", {}, "Disabling Wi-Fi")
        elif structured.action == "CONNECT": return _fast("sys_wifi_connect", {"ssid": structured.query or ""}, f"Connecting to Wi-Fi {structured.query}")
        return _fast("sys_wifi_status", {}, "Getting Wi-Fi status")

    elif structured.intent == Intent.WINDOWS_BLUETOOTH:
        if structured.action == "ENABLE": return _fast("sys_bluetooth_enable", {}, "Enabling Bluetooth")
        elif structured.action == "DISABLE": return _fast("sys_bluetooth_disable", {}, "Disabling Bluetooth")
        elif structured.action == "TOGGLE": return _fast("sys_bluetooth_toggle", {}, "Toggling Bluetooth")
        elif structured.action == "DISCOVER": return _fast("sys_bluetooth_discover", {}, "Discovering Bluetooth devices")
        elif structured.action == "CONNECT": return _fast("sys_bluetooth_connect", {"device_name": structured.query or ""}, f"Connecting to {structured.query}")
        elif structured.action == "DISCONNECT": return _fast("sys_bluetooth_disconnect", {"device_name": structured.query or ""}, f"Disconnecting {structured.query}")
        return _fast("sys_bluetooth_status", {}, "Getting Bluetooth status")

    elif structured.intent == Intent.WINDOWS_BRIGHTNESS:
        if structured.action == "SET": return _fast("sys_brightness_set", {"percent": structured.value}, f"Setting brightness to {structured.value}")
        return _fast("sys_brightness_get", {}, "Getting brightness")

    elif structured.intent == Intent.WINDOWS_VOLUME:
        if structured.action == "SET": return _fast("sys_volume_set", {"percent": structured.value}, f"Setting volume to {structured.value}")
        elif structured.action == "MUTE": return _fast("sys_volume_mute", {}, "Muting volume")
        elif structured.action == "UNMUTE": return _fast("sys_volume_unmute", {}, "Unmuting volume")
        return _fast("sys_volume_get", {}, "Getting volume")

    elif structured.intent == Intent.WINDOWS_AUDIO_OUTPUT:
        if structured.action == "SET": return _fast("sys_audio_output_set", {"device_name": structured.query}, f"Setting audio to {structured.query}")
        return _fast("sys_audio_output_get", {}, "Getting audio output")

    elif structured.intent == Intent.WINDOWS_AIRPLANE_MODE:
        if structured.action == "ENABLE": return _fast("sys_airplane_mode_enable", {}, "Enabling Airplane Mode")
        elif structured.action == "DISABLE": return _fast("sys_airplane_mode_disable", {}, "Disabling Airplane Mode")
        return _fast("sys_airplane_mode_status", {}, "Getting Airplane Mode status")

    elif structured.intent == Intent.WINDOWS_ENERGY_SAVER:
        if structured.action == "ENABLE": return _fast("sys_energy_saver_enable", {}, "Enabling Energy Saver")
        elif structured.action == "DISABLE": return _fast("sys_energy_saver_disable", {}, "Disabling Energy Saver")
        return _fast("sys_energy_saver_status", {}, "Getting Energy Saver status")

    elif structured.intent == Intent.WINDOWS_ACCESSIBILITY:
        return _fast("sys_accessibility_open", {}, "Opening Accessibility")

    elif structured.intent == Intent.WINDOWS_QUICK_SETTINGS:
        return _fast("sys_quick_settings_open", {}, "Opening Quick Settings")

    # Unknown -> fallback to Agent Planner (Tier 2)
    return None
