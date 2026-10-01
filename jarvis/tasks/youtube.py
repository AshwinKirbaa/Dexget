import time
from typing import Optional
from jarvis.tools.base import ToolResult
from jarvis.agent.tool_registry import ToolRegistry
from .accounts import account_manager
from jarvis.automation.browser_session import BrowserSessionRequest, browser_session_manager

class YouTubePlayTask:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, query: str, account_override: Optional[str] = None, browser_override: Optional[str] = None) -> ToolResult:
        # 1. Resolve account policy
        account = account_manager.get_account_for_task("youtube", account_override)
        target_browser = browser_override or account.browser
        
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
        return ToolResult(True, observation=f"Playing '{query}' on YouTube Music using {account.name} account in {target_browser}.")

