from jarvis.automation.manager import AutomationManager

def verify_application_open(manager: AutomationManager, app_name: str) -> bool:
    obs = manager.observe("windows")
    return app_name.lower() in obs.text_representation.lower()

def verify_window_focused(manager: AutomationManager, app_name: str) -> bool:
    obs = manager.observe("windows")
    return app_name.lower() in obs.active_window.lower()

def verify_url(manager: AutomationManager, url_fragment: str) -> bool:
    if not manager.browser_backend: return False
    return url_fragment.lower() in manager.browser_backend.state.get("current_url", "").lower()

def verify_page_content(manager: AutomationManager, text: str) -> bool:
    obs = manager.observe("browser")
    return text.lower() in obs.text_representation.lower()

def verify_element_visible(manager: AutomationManager, target_id: str) -> bool:
    obs = manager.observe("browser")
    return any(el.get("id") == target_id for el in obs.ui_elements)

def verify_text_present(manager: AutomationManager, backend: str, text: str) -> bool:
    obs = manager.observe(backend)
    return text.lower() in obs.text_representation.lower()

def verify_service_authentication(service: str, observation) -> dict:
    """
    Checks if a given service is authenticated or requires authentication based on an Observation.
    Returns:
        {"status": "AUTHENTICATED" | "AUTHENTICATION_REQUIRED" | "UNKNOWN", "service": service}
    """
    text = observation.text_representation.lower()
    url = (observation.url or "").lower()
    
    if service.lower() == "gmail":
        if "accounts.google.com" in url or "signin" in url:
            auth_indicators = ["sign in", "email or phone", "forgot email", "create account", "next"]
            if any(ind in text for ind in auth_indicators):
                return {"status": "AUTHENTICATION_REQUIRED", "service": "gmail"}
                
        if "mail.google.com" in url:
            if "inbox" in text or "compose" in text or "starred" in text:
                return {"status": "AUTHENTICATED", "service": "gmail"}
                
        # Fallback UI indicators
        if "sign in" in text and "create account" in text:
            return {"status": "AUTHENTICATION_REQUIRED", "service": "gmail"}

    return {"status": "UNKNOWN", "service": service}

def verify_browser_profile(manager: AutomationManager) -> dict:
    if not manager.browser_backend:
        return {"status": "NO_BACKEND"}
    state = getattr(manager.browser_backend, "connection_state", {})
    return {
        "profile_exists": state.get("profile_exists", False),
        "chrome_running": state.get("chrome_running", False),
        "remote_debug_enabled": state.get("remote_debug_enabled", False),
        "session_attached": state.get("session_attached", False)
    }

def verify_service_page(manager: AutomationManager) -> dict:
    obs = manager.observe("browser")
    return {
        "url": obs.url,
        "title": obs.page_title,
        "auth_state": verify_service_authentication("gmail", obs)["status"]
    }
