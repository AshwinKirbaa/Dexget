import time
from typing import Optional
from jarvis.tools.base import ToolResult
from jarvis.agent.tool_registry import ToolRegistry
from .accounts import account_manager
from jarvis.automation.browser_session import BrowserSessionRequest, browser_session_manager


def _launch_installed_youtube(registry: ToolRegistry, query: str, app: str, profile: str) -> ToolResult:
    """Call old and new win_youtube_search registrations compatibly."""
    kwargs = {"query": query, "app": app}
    try:
        if "profile" in registry.get("win_youtube_search").parameters:
            kwargs["profile"] = profile
    except Exception:
        pass
    return registry.execute("win_youtube_search", **kwargs)

class YouTubePlayTask:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, query: str, account_override: Optional[str] = None, browser_override: Optional[str] = None) -> ToolResult:
        # 1. Resolve account policy
        account = account_manager.get_account_for_task("youtube", account_override)
        target_browser = browser_override or account.browser

        # Use the installed YouTube app with the selected real Chrome profile.
        # The generic Playwright profile is deliberately isolated and therefore
        # cannot share the user's Google login.
        if self.registry.has("win_youtube_search"):
            if self.registry.has("win_unmute"):
                self.registry.execute("win_unmute")
            direct = _launch_installed_youtube(
                self.registry, query, "YouTube", account.profile_dir
            )
            if direct.success:
                return ToolResult(
                    True,
                    output=direct.output,
                    observation=f"Playing '{query}' in YouTube using {account.name}.",
                )
        
        # 2. Select browser/profile
        req = BrowserSessionRequest(
            logical_account=account.name,
            browser=target_browser,
            profile=account.profile_dir
        )
        browser_session_manager.set_active_session(req)
        
        # 3. Navigate to YouTube
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        res = self.registry.execute("browser_navigate", url=search_url)
        if not res.success:
            browser_session_manager.clear_session()
            return res

        # 4. Observe results
        res = self.registry.execute("browser_observe")
        if not res.success:
            return res
            
        # Extract observation text
        obs_text = res.observation
        
        # 5. Identify result
        import re
        target_id = None
        
        lines = obs_text.split('\n')
        for line in lines:
            if "[node_" in line and "a:" in line:
                if len(line) > 30 and "youtube" not in line.lower() and "shorts" not in line.lower() and "sign in" not in line.lower():
                    match = re.search(r'\[(node_\d+)\]', line)
                    if match:
                        target_id = match.group(1)
                        break
                        
        if not target_id:
            for line in lines:
                if "[node_" in line and query.lower() in line.lower():
                    match = re.search(r'\[(node_\d+)\]', line)
                    if match:
                        target_id = match.group(1)
                        break
                        
        if not target_id:
            return ToolResult(False, observation="Could not identify the correct video in the search results.")
            
        # 6. Click result
        res = self.registry.execute("browser_click", target=target_id)
        if not res.success:
            return res
            
        # 7. Verify playback
        time.sleep(2) # wait for navigation
        res = self.registry.execute("browser_observe")
        if query.lower() not in res.observation.lower() and "watch" not in res.observation.lower():
            return ToolResult(False, observation="Failed to verify video playback.")
            
        return ToolResult(True, observation=f"Playing '{query}' on YouTube using {account.name} account in {target_browser}.")

class YouTubeMusicPlayTask:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, query: str, account_override: Optional[str] = None, browser_override: Optional[str] = None) -> ToolResult:
        account = account_manager.get_account_for_task("youtube_music", account_override)
        target_browser = browser_override or account.browser

        # Prefer the installed YouTube Music PWA. Its Start Menu shortcut
        # contains the user's real Chrome profile and app id, so it preserves
        # sign-in and can open the resolved track directly without remote
        # browser-control consent or a fragile search-result click.
        if self.registry.has("win_youtube_search"):
            # An explicit play request implies audible playback. Clear master
            # mute when the audio tool is available, without changing volume.
            if self.registry.has("win_unmute"):
                self.registry.execute("win_unmute")
            direct = _launch_installed_youtube(
                self.registry, query, "YouTube Music", account.profile_dir
            )
            if direct.success:
                return ToolResult(
                    True,
                    output=direct.output,
                    observation=f"Playing '{query}' in the installed YouTube Music app using {account.name}.",
                )
        
        req = BrowserSessionRequest(
            logical_account=account.name,
            browser=target_browser,
            profile=account.profile_dir
        )
        browser_session_manager.set_active_session(req)
        
        search_url = f"https://music.youtube.com/search?q={query.replace(' ', '+')}"
        res = self.registry.execute("browser_navigate", url=search_url)
        if not res.success:
            browser_session_manager.clear_session()
            return res

        res = self.registry.execute("browser_observe")
        if not res.success:
            return res
            
        obs_text = res.observation
        import re
        target_id = None
        
        lines = obs_text.split('\n')
        for line in lines:
            if "[node_" in line and "a:" in line:
                if len(line) > 15 and "search" not in line.lower() and "sign in" not in line.lower():
                    match = re.search(r'\[(node_\d+)\]', line)
                    if match:
                        target_id = match.group(1)
                        break
                        
        if not target_id:
            for line in lines:
                if "[node_" in line and query.lower() in line.lower():
                    match = re.search(r'\[(node_\d+)\]', line)
                    if match:
                        target_id = match.group(1)
                        break
                        
        if not target_id:
            return ToolResult(False, observation="Could not identify the correct song in the search results.")
            
        res = self.registry.execute("browser_click", target=target_id)
        if not res.success:
            return res
            
        time.sleep(2)
        verify = self.registry.execute("browser_observe")
        if not verify.success:
            return ToolResult(False, observation="The song was selected, but playback could not be verified.")
        verify_text = (verify.observation or "").lower()
        if "music.youtube.com" not in verify_text and "watch" not in verify_text:
            return ToolResult(False, observation="YouTube Music opened, but the selected song did not start playing.")
        return ToolResult(True, observation=f"Playing '{query}' on YouTube Music in {target_browser}.")

