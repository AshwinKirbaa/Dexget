import time
from typing import Optional
from jarvis.tools.base import ToolResult
from jarvis.agent.tool_registry import ToolRegistry
from .accounts import account_manager
from jarvis.automation.browser_session import BrowserSessionRequest, browser_session_manager

SERVICE_URLS = {
    "gmail": "https://mail.google.com/",
    "youtube": "https://www.youtube.com/",
    "youtube music": "https://music.youtube.com/",
    "github": "https://github.com/",
    "google": "https://www.google.com/",
    "google drive": "https://drive.google.com/",
    "google docs": "https://docs.google.com/",
    "google calendar": "https://calendar.google.com/"
}

class WebOpenTask:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, url: str, site_name: str, account_override: Optional[str] = None, browser_override: Optional[str] = None) -> ToolResult:
        # 1. Resolve service
        target_url = url
        if site_name.lower() in SERVICE_URLS:
            target_url = SERVICE_URLS[site_name.lower()]

        # 2. Resolve account
        account = account_manager.get_account_for_task(site_name.lower(), account_override)
        
        # 3. Resolve browser/profile
        target_browser = browser_override or account.browser
        
        # We need a function to verify profile and get state, but let's first configure the session
        req = BrowserSessionRequest(
            logical_account=account.name,
            browser=target_browser,
            profile=account.profile_dir
        )
        browser_session_manager.set_active_session(req)
        
        # 4 & 5. Acquire browser session and navigate
        res = self.registry.execute("browser_navigate", url=target_url)
        if not res.success:
            browser_session_manager.clear_session()
            error_msg = f"{target_browser.capitalize()} {account.profile_dir} profile was found, but I couldn't attach to that running session." if target_browser.lower() == "chrome" else f"{target_browser.capitalize()} {account.name} profile was found, but the browser session did not become controllable."
            return ToolResult(False, error="session_failed", observation=error_msg)
            
        time.sleep(2)
        
        # 6. Observe current page
        from jarvis.automation import automation_manager
        from jarvis.automation.verifier import verify_service_authentication
        
        try:
            obs = automation_manager.observe("browser")
            
            # 7 & 8. Verify service and authentication
            auth_status = verify_service_authentication(site_name, obs)
            
            # 9. Report result
            if auth_status["status"] == "AUTHENTICATION_REQUIRED":
                return ToolResult(
                    True, 
                    observation=f"Opened {site_name} in {target_browser} using {account.name} profile, but it requires login. Please sign in."
                )
        except Exception as e:
            # External browser fallback etc
            pass
            
        obs_res = self.registry.execute("browser_observe")
        return ToolResult(True, observation=f"Opened {site_name} in {target_browser} using {account.name} profile.\n{obs_res.observation if obs_res.success else ''}")

