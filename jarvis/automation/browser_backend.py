import asyncio
import os
import subprocess
from typing import Dict, Any, List, Optional
from .base import AutomationBackend, Observation


class BrowserConnectionState:
    PROFILE_EXISTS        = "profile_exists"
    CHROME_RUNNING        = "chrome_running"
    REMOTE_DEBUG_ENABLED  = "remote_debug_enabled"
    SESSION_DETECTED      = "session_detected"
    SESSION_ATTACHED      = "session_attached"
    PROFILE_IDENTITY      = "profile_identity"
    SERVICE_AUTH          = "service_auth"


def _read_devtools_active_port(user_data_dir: str) -> Optional[tuple]:
    """
    Read DevToolsActivePort - contains TWO lines:
      Line 1: port number (e.g. 9222)
      Line 2: WebSocket path including UUID (e.g. /devtools/browser/<uuid>)
    Returns (port_str, ws_path) or None.

    CRITICAL: Must read BOTH lines. Playwright only reads line 1 and builds
    ws://localhost:PORT/devtools/browser (no UUID) which gets 403.
    The correct endpoint is ws://localhost:PORT/devtools/browser/<UUID>.
    """
    dat_path = os.path.join(user_data_dir, "DevToolsActivePort")
    try:
        with open(dat_path, "r") as f:
            lines = f.read().splitlines()
        if len(lines) >= 2:
            return (lines[0].strip(), lines[1].strip())
        elif lines:
            return (lines[0].strip(), "/devtools/browser")
    except Exception:
        pass
    return None


async def _try_attach_to_chrome(playwright, user_data_dir: str, timeout_ms: int = 5000):
    """
    Attach Playwright to an already-running Chrome session via CDP.

    The correct endpoint is ws://localhost:{port}{uuid_path} where uuid_path
    comes from line 2 of DevToolsActivePort. Without the UUID the connection
    gets 403 Forbidden.
    """
    port_info = _read_devtools_active_port(user_data_dir)
    if not port_info:
        return None

    port, ws_path = port_info

    for host in ("localhost", "127.0.0.1"):
        endpoint = f"ws://{host}:{port}{ws_path}"
        try:
            browser = await playwright.chromium.connect_over_cdp(endpoint, timeout=timeout_ms)
            return browser
        except Exception as e:
            print(f"  [CDP] Failed {endpoint}: {str(e)[:100]}")
    return None


def _chrome_exe_path() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "chrome.exe",
    ]
    return next((p for p in candidates if os.path.exists(p)), "chrome.exe")


class BrowserUseBackend(AutomationBackend):
    """
    Browser automation backend with three modes:

    ATTACHED   - Playwright connected to the real running Chrome via CDP WebSocket.
                 Full read/write access to existing tabs, sessions, and auth state.
    SUBPROCESS - Chrome opened via subprocess with correct profile.
                 No Playwright control. Only navigation via subprocess.
    GENERIC    - Playwright launches its own Chromium instance.
                 Full automation, no existing session.
    """

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.external_browser = False

        self.connection_state: Dict[str, Any] = {
            BrowserConnectionState.PROFILE_EXISTS:       None,
            BrowserConnectionState.CHROME_RUNNING:       None,
            BrowserConnectionState.REMOTE_DEBUG_ENABLED: None,
            BrowserConnectionState.SESSION_DETECTED:     None,
            BrowserConnectionState.SESSION_ATTACHED:     None,
            BrowserConnectionState.PROFILE_IDENTITY:     None,
            BrowserConnectionState.SERVICE_AUTH:         None,
        }

        self.state = {
            "current_browser":   None,
            "current_context":   None,
            "current_tab":       None,
            "current_url":       None,
            "page_title":        None,
            "last_observation":  None,
            "selected_element":  None,
            "existing_tabs":     [],
        }

    async def _init_browser(
        self,
        browser_exec: Optional[str] = None,
        profile_dir: Optional[str] = None,
        url: Optional[str] = None,
    ):
        if self.playwright:
            return

        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()

        if profile_dir:
            await self._init_profile_browser(browser_exec, profile_dir, url)
        else:
            await self._init_generic_browser(url)

        self.state["current_browser"] = browser_exec or "chromium"
        self.state["current_context"] = profile_dir or "default"
        self.state["current_tab"] = "tab1"
        if self.page:
            await self._update_state()

    async def _init_profile_browser(
        self,
        browser_exec: Optional[str],
        profile_dir: str,
        url: Optional[str],
    ):
        from jarvis.tasks.account_discovery import get_browser_user_data_dir

        user_data_dir = get_browser_user_data_dir(browser_exec or "chrome")
        if not user_data_dir:
            raise Exception(
                f"Cannot find user data directory for {browser_exec or 'chrome'}."
            )

        profile_path = os.path.join(user_data_dir, profile_dir)
        self.connection_state[BrowserConnectionState.PROFILE_EXISTS] = os.path.isdir(profile_path)

        import psutil
        exe_name = "brave.exe" if browser_exec == "brave" else "chrome.exe"
        is_running = any(
            p.info.get("name") == exe_name
            for p in psutil.process_iter(["name"])
        )
        self.connection_state[BrowserConnectionState.CHROME_RUNNING] = is_running
        self.connection_state[BrowserConnectionState.SESSION_DETECTED] = is_running

        port_info = _read_devtools_active_port(user_data_dir)
        self.connection_state[BrowserConnectionState.REMOTE_DEBUG_ENABLED] = port_info is not None

        # Attempt 1: Playwright CDP attachment (preferred)
        if is_running and port_info:
            browser = await _try_attach_to_chrome(self.playwright, user_data_dir, timeout_ms=5000)
            if browser:
                self.browser = browser
                self.context = browser.contexts[0] if browser.contexts else None
                self.external_browser = False
                self.connection_state[BrowserConnectionState.SESSION_ATTACHED] = True

                if self.context:
                    self.state["existing_tabs"] = [
                        {"url": p.url, "title": ""}
                        for p in self.context.pages
                    ]

                self.page = await self._find_or_create_page(url)
                return

        # Attempt 2: Subprocess fallback
        if is_running and port_info:
            print(
                "  [CDP] Note: Connection timed out. Chrome's remote debugging "
                "requires chrome://inspect to be open for external connections."
            )
        exe_path = (
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
            if browser_exec == "brave"
            else _chrome_exe_path()
        )
        cmd = [exe_path, f"--profile-directory={profile_dir}"]
        if url:
            cmd.append(url)
        subprocess.Popen(cmd)
        self.external_browser = True
        self.browser = None
        self.context = None
        self.page = None
        self.connection_state[BrowserConnectionState.SESSION_ATTACHED] = False

    async def _find_or_create_page(self, url: Optional[str]):
        if not self.context:
            return None
        pages = self.context.pages
        if url:
            for p in pages:
                if url in p.url or p.url in url:
                    try:
                        await p.bring_to_front()
                    except Exception:
                        pass
                    return p
        real_pages = [p for p in pages if not p.url.startswith("chrome://")]
        if real_pages:
            try:
                await real_pages[0].bring_to_front()
            except Exception:
                pass
            return real_pages[0]
        if pages:
            return pages[0]
        return await self.context.new_page()

    async def _init_generic_browser(self, url: Optional[str]):
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        self.external_browser = False
        self.connection_state[BrowserConnectionState.SESSION_ATTACHED] = True

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        timeout_sec = float(os.environ.get("JARVIS_BROWSER_ACTION_TIMEOUT", "10"))
        return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout_sec))

    async def _update_state(self):
        if self.page:
            self.state["current_url"] = self.page.url
            try:
                self.state["page_title"] = await self.page.title()
            except Exception:
                self.state["page_title"] = ""

    async def _observe_async(self) -> Observation:
        await self._init_browser()
        await self._update_state()

        if not self.page:
            return Observation(
                "No page attached. Browser opened via subprocess.",
                [],
                active_window="Browser",
                url=None,
                page_title=None,
            )

        script = """
        () => {
            let elements = [];
            let i = 0;
            document.querySelectorAll('a, button, input, [role="button"]').forEach(el => {
                if (el.offsetParent !== null) {
                    let text = el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('name') || '';
                    if (text) {
                        elements.push({
                            id: 'node_' + i++,
                            tagName: el.tagName.toLowerCase(),
                            text: text.trim().substring(0, 50),
                            selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ').join('.') : '')
                        });
                    }
                }
            });
            return elements;
        }
        """
        try:
            elements = await self.page.evaluate(script)
        except Exception:
            elements = []

        self.state["last_observation"] = elements
        lines = [
            f"URL: {self.state.get('current_url')}",
            f"Title: {self.state.get('page_title')}",
            "Interactive Elements:",
        ]
        for el in elements:
            lines.append(f"  [{el['id']}] {el['tagName']}: '{el['text']}'")

        return Observation(
            "\n".join(lines),
            elements,
            active_window="Browser",
            url=self.state.get("current_url"),
            page_title=self.state.get("page_title"),
        )

    def observe(self, **kwargs) -> Observation:
        return self._run_async(self._observe_async())

    async def _click_async(self, target: str) -> bool:
        if not self.page:
            return False
        elements = self.state.get("last_observation", [])
        el = next((e for e in elements if e["id"] == target), None)
        if not el:
            el = next((e for e in elements if target.lower() in e["text"].lower()), None)
        if el:
            try:
                await self.page.click(f"text={el['text']}", timeout=5000)
                await self.page.wait_for_load_state("networkidle", timeout=5000)
                await self._update_state()
                return True
            except Exception as e:
                print(f"Click failed: {e}")
        return False

    def click(self, target: str, **kwargs) -> bool:
        return self._run_async(self._click_async(target))

    async def _type_async(self, target: str, text: str) -> bool:
        if not self.page:
            return False
        elements = self.state.get("last_observation", [])
        el = next((e for e in elements if e["id"] == target), None)
        if not el:
            el = next(
                (e for e in elements
                 if target.lower() in e["text"].lower()
                 or (e["tagName"] == "input" and "search" in target.lower())),
                None,
            )
        if el and el["tagName"] == "input":
            try:
                locators = await self.page.locator("input").all()
                for loc in locators:
                    if await loc.is_visible():
                        await loc.fill(text)
                        await self._update_state()
                        return True
            except Exception as e:
                print(f"Type failed: {e}")
        return False

    def type(self, target: str, text: str, **kwargs) -> bool:
        return self._run_async(self._type_async(target, text))

    async def _press_async(self, key_combo: str) -> bool:
        if not self.page:
            return False
        try:
            await self.page.keyboard.press(key_combo)
            await self.page.wait_for_load_state("networkidle", timeout=5000)
            await self._update_state()
            return True
        except Exception:
            return False

    def press(self, key_combo: str, **kwargs) -> bool:
        key = key_combo.replace("{", "").replace("}", "")
        return self._run_async(self._press_async(key))

    def scroll(self, direction: str, amount: int = 1, **kwargs) -> bool:
        if not self.page:
            return False

        async def _scroll():
            y = 500 * amount if direction == "down" else -500 * amount
            await self.page.mouse.wheel(0, y)
            return True

        return self._run_async(_scroll())

    async def _navigate_async(
        self,
        url: str,
        browser_exec: Optional[str] = None,
        profile_dir: Optional[str] = None,
    ) -> bool:
        await self._init_browser(browser_exec=browser_exec, profile_dir=profile_dir, url=url)

        if self.external_browser:
            return True

        if not self.page:
            return False

        try:
            if not url.startswith("http"):
                url = "https://" + url
            await self.page.goto(url, wait_until="domcontentloaded")
            await self._update_state()
            return True
        except Exception as e:
            print(f"Navigate failed: {e}")
            return False

    def launch_application(self, app_name: str, **kwargs) -> bool:
        url = kwargs.get("url")
        browser_exec = kwargs.get("browser")
        profile_dir = kwargs.get("profile")
        if url:
            return self._run_async(
                self._navigate_async(url, browser_exec=browser_exec, profile_dir=profile_dir)
            )
        self._run_async(self._init_browser(browser_exec=browser_exec, profile_dir=profile_dir))
        return True

    def focus_application(self, app_name: str, **kwargs) -> bool:
        if self.page:
            try:
                self._run_async(self.page.bring_to_front())
                return True
            except Exception:
                return False
        return False

    def verify_action(self, expected_condition: str, **kwargs) -> bool:
        obs = self.observe()
        return expected_condition.lower() in obs.text_representation.lower()

    async def async_cancel(self):
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    def cancel(self):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.async_cancel())
                return
        except RuntimeError:
            pass
        self._run_async(self.async_cancel())
