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
        settle_deadline = time.monotonic() + 1
        while time.monotonic() < settle_deadline:
            app.processEvents()
            if (widget.name_label.width() >= 150 and
                    (not widget._animation or
                     widget._animation.state() != widget._animation.State.Running)):
                break
            time.sleep(0.01)
        app.processEvents()
        assert widget.name_label.text() == "One Sun One Moon"
        assert widget.name_label.maximumWidth() == 200
        assert widget.status_label.text() == "Anirudh Ravichander"
        assert widget.play_pause_btn.text() == "❚❚"
        assert not widget.album_art.isHidden()
        assert not widget.previous_btn.isHidden()
        assert widget.MEDIA_MIN_WIDTH <= widget._compact_size().width() < widget.MEDIA_SIZE.width()
        assert widget._compact_size().height() == widget.MEDIA_SIZE.height()

        starting_geometry = widget.geometry()
        widget.hide_media_island()
        assert widget._media_manually_hidden
        assert widget._auto_hidden
        minimize_target = widget._animation_target
        assert minimize_target.size() == widget.MINIMIZE_SIZE
        assert widget.geometry() == starting_geometry
        widget._animation.setCurrentTime(widget._animation.duration() // 2)
        assert widget.geometry() == starting_geometry
        assert widget.container.width() < starting_geometry.width()
        assert widget.title_bar_opacity.opacity() == 0.0
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
        assert widget._hover_timer.interval() == 100
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
        target = widget._animation_target
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


def test_energy_saver_shows_low_power_activity_and_restores_state():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.show_low_power_activity(30)
        assert widget._low_power_active
        assert widget._compact_size() == widget.LOW_POWER_SIZE
        assert widget.low_power_label.text() == "Low Battery"
        assert widget.low_power_percent.text() == "30%"
        assert widget.low_power_battery.low_power
        assert not widget.low_power_battery.isHidden()
        assert widget.identity_widget.isHidden()

        widget.finish_low_power_activity()
        assert not widget._low_power_active
        assert widget.low_power_label.isHidden()
        assert widget.low_power_battery.isHidden()
        assert not widget.identity_widget.isHidden()
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_notification_live_activity_shows_content_and_restores_state():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.show_notification_activity("WhatsApp", "New message", "Ashwin: Hello")
        assert widget._notification_active
        assert widget._compact_size() == widget.NOTIFICATION_SIZE
        assert widget.notification_icon.text() == "✉"
        assert widget.notification_title.text() == "New message"
        assert widget.notification_body.text() == "“Ashwin: Hello”  · now"
        assert widget.title_bar.height() == widget.NOTIFICATION_SIZE.height()
        assert "rgba(12, 14, 18, 244)" in widget.container.styleSheet()
        assert "color: white" in widget.notification_title.styleSheet()
        assert not widget.notification_identity.isHidden()
        assert widget.identity_widget.isHidden()

        widget.finish_notification_activity()
        assert not widget._notification_active
        assert widget.notification_identity.isHidden()
        assert not widget.identity_widget.isHidden()
        assert widget.title_bar.height() == 48
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_duplicate_resize_requests_do_not_restart_running_animation():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget._animate_to(widget.COLLAPSED_SIZE, 1000)
        animation = widget._animation
        widget._animate_to(widget.COLLAPSED_SIZE, 1000)
        assert widget._animation is animation
        assert widget._animation.state() == widget._animation.State.Running
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_call_layout_is_contextual_and_controls_microphone():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget._foreground_title = "Google Meet - Weekly call - Google Chrome"
        widget._foreground_process = "chrome.exe"
        with patch.object(widget, "_active_microphone_clients",
                          return_value={r"microphone\\nonpackaged\\chrome.exe"}):
            widget._check_call_context()
        app.processEvents()
        assert widget._call_context == "Google Meet"
        assert widget.name_label.text() == "Google Meet Call"
        assert not widget.call_mute_btn.isHidden()
        assert widget.screen_assist_btn.isHidden()
        assert widget._compact_size() == widget.CALL_SIZE

        with patch.object(widget, "_set_input_muted", return_value=True) as setter:
            widget.toggle_call_mute()
        setter.assert_called_once_with(True)
        assert widget._call_muted
        assert widget.call_mute_btn.text() == "Unmute"
        assert widget.status_label.text() == "Microphone muted"

        with patch.object(widget, "_active_microphone_clients", return_value=set()):
            for _ in range(3):
                widget._check_call_context()
        assert widget._call_context is None
        assert widget.call_mute_btn.isHidden()
        assert not widget.screen_assist_btn.isHidden()

        # A background Discord capability record must not claim the island
        # unless Discord was the foreground app when live use began.
        widget._foreground_title = "Codex"
        widget._foreground_process = "codex.exe"
        with patch.object(widget, "_active_microphone_clients",
                          return_value={r"microphone\\nonpackaged\\discord.exe"}):
            widget._check_call_context()
        assert widget._call_context is None
        assert widget.call_mute_btn.isHidden()

        widget._foreground_title = "Friends - Discord"
        widget._foreground_process = "Discord.exe"
        with patch.object(widget, "_active_microphone_clients",
                          return_value={r"microphone\\nonpackaged\\discord.exe"}), \
                patch.object(widget, "_discord_rtc_connected", return_value=False):
            widget._check_call_context()
        assert widget._call_context is None

        with patch.object(widget, "_active_microphone_clients",
                          return_value={r"microphone\\nonpackaged\\discord.exe"}), \
                patch.object(widget, "_discord_rtc_connected", return_value=True):
            widget._check_call_context()
        assert widget._call_context == "Discord"
        assert widget.name_label.text() == "Discord Call"
        assert not widget.call_mute_btn.isHidden()
        assert not widget._auto_hidden
        assert widget._call_hide_timer.isActive()

        widget.hide_call_island()
        widget._animation.setCurrentTime(widget._animation.duration())
        app.processEvents()
        assert widget.isHidden()
        assert widget._call_context == "Discord"

        widget.reveal_idle_island()
        app.processEvents()
        assert not widget.isHidden()
        assert widget._call_hide_timer.isActive()

        # A transient microphone ownership gap must not hide an established
        # call activity; the third consecutive miss ends it.
        with patch.object(widget, "_active_microphone_clients", return_value=set()):
            widget._check_call_context()
            widget._check_call_context()
        assert widget._call_context == "Discord"
        assert not widget.isHidden()
    finally:
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_compact_click_opens_feature_before_dexget_ai():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.update_media({
            "title": "Purpose Is Glorious",
            "artist": "Natalie Holt",
            "app": "YouTube Music",
            "playing": True,
            "position": 42,
            "duration": 189,
        })
        widget.toggle_island()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_feature_content()
        app.processEvents()

        assert widget.is_expanded
        assert widget._expanded_view == "feature"
        assert not widget.feature_panel.isHidden()
        assert widget.feature_eyebrow.text() == "NOW PLAYING"
        assert widget.feature_title.text() == "Purpose Is Glorious"
        assert not widget.media_feature_widget.isHidden()
        assert widget.feature_ai_btn.isHidden()
        assert widget.media_feature_title.text() == "Purpose Is Glorious"
        assert widget.media_feature_artist.text() == "Natalie Holt"
        assert widget.media_elapsed_label.text() == "0:42"
        assert widget.media_total_label.text() == "-2:27"
        assert widget.media_seek_slider.value() == 42
        assert widget.media_seek_slider.maximum() == 189
        media_size = widget._feature_expanded_size()
        assert media_size.height() == widget.MEDIA_FEATURE_HEIGHT
        assert widget.MEDIA_FEATURE_MIN_WIDTH <= media_size.width() <= widget.MEDIA_FEATURE_MAX_WIDTH
        screen_area = QApplication.primaryScreen().availableGeometry()
        media_geometry = widget._target_geometry(media_size)
        assert abs(media_geometry.center().x() - screen_area.center().x()) <= 1
        assert widget.scroll_area.isHidden()
        assert widget.input_frame.isHidden()
        assert widget._feature_collapse_timer.isActive()

        with patch.object(widget.media_worker, "control") as control:
            widget._control_expanded_media("play_pause")
            control.assert_called_once_with("play_pause")
            assert not widget._media["playing"]
            assert not widget.media_feature_play_btn.playing

        widget._auto_collapse_feature()
        assert not widget.is_expanded
        assert widget.feature_panel.isHidden()

        widget.expand_feature()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_feature_content()

        widget.open_ai_panel()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_expanded_content()
        app.processEvents()
        assert widget._expanded_view == "ai"
        assert widget.feature_panel.isHidden()
        assert not widget.scroll_area.isHidden()
        assert not widget.input_frame.isHidden()
        assert not widget._feature_collapse_timer.isActive()
    finally:
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_playback_start_does_not_duplicate_compact_header_over_player():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        paused = {
            "title": "Purpose Is Glorious", "artist": "Natalie Holt",
            "app": "YouTube Music", "playing": False,
            "position": 30, "duration": 189,
        }
        # Prepare an expanded media surface without running the normal paused
        # auto-hide path, then reproduce pressing Play inside that surface.
        widget._media = paused
        widget.expand_feature()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_feature_content()
        widget.update_media({**paused, "playing": True, "position": 31})
        app.processEvents()

        assert widget.is_expanded
        assert widget._expanded_view == "feature"
        assert not widget.feature_panel.isHidden()
        assert widget.title_bar.isHidden()
        assert widget.media_feature_play_btn.playing
    finally:
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_interrupted_expand_does_not_reveal_stale_content():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.expand_island()
        first_generation = widget._transition_generation
        widget.collapse_island()
        assert widget._transition_generation > first_generation
        widget._show_expanded_content()
        assert widget.scroll_area.isHidden()
        assert widget.input_frame.isHidden()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_screen_assist_submits_visible_text_and_blocks_proctoring():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget._screen_context_ready("A problem asks for a Python addition program")
        assert widget._screen_context
        assert "captured screen" in widget.input_field.placeholderText().lower()
        assert not widget.worker.busy.is_set()

        widget.input_field.setText("Write the complete program")
        with patch.object(widget.worker, "submit_text", return_value=True) as submit:
            widget.send_message()
            prompt = submit.call_args.args[0]
            assert "complete runnable code" in prompt
            assert "Write the complete program" in prompt
            assert "Python addition program" in prompt
            assert submit.call_args.kwargs["display_text"] == "Write the complete program"
            assert widget._screen_context is None

        with patch.object(widget, "_proctoring_active", return_value=True):
            with patch.object(widget, "add_message") as add_message:
                widget.start_screen_assist()
                assert "disabled" in add_message.call_args.args[1]
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()
