import os
import threading
import time
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from jarvis.agent.agent import Agent
from jarvis.agent.tool_registry import ToolRegistry
from jarvis.tools.base import RiskLevel, Tool, ToolResult
from widget import JarvisWidget, JarvisWorker


def test_widget_text_mode_and_confirmation_without_voice():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    finished = []
    worker_thread = None
    try:
        assert widget.worker.vm is None
        widget.agent.registry.register(Tool(
            "sensitive", "Test approval", {}, RiskLevel.HIGH,
            lambda: ToolResult(True, observation="Approved")))
        worker_thread = threading.Thread(
            target=lambda: finished.append(widget.agent.registry.execute("sensitive")))
        worker_thread.start()
        deadline = time.monotonic() + 2
        while widget.confirmation_panel.isHidden() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert not widget.confirmation_panel.isHidden()
        assert not finished
        widget.resolve_confirmation(True)
        worker_thread.join(2)
        assert finished[0].success
    finally:
        widget.worker.shutdown()
        if worker_thread:
            worker_thread.join(2)
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_stop_before_worker_starts_drops_pending_command():
    app = QApplication.instance() or QApplication([])
    worker = JarvisWorker(Agent(ToolRegistry()))
    worker.submit_text("some task")
    worker.cancel()
    assert worker.commands.empty()
    assert worker.agent.registry.cancel_event.is_set()
    assert not worker.busy.is_set()
