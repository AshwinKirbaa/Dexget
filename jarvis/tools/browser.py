import os
import urllib.parse
from typing import Optional
from jarvis.tools.base import RiskLevel, Tool, ToolResult

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException, NoSuchWindowException, InvalidSessionIdException

DEFAULT_WAIT_SECONDS = 10

_BY_MAP = {
    "css": By.CSS_SELECTOR, "xpath": By.XPATH, "id": By.ID,
    "name": By.NAME, "text": By.LINK_TEXT, "tag": By.TAG_NAME,
}

from jarvis.tools.browser_engine import _engine as browser_engine, ContextMode, BrowserTabManager, BrowserContextFactory

class LegacyBrowserAdapter:
    def __init__(self):
        self.factory = BrowserContextFactory()

    def get_driver(self):
        ctx = self.factory.get_context(ContextMode.DEFAULT_ACCOUNT)
        return ctx.driver

    def new_tab(self, url: Optional[str] = None):
        driver = self.get_driver()
        tabs = BrowserTabManager(driver)
        tabs.create_tab(url)

    def recover(self):
        # Engine recovers context automatically via get_context
        pass

    def close(self):
        if ContextMode.DEFAULT_ACCOUNT in self.factory._contexts:
            try:
                self.factory._contexts[ContextMode.DEFAULT_ACCOUNT].driver.quit()
            except:
                pass
            del self.factory._contexts[ContextMode.DEFAULT_ACCOUNT]

_manager = LegacyBrowserAdapter()



def _locator(by: str, selector: str):
    return _BY_MAP.get(by, By.CSS_SELECTOR), selector


def browser_open(url: str, new_tab: bool = True) -> ToolResult:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        
    try:
        if new_tab:
            _manager.new_tab(url)
        else:
            driver = _manager.get_driver()
            driver.get(url)
        return ToolResult(True, output=url, observation=f"Opened {url} in browser.")
    except Exception as exc:
        _manager.recover()
        return ToolResult(False, error=str(exc), observation="The browser window was closed or invalid. Session has been recovered. Please try again.")

def open_url(url: str) -> ToolResult:
    return browser_open(url, new_tab=True)

def browser_navigate(url: str) -> ToolResult:
    return browser_open(url, new_tab=False)

def browser_back() -> ToolResult:
    try:
        _manager.get_driver().back()
        return ToolResult(True, observation="Navigated back")
    except Exception as e:
        return ToolResult(False, error=str(e), observation=f"Failed to navigate back: {str(e)}")

def browser_refresh() -> ToolResult:
    try:
        _manager.get_driver().refresh()
        return ToolResult(True, observation="Refreshed page")
    except Exception as e:
        return ToolResult(False, error=str(e), observation=f"Failed to refresh: {str(e)}")

def browser_find_element(by: str, selector: str) -> ToolResult:
    # Deprecated in favor of observe, but keep for compatibility
    return ToolResult(True, observation="Please use browser_observe to see the whole page instead.")

def browser_click(selector: str, by: str = None) -> ToolResult:
    res = browser_engine.execute_task("click", target=selector, params={"by": by})
    if res.get("success"):
        return ToolResult(True, observation=f"Clicked element {selector!r}")
    return ToolResult(False, error=res.get("message"), observation=f"Could not click {selector!r}: {res.get('message')}")

def browser_type(selector: str, text: str, submit: bool = False, by: str = None) -> ToolResult:
    res = browser_engine.execute_task("type", target=selector, params={"by": by, "text": text})
    if res.get("success"):
        if submit:
            # simple submit hack for now
            try:
                driver = _manager.get_driver()
                from jarvis.tools.browser_engine import ElementLocator
                el = ElementLocator.locate(driver, selector, by)
                el.send_keys(Keys.RETURN)
            except:
                pass
        return ToolResult(True, observation=f"Typed into {selector!r}: {text!r}")
    return ToolResult(False, error=res.get("message"), observation=f"Could not type into {selector!r}: {res.get('message')}")

def browser_get_text(selector: str, by: str = None) -> ToolResult:
    return ToolResult(True, observation="Please use browser_observe to see the whole page instead.")

def browser_get_links(max_links: int = 30) -> ToolResult:
    try:
        driver = _manager.get_driver()
        elements = driver.find_elements(By.TAG_NAME, "a")[:max_links]
        links = [{"text": e.text, "href": e.get_attribute("href")} for e in elements]
        return ToolResult(True, output=links, observation=f"Found {len(links)} link(s) on current page")
    except Exception as e:
        return ToolResult(False, error=str(e), observation=f"Failed to get links: {str(e)}")

def browser_scroll(pixels: int = 800) -> ToolResult:
    try:
        driver = _manager.get_driver()
        driver.execute_script(f"window.scrollBy(0, {int(pixels)});")
        return ToolResult(True, observation=f"Scrolled {pixels}px")
    except Exception as e:
        return ToolResult(False, error=str(e), observation=f"Failed to scroll: {str(e)}")

def browser_screenshot(path: str) -> ToolResult:
    try:
        driver = _manager.get_driver()
        driver.save_screenshot(path)
        return ToolResult(True, output=path, observation=f"Saved screenshot to {path}")
    except Exception as e:
        return ToolResult(False, error=str(e), observation=f"Failed to save screenshot: {str(e)}")

def browser_observe() -> ToolResult:
    try:
        res = browser_engine.execute_task("observe")
        if res.get("success"):
            data = res.get("data", {})
            if data.get("url") == "data:," and not data.get("title") and not data.get("elements"):
                _manager.recover()
                return ToolResult(False, error="session_stale", observation="Browser session is not ready or page is blank. Session has been recovered. Please try navigating again.")
                
            import json
            # Only show first 50 elements to not overload LLM
            data_str = json.dumps(data, indent=2)
            return ToolResult(True, output=data_str, observation=f"Observed page state:\n{data_str}")
        return ToolResult(False, error=res.get("message"), observation=res.get("message"))
    except Exception as e:
        return ToolResult(False, error=str(e), observation=str(e))

def browser_close() -> ToolResult:
    _manager.close()
    return ToolResult(True, observation="Closed browser session")

def youtube_play(query: str) -> ToolResult:
    """Specialized deterministic handler for 'play X on youtube'."""
    try:
        _manager.new_tab()
        driver = _manager.get_driver()
        encoded = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        driver.get(url)
        
        selector = "ytd-video-renderer a#video-title"
        el = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        title = el.get_attribute("title") or el.text or query
        el.click()
        return ToolResult(True, observation=f"Playing '{title}' on YouTube")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not play '{query}' on YouTube: {exc}")


def register(registry) -> None:
    common = {
        "by": {"type": "str", "required": False, "description": "optional, e.g. css, xpath, id"},
        "selector": {"type": "str", "required": True, "description": "The exact locator string, or visible text if by is omitted"},
    }
    registry.register(Tool("browser_observe", "Observe the current webpage and return interactive elements (MUST USE BEFORE INTERACTING)",
                            {}, RiskLevel.LOW, browser_observe, "browser"))
    registry.register(Tool("browser_open", "Open a URL in the browser in a new tab.",
                            {"url": {"type": "str", "required": True}}, RiskLevel.LOW, browser_open, "browser"))
    registry.register(Tool("browser_navigate", "Navigate the current browser tab to a URL.",
                            {"url": {"type": "str", "required": True}}, RiskLevel.LOW, browser_navigate, "browser"))
    registry.register(Tool("browser_back", "Go back one page in browser history.", {}, RiskLevel.LOW, browser_back, "browser"))
    registry.register(Tool("browser_refresh", "Refresh the current page.", {}, RiskLevel.LOW, browser_refresh, "browser"))
    registry.register(Tool("browser_find_element", "Wait for and read an element's text by selector.",
                            common, RiskLevel.LOW, browser_find_element, "browser"))
    registry.register(Tool("browser_click", "Wait for and click an element by selector.",
                            common, RiskLevel.LOW, browser_click, "browser"))
    registry.register(Tool("browser_type", "Type text into an input element, optionally pressing Enter.",
                            {**common, "text": {"type": "str", "required": True}, "submit": {"type": "bool"}},
                            RiskLevel.LOW, browser_type, "browser"))
    registry.register(Tool("browser_get_text", "Alias of browser_find_element for reading element text.",
                            common, RiskLevel.LOW, browser_get_text, "browser"))
    registry.register(Tool("browser_get_links", "Get all links on the current page.",
                            {"max_links": {"type": "int"}}, RiskLevel.LOW, browser_get_links, "browser"))
    registry.register(Tool("browser_scroll", "Scroll the page vertically by N pixels.",
                            {"pixels": {"type": "int"}}, RiskLevel.LOW, browser_scroll, "browser"))
    registry.register(Tool("browser_screenshot", "Save a screenshot of the current page.",
                            {"path": {"type": "str", "required": True}}, RiskLevel.LOW, browser_screenshot, "browser"))
    registry.register(Tool("browser_close", "Close the browser session.", {}, RiskLevel.LOW, browser_close, "browser"))
    registry.register(Tool("youtube_play", "Fast-path specialized handler to search and play a YouTube video directly.",
                            {"query": {"type": "str", "required": True}}, RiskLevel.LOW, youtube_play, "browser"))
