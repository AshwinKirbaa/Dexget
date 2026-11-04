import os
import threading
import time
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint
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


def test_dynamic_island_reacts_to_media_metadata():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.collapse_island()
        widget.update_media({
            "title": "One Sun One Moon",
            "artist": "Anirudh Ravichander",
            "app": "YouTube Music",
            "playing": True,
        })
        assert not widget.isHidden()
        assert not widget._media_manually_hidden
        widget.resize(widget.MEDIA_SIZE)
        widget.show()
        app.processEvents()
        assert widget.name_label.text() == "One Sun One Moon"
        assert 150 <= widget.name_label.width() <= 200
        assert widget.status_label.text() == "Anirudh Ravichander"
        assert widget.play_pause_btn.text() == "❚❚"
        assert not widget.album_art.isHidden()
        assert not widget.previous_btn.isHidden()
        assert widget.MEDIA_MIN_WIDTH <= widget._compact_size().width() < widget.MEDIA_SIZE.width()
        assert widget._compact_size().height() == widget.MEDIA_SIZE.height()

        widget.hide_media_island()
        assert widget._media_manually_hidden
        assert widget._auto_hidden
        deadline = time.monotonic() + 1
        while not widget.isHidden() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert widget.isHidden()
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()
        widget._check_hot_zone()
        assert widget._media_manually_hidden
        assert widget._auto_hidden
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()

        widget.activate_island()
        assert not widget._media_manually_hidden
        assert not widget.isHidden()
        assert not widget.is_expanded
        assert widget.scroll_area.isHidden()
        assert widget.input_frame.isHidden()
        assert widget.windowOpacity() == 1.0
        assert widget._animation.duration() >= 300
        assert widget.expand_btn.parent() is None

        widget.update_media({
            "title": "One Sun One Moon",
            "artist": "Anirudh Ravichander",
            "app": "YouTube Music",
            "playing": False,
        })
        deadline = time.monotonic() + 1
        while not widget.isHidden() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert widget.isHidden()
        assert widget._media_manually_hidden
        widget.reveal_idle_island()
        assert not widget.isHidden()
        assert not widget._media_manually_hidden

        widget.update_media({
            "title": "One Sun One Moon",
            "artist": "Anirudh Ravichander",
            "app": "YouTube Music",
            "playing": True,
        })
        assert not widget.isHidden()
        assert not widget._media_manually_hidden

        widget.update_media({})
        deadline = time.monotonic() + 1
        while not widget.isHidden() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert widget.isHidden()

        widget.update_media({})
        assert widget.name_label.text() == "DEXGET"
        assert widget.album_art.isHidden()
        assert widget.previous_btn.isHidden()
        assert widget._compact_size() == widget.COLLAPSED_SIZE
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_idle_island_hides_and_reveals_with_rounded_mask():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget._assistant_state = "Idle"
        widget.hide_idle_island()
        assert widget._auto_hidden
        assert widget.windowOpacity() < 0.1

        widget.reveal_idle_island()
        assert not widget._auto_hidden
        assert widget.windowOpacity() == 1.0
        widget._animation.stop()
        widget.resize(widget.COLLAPSED_SIZE)
        app.processEvents()
        assert widget._corner_radius() == widget.height() / 2
        assert widget.mask().isEmpty()
        assert widget.HOT_ZONE_WIDTH == 140
        assert widget.HOT_ZONE_HEIGHT == 12
        assert widget._hover_timer.interval() == 40
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_expand_defers_content_until_surface_has_grown():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.expand_island()
        assert widget.scroll_area.isHidden()
        assert widget.input_frame.isHidden()
        deadline = time.monotonic() + 1.5
        while widget.scroll_area.isHidden() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert not widget.scroll_area.isHidden()
        assert not widget.input_frame.isHidden()
        assert widget.container.graphicsEffect() is None
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_media_expand_preserves_content_aware_width():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.update_media({
            "title": "A deliberately long media title for sizing",
            "artist": "A deliberately long artist name",
            "app": "YouTube Music", "playing": True,
        })
        compact_width = widget._compact_size().width()
        widget.resize(widget._compact_size())
        widget.expand_island()
        target = widget._animation.endValue()
        assert target.width() == compact_width
        assert target.width() >= widget.EXPANDED_SIZE.width()
        assert target.height() == widget.EXPANDED_SIZE.height()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_hover_revealed_paused_media_minimizes_after_pointer_leaves():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.update_media({
            "title": "Paused song", "artist": "Artist",
            "app": "YouTube Music", "playing": False,
        })
        widget.reveal_idle_island()
        assert not widget.isHidden()
        widget._hover_leave_at = time.monotonic() - 2
        with patch("widget.QCursor.pos", return_value=QPoint(-100, -100)):
            widget._check_hot_zone()
        deadline = time.monotonic() + 1
        while not widget.isHidden() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert widget.isHidden()
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_charger_connection_shows_live_activity_and_restores_state():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.show_charging_activity(75)
        assert widget._charging_active
        assert widget._compact_size() == widget.CHARGING_SIZE
        assert widget.charging_label.text() == "Charging"
        assert widget.charging_percent.text() == "75%"
        assert widget.battery_indicator.percent == 75
        assert not widget.charging_label.isHidden()
        assert widget.identity_widget.isHidden()
        assert widget.close_btn.isHidden()

        widget.finish_charging_activity()
        assert not widget._charging_active
        assert widget.charging_label.isHidden()
        assert not widget.identity_widget.isHidden()
        assert not widget.close_btn.isHidden()
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_headset_connection_shows_live_activity_and_restores_state():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        assert widget._is_headset_name("Headphones (realme Buds T310)")
        assert widget._is_headset_name("AirPods Pro")
        assert not widget._is_headset_name("Laptop Speakers")

        widget.show_headset_activity("Headphones (realme Buds T310)")
        assert widget._headset_active
        assert widget._compact_size() == widget.HEADSET_SIZE
        assert widget.headset_name.text() == "realme Buds T310"
        assert widget.headset_status.text() == "Connected"
        assert not widget.earbuds_indicator.isHidden()
        assert not widget.connection_ring.isHidden()
        assert widget.identity_widget.isHidden()
        assert widget.close_btn.isHidden()

        widget.finish_headset_activity()
        assert not widget._headset_active
        assert widget.earbuds_indicator.isHidden()
        assert widget.connection_ring.isHidden()
        assert not widget.identity_widget.isHidden()
        assert not widget.close_btn.isHidden()
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()
