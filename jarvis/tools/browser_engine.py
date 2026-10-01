import os
import json
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, NoSuchWindowException, TimeoutException

class AuthState(Enum):
    AUTHENTICATED = "AUTHENTICATED"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    UNKNOWN = "UNKNOWN"

class ContextMode(Enum):
    DEFAULT_ACCOUNT = "DEFAULT_ACCOUNT"
    PRIVATE = "PRIVATE"
    AUTOMATION = "AUTOMATION"

@dataclass
class BrowserContext:
    mode: ContextMode
    driver: webdriver.Chrome

class BrowserResolver:
    @staticmethod
    def resolve(browser_name: str) -> str:
        browser_name = browser_name.lower()
        if "brave" in browser_name: return "brave"
        if "edge" in browser_name: return "edge"
        if "firefox" in browser_name: return "firefox"
        return "chrome"

class BrowserProfileResolver:
    @staticmethod
    def resolve(profile_name: str) -> str:
        if profile_name.lower() in ("default", "main"):
            return "Default"
        return profile_name

class BrowserContextFactory:
    def __init__(self):
        self._contexts: Dict[ContextMode, BrowserContext] = {}

    def get_context(self, mode: ContextMode = ContextMode.DEFAULT_ACCOUNT) -> BrowserContext:
        if mode in self._contexts and self.is_alive(self._contexts[mode].driver):
            return self._contexts[mode]
            
        browser = os.environ.get("JARVIS_BROWSER", "chrome").lower()
        if browser not in ("chrome", "edge"):
            raise ValueError("JARVIS_BROWSER must be chrome or edge.")
        options = webdriver.EdgeOptions() if browser == "edge" else webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        
        if mode == ContextMode.DEFAULT_ACCOUNT:
            base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
            user_dir = Path(os.environ.get("JARVIS_BROWSER_PROFILE") or
                            base / "JarvisAgent" / f"{browser}-automation")
            user_dir.mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={user_dir.resolve()}")
        elif mode == ContextMode.PRIVATE:
            options.add_argument("--inprivate" if browser == "edge" else "--incognito")
            
        options.page_load_strategy = "eager"
        driver_type = webdriver.Edge if browser == "edge" else webdriver.Chrome
        driver = driver_type(options=options)
        driver.set_page_load_timeout(30)
            
        ctx = BrowserContext(mode=mode, driver=driver)
        self._contexts[mode] = ctx
        return ctx

    def is_alive(self, driver):
        try:
            if not driver.session_id:
                return False
            handles = driver.window_handles
            if handles:
                try:
                    driver.current_window_handle
                except NoSuchWindowException:
                    driver.switch_to.window(handles[-1])
                return True
        except Exception:
            pass
        try:
            driver.quit()
        except Exception:
            pass
        return False

class BrowserTabManager:
    def __init__(self, driver):
        self.driver = driver

    def create_tab(self, url: Optional[str] = None):
        if len(self.driver.window_handles) == 1 and self.driver.current_url in (
            "data:,", "about:blank", "chrome://newtab/", "chrome://new-tab-page/", "edge://newtab/"
        ):
            if url:
                self.driver.get(url)
            return self.driver.current_window_handle
            
        self.driver.switch_to.new_window("tab")
        if url:
            self.driver.get(url)
        return self.driver.current_window_handle
        
    def get_tabs(self):
        return self.driver.window_handles

class PageObserver:
    def __init__(self, driver):
        self.driver = driver

    def observe(self, offset: int = 0) -> Dict[str, Any]:
        if offset < 0:
            raise ValueError("Observation offset must be nonnegative.")
        info = self.driver.execute_script("""
            const prefix = arguments[0];
            const offset = arguments[1];
            const nodes = [...document.querySelectorAll(
                'a,button,input,select,textarea,[role="button"],[role="link"],[contenteditable="true"]'
            )].filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden');
            const elements = nodes.slice(offset,offset+60).map((el,i) => {
                const ref = prefix + '-' + i;
                el.setAttribute('data-jarvis-ref', ref);
                const idSelector = el.id ? '#' + CSS.escape(el.id) : null;
                const selector = idSelector && document.querySelectorAll(idSelector).length === 1
                    ? idSelector : '[data-jarvis-ref="' + ref + '"]';
                return {selector, id: el.id || '', name: el.getAttribute('name') || '',
                    tag: el.tagName.toLowerCase(), type: el.type || '',
                    text: (el.innerText || el.getAttribute('aria-label') ||
                           el.getAttribute('placeholder') || '').trim().slice(0,180),
                    value: el.type === 'password' ? '[redacted]' : (el.value || '').slice(0,180),
                    href: el.href || null, disabled: !!el.disabled};
            });
            return {text: (document.body?.innerText || '').slice(0,6000), elements,
                    total_elements: nodes.length, offset,
                    frames: [...document.querySelectorAll('iframe,frame')].map((f,i) =>
                        ({index:i, name:f.name, title:f.title, src:f.src}))};
        """, uuid.uuid4().hex[:8], offset)
        info.update(url=self.driver.current_url, title=self.driver.title,
                    auth_state=self.detect_auth_state().value)
        return info

    def detect_auth_state(self) -> AuthState:
        # Heuristics based on URL or common elements
        url = self.driver.current_url.lower()
        if "login" in url or "signin" in url:
            return AuthState.LOGIN_REQUIRED
        return AuthState.UNKNOWN

class ElementLocator:
    @staticmethod
    def locate(driver, target: str, by: str = None):
        # The planner may omit an optional locator mode. Snapshot selectors
        # remain directly usable without that flag.
        if by is None and target.startswith(("#", ".", "[")):
            by = "css"
        elif by is None and target.startswith(("/", "(")):
            by = "xpath"
        by_map = {"css": By.CSS_SELECTOR, "css_selector": By.CSS_SELECTOR,
                  "xpath": By.XPATH, "id": By.ID, "name": By.NAME,
                  "text": By.LINK_TEXT, "link_text": By.LINK_TEXT, "tag": By.TAG_NAME}
        if by and by.lower() != "text":
            if by.lower() not in by_map:
                raise ValueError(f"Unsupported locator {by!r}; use css, xpath, id, name or text.")
            by_type = by_map[by.lower()]
            return WebDriverWait(driver, 10).until(EC.presence_of_element_located((by_type, target)))
            
        def find_visible(_):
            matches = driver.execute_script("""
                const target = arguments[0];
                return [...document.querySelectorAll('a,button,input,select,textarea,[role]')]
                    .filter(el => el.getClientRects().length && [
                        (el.innerText || '').trim(), el.getAttribute('placeholder'),
                        el.getAttribute('aria-label'), el.id, el.getAttribute('name')
                    ].includes(target));
            """, target)
            if len(matches) > 1:
                raise ValueError("Several elements match. Observe and use an exact CSS selector.")
            return matches[0] if matches else False
        return WebDriverWait(driver, 10).until(find_visible)

class BrowserVerification:
    @staticmethod
    def verify_page_loaded(driver) -> bool:
        try:
            return driver.execute_script("return document.readyState") == "complete"
        except:
            return False
            
    @staticmethod
    def verify_element_visible(el) -> bool:
        try:
            return el.is_displayed()
        except:
            return False

class BrowserRecovery:
    @staticmethod
    def recover_blank_state(driver, factory, mode):
        # Blank browser state (data:,) -> Recover
        try:
            driver.quit()
        except:
            pass
        # Force re-creation
        if mode in factory._contexts:
            del factory._contexts[mode]
        return factory.get_context(mode).driver

class BrowserAutomationEngine:
    def __init__(self):
        self.factory = BrowserContextFactory()

    def execute_task(self, action: str, target: str = None, params: dict = None) -> dict:
        params = params or {}
        try:
            context = self.factory.get_context(ContextMode.DEFAULT_ACCOUNT)
            driver = context.driver
            observer = PageObserver(driver)
            if action == "navigate":
                driver.get(target)
                return {"success": True, "status": "completed", "action": "navigate", "url": driver.current_url, "title": driver.title}
            
            elif action == "click":
                el = ElementLocator.locate(driver, target, params.get("by"))
                # Wait for clickable
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(el))
                el.click()
                return {"success": True, "status": "completed", "action": "click",
                        "data": {"url": driver.current_url, "title": driver.title}}
                
            elif action == "type":
                el = ElementLocator.locate(driver, target, params.get("by"))
                editable = el.get_attribute("contenteditable") in ("true", "plaintext-only")
                if not editable and (el.tag_name not in ("input", "textarea") or
                                     el.get_attribute("type") in ("button", "submit", "checkbox", "radio")):
                    raise ValueError(f"Selected {el.tag_name} {el.text!r} is not a text field. Choose an input or textarea from browser_observe.")
                if editable:
                    el.send_keys(Keys.CONTROL, "a")
                else:
                    el.clear()
                el.send_keys(params.get("text", ""))
                value = "[redacted]" if el.get_attribute("type") == "password" else (
                    el.get_attribute("value") or el.text)
                if params.get("submit"):
                    el.send_keys(Keys.ENTER)
                return {"success": True, "status": "completed", "action": "type",
                        "data": {"value": value, "submitted": bool(params.get("submit"))}}
                
            elif action == "observe":
                data = observer.observe(params.get("offset", 0))
                return {"success": True, "status": "completed", "action": "observe", "data": data}
                
            else:
                return {"success": False, "status": "unknown_action", "message": f"Action {action} not implemented"}
                
        except Exception as e:
            message = getattr(e, "msg", None) or str(e)
            return {"success": False, "status": "error", "message": message[:1000],
                    "recoverable": True, "recovery_attempted": False}

_engine = BrowserAutomationEngine()

class BrowserWorkflowExecutor:
    @staticmethod
    def run_browser_workflow(workflow_steps: List[dict]) -> dict:
        results = []
        for step in workflow_steps:
            action = step.get("action")
            target = step.get("target")
            params = step.get("parameters", {})
            
            res = _engine.execute_task(action, target, params)
            results.append(res)
            
            if not res.get("success"):
                break
                
        return {"status": "completed" if all(r.get("success") for r in results) else "failed", "steps": results}

def run_browser_workflow(workflow_steps: List[dict]) -> dict:
    return BrowserWorkflowExecutor.run_browser_workflow(workflow_steps)
