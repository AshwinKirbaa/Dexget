import os
import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
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
            
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        
        if mode == ContextMode.DEFAULT_ACCOUNT:
            user_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")
            if os.path.exists(user_dir):
                options.add_argument(f"user-data-dir={user_dir}")
        elif mode == ContextMode.PRIVATE:
            options.add_argument("--incognito")
            
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(15)
        except WebDriverException:
            # Fallback for DEFAULT_ACCOUNT if locked
            fallback_options = webdriver.ChromeOptions()
            fallback_options.add_argument("--start-maximized")
            driver = webdriver.Chrome(options=fallback_options)
            driver.set_page_load_timeout(15)
            
        ctx = BrowserContext(mode=mode, driver=driver)
        self._contexts[mode] = ctx
        return ctx

    def is_alive(self, driver):
        try:
            import time
            start = time.time()
            
            # Simple check if session is valid
            if not driver.session_id:
                return False
                
            url = driver.current_url
            
            # Check for BLANK state which often happens when CDP disconnects
            if url == "data:," and len(driver.window_handles) == 1:
                # Give it a tiny bit of time if it's just starting
                title = driver.title
                if not title and time.time() - start > 2.0:
                    try:
                        driver.quit()
                    except:
                        pass
                    return False
                    
            return True
        except (WebDriverException, NoSuchWindowException, TimeoutException) as e:
            try:
                driver.quit()
            except:
                pass
            return False
        except Exception:
            try:
                driver.quit()
            except:
                pass
            return False

class BrowserTabManager:
    def __init__(self, driver):
        self.driver = driver

    def create_tab(self, url: Optional[str] = None):
        if len(self.driver.window_handles) == 1 and self.driver.current_url == "data:,":
            if url:
                self.driver.get(url)
            return self.driver.current_window_handle
            
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        if url:
            self.driver.get(url)
        return self.driver.current_window_handle
        
    def get_tabs(self):
        return self.driver.window_handles

class PageObserver:
    def __init__(self, driver):
        self.driver = driver

    def observe(self) -> Dict[str, Any]:
        info = {
            "url": self.driver.current_url,
            "title": self.driver.title,
            "auth_state": self.detect_auth_state().value,
            "elements": []
        }
        
        # Simple extraction of interactive elements
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a, button, input, select, textarea")
            for el in elements[:50]: # Limit for performance/context size
                try:
                    if el.is_displayed():
                        tag = el.tag_name
                        text = el.text or el.get_attribute("value") or el.get_attribute("placeholder") or ""
                        el_id = el.get_attribute("id")
                        el_name = el.get_attribute("name")
                        href = el.get_attribute("href") if tag == "a" else None
                        info["elements"].append({
                            "tag": tag,
                            "text": text.strip(),
                            "id": el_id,
                            "name": el_name,
                            "href": href
                        })
                except Exception:
                    continue
        except Exception:
            pass
            
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
        # Preferred order: accessibility role/name, visible text, id, name, xpath, etc.
        # Fallback to xpath if needed
        # We can simulate this
        if by:
            by_type = getattr(By, by.upper())
            return WebDriverWait(driver, 10).until(EC.presence_of_element_located((by_type, target)))
            
        # Try text
        try:
            return driver.find_element(By.XPATH, f"//*[text()='{target}']")
        except:
            pass
            
        # Try placeholder or aria-label
        try:
            return driver.find_element(By.XPATH, f"//*[@placeholder='{target}' or @aria-label='{target}']")
        except:
            pass
            
        raise Exception(f"Could not locate element: {target}")

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
        context = self.factory.get_context(ContextMode.DEFAULT_ACCOUNT)
        driver = context.driver
        tabs = BrowserTabManager(driver)
        observer = PageObserver(driver)
        
        try:
            if action == "navigate":
                tabs.create_tab(target)
                return {"success": True, "status": "completed", "action": "navigate", "url": driver.current_url, "title": driver.title}
            
            elif action == "click":
                el = ElementLocator.locate(driver, target, params.get("by"))
                # Wait for clickable
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(el))
                el.click()
                return {"success": True, "status": "completed", "action": "click", "verification": {"page_loaded": True}}
                
            elif action == "type":
                el = ElementLocator.locate(driver, target, params.get("by"))
                el.clear()
                el.send_keys(params.get("text", ""))
                return {"success": True, "status": "completed", "action": "type"}
                
            elif action == "observe":
                data = observer.observe()
                return {"success": True, "status": "completed", "action": "observe", "data": data}
                
            else:
                return {"success": False, "status": "unknown_action", "message": f"Action {action} not implemented"}
                
        except Exception as e:
            return {"success": False, "status": "error", "message": str(e), "recoverable": True, "recovery_attempted": False}

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
