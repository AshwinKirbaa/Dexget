"""Local-only browser smoke test. Add --live-model to exercise Ollama planning."""
import argparse
import functools
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from selenium import webdriver
from jarvis.tools import browser
from jarvis.tools.browser_engine import BrowserContext, ContextMode

HTML = """<!doctype html><title>JARVIS automation test</title>
<label>Name <input id="name" aria-label="Name" placeholder="Name"></label>
<button onclick="document.querySelector('#result').textContent='Saved: '+document.querySelector('#name').value">Save</button>
<p id="result">Nothing saved yet</p>
<select aria-label="Color"><option>Red</option><option>Blue</option></select>
<a href="/second.html">Second page</a>"""


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main(live_model=False, model=None):
    with tempfile.TemporaryDirectory(prefix="jarvis_browser_smoke_") as directory:
        root = Path(directory)
        (root / "index.html").write_text(HTML, encoding="utf-8")
        (root / "second.html").write_text("<title>Second page</title><p>Second page verified</p>", encoding="utf-8")
        server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=directory))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        options.add_argument(f"--user-data-dir={root / 'profile'}")
        driver = None
        try:
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(15)
            browser._manager.factory._contexts[ContextMode.DEFAULT_ACCOUNT] = BrowserContext(
                ContextMode.DEFAULT_ACCOUNT, driver)
            url = f"http://127.0.0.1:{server.server_port}/index.html"
            if live_model:
                from jarvis.agent.executor import Executor, ExecutorConfig
                from jarvis.agent.tool_registry import ToolRegistry
                from jarvis_integration import _make_ollama_fn
                registry = ToolRegistry()
                browser.register(registry)
                # Only tools required by this controlled task; no desktop or shell access.
                keep = {"browser_open", "browser_observe", "browser_click", "browser_type", "browser_get_text"}
                for tool in registry.list_tools():
                    if tool.name not in keep:
                        registry.unregister(tool.name)
                executor = Executor(registry, _make_ollama_fn(model=model or os.getenv("JARVIS_OLLAMA_MODEL", "gemma3:4b")),
                                    ExecutorConfig(max_steps=12),
                                    on_progress=lambda message: print(message, flush=True))
                outcome = executor.run(
                    f"Open {url}, enter Jarvis Test in the Name input, click Save, "
                    "then verify the page displays Saved: Jarvis Test. Complete only after checking the text.")
                if outcome.status.value != "completed":
                    print(json.dumps([{"tool": s.tool, "parameters": s.parameters, "error": s.error}
                                      for s in outcome.task_state.failed_steps]), flush=True)
                assert outcome.status.value == "completed", outcome.final_message
            else:
                assert browser.browser_open(url).success
                observation = browser.browser_observe()
                assert observation.success, observation.error
                elements = observation.output["elements"]
                name = next(e["selector"] for e in elements if e["text"] == "Name")
                save = next(e["selector"] for e in elements if e["text"] == "Save")
                assert browser.browser_type(name, "Jarvis Test", by="css").success
                assert browser.browser_click(save, by="css").success
            # Independently check the real DOM; the model's completion text is not sufficient.
            assert driver.find_element("id", "result").text == "Saved: Jarvis Test"
            assert browser.browser_get_text("#result", "css").output["text"] == "Saved: Jarvis Test"
            assert browser.browser_select("select", "Blue").success
            assert driver.find_element("css selector", "select").get_attribute("value") == "Blue"
            original = driver.current_window_handle
            tab_count = len(driver.window_handles)
            assert browser.browser_open(url.replace("index", "second")).success
            assert len(browser.browser_tabs().output) == tab_count + 1
            assert browser.browser_switch_tab(original).success
            assert driver.find_element("id", "result").text == "Saved: Jarvis Test"
            print("PASS: real browser form, DOM verification, select, tabs and shared session.", flush=True)
        finally:
            if driver is not None:
                driver.quit()
            browser._manager.factory._contexts.clear()
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-model", action="store_true")
    parser.add_argument("--model", help="Installed Ollama model to use for the live test.")
    args = parser.parse_args()
    main(args.live_model, args.model)
