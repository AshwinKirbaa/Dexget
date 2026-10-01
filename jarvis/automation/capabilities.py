"""
Central Capability Registry for JARVIS.

This module maps the unified, structured capability names requested by the planner
to the underlying tool implementations. The planner ONLY uses these capability names.

Capabilities:
Browser: browser_open browser_navigate browser_back browser_forward browser_refresh browser_observe browser_get_url browser_get_title browser_find browser_click browser_type browser_press browser_scroll browser_select browser_download browser_upload
Windows: windows_open_app windows_close_app windows_focus_window windows_click windows_type windows_press windows_hotkey windows_get_windows windows_observe windows_find_element
System: system_volume system_mute system_brightness system_processes system_shutdown system_restart
Filesystem: file_search file_open file_copy file_move file_delete folder_open
Media: local_media_search local_media_play local_media_stop local_media_pause
"""
from typing import Callable
from jarvis.agent.tool_registry import ToolRegistry
from jarvis.tools.base import Tool, RiskLevel, ToolResult

def register_capabilities(registry: ToolRegistry, confirm_fn: Callable[[str], bool]):
    
    # Imports
    from jarvis.automation import automation_manager
    from jarvis.tools import windows
    from jarvis.tools import filesystem
    
    try:
        from jarvis.tools import local_media
    except ImportError:
        local_media = None

    # --- BROWSER CAPABILITIES ---
    def _browser_open(url: str = None, **kwargs):
        from jarvis.automation.browser_session import browser_session_manager
        browser, profile = browser_session_manager.get_browser_and_profile()
        success = automation_manager.execute_action("browser", "launch_application", url=url, app_name="browser", browser=browser, profile=profile)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=obs.text_representation)

    def _browser_navigate(url: str, **kwargs):
        from jarvis.automation.browser_session import browser_session_manager
        browser, profile = browser_session_manager.get_browser_and_profile()
        success = automation_manager.execute_action("browser", "launch_application", url=url, app_name="browser", browser=browser, profile=profile)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Navigated to {url}.\n{obs.text_representation}")

    def _browser_back(**kwargs):
        return ToolResult(False, error="not_implemented", observation="browser_back not implemented yet")

    def _browser_forward(**kwargs):
        return ToolResult(False, error="not_implemented", observation="browser_forward not implemented yet")

    def _browser_refresh(**kwargs):
        return ToolResult(False, error="not_implemented", observation="browser_refresh not implemented yet")

    def _browser_observe(**kwargs):
        obs = automation_manager.observe("browser")
        return ToolResult(True, observation=obs.text_representation)

    def _browser_get_url(**kwargs):
        obs = automation_manager.observe("browser")
        return ToolResult(True, observation=f"URL: {obs.url}")

    def _browser_get_title(**kwargs):
        obs = automation_manager.observe("browser")
        return ToolResult(True, observation=f"Title: {obs.page_title}")

    def _browser_find(query: str, **kwargs):
        return ToolResult(False, error="not_implemented", observation="browser_find not implemented yet")

    def _browser_click(target: str, **kwargs):
        success = automation_manager.execute_action("browser", "click", target=target)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Clicked {target}.\n{obs.text_representation}")

    def _browser_type(target: str, text: str, **kwargs):
        success = automation_manager.execute_action("browser", "type", target=target, text=text)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Typed '{text}' into {target}.\n{obs.text_representation}")

    def _browser_press(key_combo: str, **kwargs):
        success = automation_manager.execute_action("browser", "press", key_combo=key_combo)
        obs = automation_manager.observe("browser")
        return ToolResult(success, observation=f"Pressed {key_combo}.\n{obs.text_representation}")

    def _browser_scroll(direction: str, amount: int = 1, **kwargs):
        success = automation_manager.execute_action("browser", "scroll", direction=direction, amount=amount)
        return ToolResult(success, observation=f"Scrolled {direction}")

    def _browser_select(target: str, option: str, **kwargs):
        return ToolResult(False, error="not_implemented", observation="browser_select not implemented yet")
        
    def _browser_download(url: str, **kwargs):
        return ToolResult(False, error="not_implemented", observation="browser_download not implemented yet")
        
    def _browser_upload(target: str, file_path: str, **kwargs):
        return ToolResult(False, error="not_implemented", observation="browser_upload not implemented yet")


    # --- WINDOWS CAPABILITIES ---
    def _windows_open_app(app_name: str, **kwargs):
        return windows.open_application(app_name)

    def _windows_close_app(app_name: str, **kwargs):
        return windows.close_application(app_name)

    def _windows_focus_window(app_name: str, **kwargs):
        success = automation_manager.execute_action("windows", "focus_application", app_name=app_name)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=obs.text_representation)

    def _windows_click(target: str, **kwargs):
        success = automation_manager.execute_action("windows", "click", target=target)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=obs.text_representation)

    def _windows_type(target: str, text: str, **kwargs):
        success = automation_manager.execute_action("windows", "type", target=target, text=text)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=obs.text_representation)

    def _windows_press(key_combo: str, **kwargs):
        success = automation_manager.execute_action("windows", "press", key_combo=key_combo)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=obs.text_representation)

    def _windows_hotkey(key_combo: str, **kwargs):
        success = automation_manager.execute_action("windows", "press", key_combo=key_combo)
        obs = automation_manager.observe("windows")
        return ToolResult(success, observation=obs.text_representation)

    def _windows_get_windows(**kwargs):
        return ToolResult(False, error="not_implemented", observation="windows_get_windows not implemented yet")

    def _windows_observe(**kwargs):
        obs = automation_manager.observe("windows")
        return ToolResult(True, observation=obs.text_representation)

    def _windows_find_element(query: str, **kwargs):
        return ToolResult(False, error="not_implemented", observation="windows_find_element not implemented yet")

    # --- SYSTEM CAPABILITIES ---
    def _system_volume(percent: int, **kwargs):
        return windows.volume_set(percent)

    def _system_mute(**kwargs):
        return windows.mute_audio()

    def _system_brightness(percent: int, **kwargs):
        return windows.set_brightness(percent)

    def _system_processes(**kwargs):
        return ToolResult(False, error="not_implemented", observation="system_processes not implemented yet")

    def _system_shutdown(**kwargs):
        return windows.shutdown_pc()

    def _system_restart(**kwargs):
        return windows.restart_pc()

    # --- FILESYSTEM CAPABILITIES ---
    def _file_search(root: str, name_contains: str, **kwargs):
        return filesystem.search_files(root, name_contains)

    def _file_open(path: str, **kwargs):
        return filesystem.read_file(path)

    def _file_copy(source: str, destination: str, **kwargs):
        return filesystem.copy_file(source, destination)

    def _file_move(source: str, destination: str, **kwargs):
        return filesystem.move_file(source, destination)

    def _file_delete(path: str, **kwargs):
        return filesystem.delete_file(path)

    def _folder_open(path: str, **kwargs):
        return filesystem.list_directory(path)

    # --- MEDIA CAPABILITIES ---
    def _local_media_search(query: str, **kwargs):
        return ToolResult(False, error="not_implemented", observation="local_media_search not implemented yet")

    def _local_media_play(media_title: str, season: int = None, episode: int = None, source: str = "movies folder", **kwargs):
        if local_media:
            return local_media.play_local_media(media_title, season, episode, source)
        return ToolResult(False, error="not_installed", observation="local_media module not found")

    def _local_media_stop(**kwargs):
        return ToolResult(False, error="not_implemented", observation="local_media_stop not implemented yet")

    def _local_media_pause(**kwargs):
        return ToolResult(False, error="not_implemented", observation="local_media_pause not implemented yet")

    
    # BROWSER REGISTRATIONS
    registry.register(Tool("browser_open", "Open browser.", {"url": {"type": "str", "required": False}}, RiskLevel.LOW, _browser_open, "browser"), overwrite=True)
    registry.register(Tool("browser_navigate", "Navigate to URL.", {"url": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _browser_navigate, "browser"), overwrite=True)
    registry.register(Tool("browser_back", "Go back in browser.", {}, RiskLevel.LOW, _browser_back, "browser"), overwrite=True)
    registry.register(Tool("browser_forward", "Go forward in browser.", {}, RiskLevel.LOW, _browser_forward, "browser"), overwrite=True)
    registry.register(Tool("browser_refresh", "Refresh browser page.", {}, RiskLevel.LOW, _browser_refresh, "browser"), overwrite=True)
    registry.register(Tool("browser_observe", "Observe browser page.", {}, RiskLevel.LOW, _browser_observe, "browser"), overwrite=True)
    registry.register(Tool("browser_get_url", "Get current URL.", {}, RiskLevel.LOW, _browser_get_url, "browser"), overwrite=True)
    registry.register(Tool("browser_get_title", "Get page title.", {}, RiskLevel.LOW, _browser_get_title, "browser"), overwrite=True)
    registry.register(Tool("browser_find", "Find element on page.", {"query": {"type": "str", "required": True}}, RiskLevel.LOW, _browser_find, "browser"), overwrite=True)
    registry.register(Tool("browser_click", "Click element.", {"target": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _browser_click, "browser"), overwrite=True)
    registry.register(Tool("browser_type", "Type text into element.", {"target": {"type": "str", "required": True}, "text": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _browser_type, "browser"), overwrite=True)
    registry.register(Tool("browser_press", "Press key in browser.", {"key_combo": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _browser_press, "browser"), overwrite=True)
    registry.register(Tool("browser_scroll", "Scroll page.", {"direction": {"type": "str", "required": True}, "amount": {"type": "int", "required": False}}, RiskLevel.LOW, _browser_scroll, "browser"), overwrite=True)
    registry.register(Tool("browser_select", "Select option from dropdown.", {"target": {"type": "str", "required": True}, "option": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _browser_select, "browser"), overwrite=True)
    registry.register(Tool("browser_download", "Download file.", {"url": {"type": "str", "required": True}}, RiskLevel.LOW, _browser_download, "browser"), overwrite=True)
    registry.register(Tool("browser_upload", "Upload file.", {"target": {"type": "str", "required": True}, "file_path": {"type": "str", "required": True}}, RiskLevel.LOW, _browser_upload, "browser"), overwrite=True)

    # WINDOWS REGISTRATIONS
    registry.register(Tool("windows_open_app", "Launch application.", {"app_name": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _windows_open_app, "windows"), overwrite=True)
    registry.register(Tool("windows_close_app", "Close application.", {"app_name": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _windows_close_app, "windows"), overwrite=True)
    registry.register(Tool("windows_focus_window", "Focus application window.", {"app_name": {"type": "str", "required": True}}, RiskLevel.LOW, _windows_focus_window, "windows"), overwrite=True)
    registry.register(Tool("windows_click", "Click element in active window.", {"target": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _windows_click, "windows"), overwrite=True)
    registry.register(Tool("windows_type", "Type text into active window.", {"target": {"type": "str", "required": True}, "text": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _windows_type, "windows"), overwrite=True)
    registry.register(Tool("windows_press", "Press key.", {"key_combo": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _windows_press, "windows"), overwrite=True)
    registry.register(Tool("windows_hotkey", "Press hotkey.", {"key_combo": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _windows_hotkey, "windows"), overwrite=True)
    registry.register(Tool("windows_get_windows", "List active windows.", {}, RiskLevel.LOW, _windows_get_windows, "windows"), overwrite=True)
    registry.register(Tool("windows_observe", "Observe active window elements.", {}, RiskLevel.LOW, _windows_observe, "windows"), overwrite=True)
    registry.register(Tool("windows_find_element", "Find UI element.", {"query": {"type": "str", "required": True}}, RiskLevel.LOW, _windows_find_element, "windows"), overwrite=True)

    # SYSTEM REGISTRATIONS
    registry.register(Tool("system_volume", "Set system volume.", {"percent": {"type": "int", "required": True}}, RiskLevel.LOW, _system_volume, "system"), overwrite=True)
    registry.register(Tool("system_mute", "Mute system audio.", {}, RiskLevel.LOW, _system_mute, "system"), overwrite=True)
    registry.register(Tool("system_brightness", "Set screen brightness.", {"percent": {"type": "int", "required": True}}, RiskLevel.LOW, _system_brightness, "system"), overwrite=True)
    registry.register(Tool("system_processes", "List system processes.", {}, RiskLevel.LOW, _system_processes, "system"), overwrite=True)
    registry.register(Tool("system_shutdown", "Shutdown computer.", {}, RiskLevel.DESTRUCTIVE, _system_shutdown, "system"), overwrite=True)
    registry.register(Tool("system_restart", "Restart computer.", {}, RiskLevel.HIGH, _system_restart, "system"), overwrite=True)

    # FILESYSTEM REGISTRATIONS
    registry.register(Tool("file_search", "Search for files.", {"root": {"type": "str", "required": True}, "name_contains": {"type": "str", "required": True}}, RiskLevel.LOW, _file_search, "filesystem"), overwrite=True)
    registry.register(Tool("file_open", "Read a file.", {"path": {"type": "str", "required": True}}, RiskLevel.LOW, _file_open, "filesystem"), overwrite=True)
    registry.register(Tool("file_copy", "Copy a file.", {"source": {"type": "str", "required": True}, "destination": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _file_copy, "filesystem"), overwrite=True)
    registry.register(Tool("file_move", "Move a file.", {"source": {"type": "str", "required": True}, "destination": {"type": "str", "required": True}}, RiskLevel.MEDIUM, _file_move, "filesystem"), overwrite=True)
    registry.register(Tool("file_delete", "Delete a file.", {"path": {"type": "str", "required": True}}, RiskLevel.HIGH, _file_delete, "filesystem"), overwrite=True)
    registry.register(Tool("folder_open", "List directory contents.", {"path": {"type": "str", "required": True}}, RiskLevel.LOW, _folder_open, "filesystem"), overwrite=True)

    # MEDIA REGISTRATIONS
    registry.register(Tool("local_media_search", "Search for local media.", {"query": {"type": "str", "required": True}}, RiskLevel.LOW, _local_media_search, "media"), overwrite=True)
    registry.register(Tool("local_media_play", "Play local media.", {"media_title": {"type": "str", "required": False}, "season": {"type": "int", "required": False}, "episode": {"type": "int", "required": False}, "source": {"type": "str", "required": False}}, RiskLevel.LOW, _local_media_play, "media"), overwrite=True)
    registry.register(Tool("local_media_stop", "Stop media playback.", {}, RiskLevel.LOW, _local_media_stop, "media"), overwrite=True)
    registry.register(Tool("local_media_pause", "Pause media playback.", {}, RiskLevel.LOW, _local_media_pause, "media"), overwrite=True)
