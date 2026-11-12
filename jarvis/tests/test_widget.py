import os
import json
import threading
import time
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton, QSizePolicy
from PyQt6.QtCore import QPoint, Qt, QSettings, QMimeData, QDateTime
from PyQt6.QtGui import QPixmap
from jarvis.agent.agent import Agent
from jarvis.agent.tool_registry import ToolRegistry
from jarvis.tools.base import RiskLevel, Tool, ToolResult
from widget import JarvisWidget, JarvisWorker, MediaSessionWorker, LocalSearchWorker


def test_media_worker_prefers_playing_session_over_stale_current_session():
    class Status:
        PLAYING = "playing"

    class Info:
        def __init__(self, status):
            self.playback_status = status

    class Session:
        def __init__(self, status):
            self.status = status

        def get_playback_info(self):
            return Info(self.status)

    paused = Session("paused")
    playing = Session("playing")

    class Manager:
        def get_current_session(self):
            return paused

        def get_sessions(self):
            return [paused, playing]

    assert MediaSessionWorker._select_session(Manager(), Status) is playing


def test_dashboard_question_is_sent_to_dexget_and_answer_stays_in_search_page():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(
            ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.dashboard_search_entry.setText("ask: Why is the sky blue?")
        with patch.object(widget.worker, "submit_text", return_value=True) as submit:
            widget._run_dashboard_search()
        submit.assert_called_once_with(
            "Why is the sky blue?", display_text="Why is the sky blue?")
        assert widget._dashboard_search_pending
        assert widget.dashboard_search_result.text() == "Asking Dexget…"

        widget.add_message("Jarvis", "Because shorter blue wavelengths scatter more.")
        assert not widget._dashboard_search_pending
        assert "blue wavelengths" in widget.dashboard_search_result.text()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_local_search_results_use_readable_scrollable_rows():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(
            ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.dashboard_search_entry.setText("brave")
        results = [
            {"path": f"C:/Apps/Brave{i}.exe", "name": f"Brave Browser {i}",
             "kind": "Application"}
            for i in range(8)
        ]
        widget._show_local_search_results("brave", results)
        rows = [
            widget.dashboard_search_results_layout.itemAt(i).widget()
            for i in range(widget.dashboard_search_results_layout.count())
            if widget.dashboard_search_results_layout.itemAt(i).widget() is not None
        ]
        assert len(rows) == 8
        assert all(row.height() == 52 for row in rows)
        assert "C:\\Apps\\Brave0.exe" in rows[0].text()
        assert widget.dashboard_search_results_scroll.widgetResizable()
        assert widget.dashboard_search_results_scroll.verticalScrollBarPolicy() == \
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        widget._show_local_search_results("brave", [])
        assert widget.dashboard_search_results_scroll.isHidden()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_local_search_fallback_finds_items_outside_windows_index(tmp_path):
    project = tmp_path / "Dexget Videos"
    project.mkdir()
    video = project / "demo recording.mp4"
    video.write_bytes(b"video")
    executable = tmp_path / "custom launcher.exe"
    executable.write_bytes(b"exe")

    worker = LocalSearchWorker()
    with patch.object(worker, "_fallback_roots", return_value=[str(tmp_path)]):
        video_results = worker._query_drive_catalog("demo recording")
        app_results = worker._query_drive_catalog("custom launcher")

    assert video_results[0]["path"] == str(video)
    assert video_results[0]["kind"] == "Video"
    assert app_results[0]["path"] == str(executable)
    assert app_results[0]["kind"] == "Application"


def test_local_search_scope_supports_drive_and_folder_shortcuts():
    worker = LocalSearchWorker()
    worker._drive_catalog = [
        (r"D:\Movies", "Movies", "Folder"),
        (r"D:\Movies\Action\film.mp4", "film.mp4", "Video"),
        (r"D:\Projects\MoviesApp.exe", "MoviesApp.exe", "Application"),
        (r"C:\Users\Ashwin\Movies", "Movies", "Folder"),
        (r"C:\Users\Ashwin\Movies\clip.mp4", "clip.mp4", "Video"),
    ]

    drive_results = worker._query_drive_catalog(":D Movies")
    suffix_results = worker._query_drive_catalog("Movies:D")
    folder_results = worker._query_drive_catalog(":Movies")
    nested_results = worker._query_drive_catalog(":D Movies Action")

    assert [item["path"] for item in drive_results] == [r"D:\Movies"]
    assert [item["path"] for item in suffix_results] == [r"D:\Movies"]
    assert {item["path"] for item in folder_results} == {
        r"D:\Movies", r"C:\Users\Ashwin\Movies"}
    assert [item["path"] for item in nested_results] == [
        r"D:\Movies\Action\film.mp4"]
    assert LocalSearchWorker._parse_search_scope(":C videos") == (
        "C", ["videos"])
    assert LocalSearchWorker._parse_search_scope("Movies:D") == (
        "D", ["Movies"])
    assert LocalSearchWorker._parse_search_scope("C: Videos lecture") == (
        "C", ["Videos", "lecture"])


def test_clipboard_history_captures_text_and_screenshots(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = QSettings("Dexget", "DynamicIsland")
    settings.remove("dashboard/clipboard_history")
    settings.remove("dashboard/clipboard")
    settings.sync()
    with patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}), \
            patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(
            ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
        try:
            QApplication.clipboard().setText("Dexget clipboard test")
            app.processEvents()
            assert widget._clipboard_history[0] == {
                "kind": "text", "text": "Dexget clipboard test"}

            screenshot = QPixmap(40, 24)
            screenshot.fill(Qt.GlobalColor.red)
            QApplication.clipboard().setPixmap(screenshot)
            app.processEvents()
            assert widget._clipboard_history[0]["kind"] == "image"
            assert os.path.isfile(widget._clipboard_history[0]["path"])

            long_text = "Dexget-" + ("long-text-" * 100)
            mixed_clipboard = QMimeData()
            mixed_clipboard.setText(long_text)
            mixed_clipboard.setImageData(screenshot.toImage())
            QApplication.clipboard().setMimeData(mixed_clipboard)
            app.processEvents()
            assert widget._clipboard_history[0] == {
                "kind": "text", "text": long_text}
            latest_row = widget.dashboard_clipboard_buttons[0]
            content_button = latest_row.findChildren(QPushButton)[0]
            copy_button = latest_row.findChild(
                QPushButton, "clipboardCopyButton")
            pin_button = latest_row.findChild(
                QPushButton, "clipboardPinButton")
            assert copy_button is not None
            assert pin_button is not None
            assert content_button.sizePolicy().horizontalPolicy() == \
                QSizePolicy.Policy.Ignored
            assert content_button.text().endswith("…")
            assert widget.dashboard_clipboard_scroll.widgetResizable()
            assert widget.dashboard_clipboard_scroll.verticalScrollBarPolicy() == \
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            pin_button.click()
            assert widget._clipboard_history[0]["pinned"] is True

            QApplication.clipboard().setText("newer unpinned item")
            app.processEvents()
            assert widget._clipboard_history[0]["pinned"] is True
            assert widget._clipboard_history[1]["text"] == "newer unpinned item"
            assert widget.dashboard_clipboard_clear.text() == "Clear"
            assert widget.findChild(
                QPushButton, "clipboardClearButton") is not None
            widget.dashboard_clipboard_clear.click()
            app.processEvents()
            assert len(widget._clipboard_history) == 1
            assert widget._clipboard_history[0]["pinned"] is True
            with open(widget._clipboard_history_file(), encoding="utf-8") as handle:
                stored = json.load(handle)
            assert len(stored) == 1
            assert stored[0]["pinned"] is True
        finally:
            widget.media_worker.shutdown()
            widget.media_worker.wait(2000)
            widget.worker.shutdown()
            widget.worker.wait(2000)
            widget.close()
            app.processEvents()
            settings.remove("dashboard/clipboard_history")


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
        assert not widget._auto_hidden
        minimize_target = widget._animation_target
        assert minimize_target.size() == widget.COLLAPSED_SIZE
        widget._animation.setCurrentTime(widget._animation.duration() // 2)
        assert widget.title_bar_opacity.opacity() == 1.0
        deadline = time.monotonic() + 1
        while widget._animation and widget._animation.state() == widget._animation.State.Running and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert not widget.isHidden()
        assert widget.default_status_widget.isVisible()
        assert widget.worker.isRunning()
        assert widget.media_worker.isRunning()
        widget._check_hot_zone()
        assert widget._media_manually_hidden
        assert not widget._auto_hidden
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
        while widget._animation and widget._animation.state() == widget._animation.State.Running and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert not widget.isHidden()
        assert widget.default_status_widget.isVisible()

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
        while widget._animation and widget._animation.state() == widget._animation.State.Running and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert not widget.isHidden()

        widget.update_media({})
        assert widget.name_label.text() == "DEXGET"
        assert widget.album_art.isHidden()
        assert widget.previous_btn.isHidden()
        assert widget._compact_size().width() == 178
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_idle_island_stays_visible_as_top_mounted_notch():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget._assistant_state = "Idle"
        widget.hide_idle_island()
        assert not widget._auto_hidden
        assert widget.windowOpacity() == 1.0
        widget._animation.setCurrentTime(widget._animation.duration())
        app.processEvents()
        assert not widget.mask().isEmpty()
        assert widget.mask().contains(QPoint(1, 1))
        assert not widget.mask().contains(
            QPoint(1, widget.COLLAPSED_SIZE.height() - 1))
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
        assert widget.close_btn.isHidden()
        assert widget.tray_force_close_action.text() == "Force close Dexget"
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
        assert widget.close_btn.isHidden()
        assert widget.tray_force_close_action.text() == "Force close Dexget"
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
        with patch.object(widget, "_play_notification_sound") as sound:
            widget.show_notification_activity(
                "WhatsApp", "New message", "Ashwin: Hello")
            sound.assert_called_once_with()
        assert widget._notification_active
        assert widget._compact_size() == widget.NOTIFICATION_SIZE
        assert widget.notification_icon.text() == "W"
        assert widget.notification_title.text() == "WhatsApp"
        assert widget.notification_body.text() == "New message\nAshwin: Hello"
        assert widget.notification_time.text()
        assert widget.title_bar.height() == widget.NOTIFICATION_SIZE.height()
        assert "rgba(12, 14, 18, 244)" in widget.container.styleSheet()
        assert "color: white" in widget.notification_title.styleSheet()
        assert not widget.notification_identity.isHidden()
        assert not widget.notification_time.isHidden()
        assert widget.identity_widget.isHidden()

        widget.finish_notification_activity()
        assert not widget._notification_active
        assert widget.notification_identity.isHidden()
        assert widget.notification_time.isHidden()
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

        # Discord is intentionally excluded from contextual call controls,
        # even when it owns the microphone and is the foreground app.
        widget._foreground_title = "Friends - Discord"
        widget._foreground_process = "Discord.exe"
        with patch.object(widget, "_active_microphone_clients",
                          return_value={r"microphone\\nonpackaged\\discord.exe"}):
            widget._check_call_context()
        assert widget._call_context is None
        assert widget.call_mute_btn.isHidden()
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
        assert abs(widget.geometry().center().x() - screen_area.center().x()) <= 1
        assert widget.container.size() == media_size
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
        assert widget._feature_expanded_size() == widget.DASHBOARD_EXPANDED_SIZE
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


def test_default_island_expands_without_resource_summary():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget._media = {}
        widget._sync_compact_surface()
        widget._update_default_status()
        assert widget.COLLAPSED_SIZE.width() == 178
        assert widget.COLLAPSED_SIZE.height() == 34
        assert not hasattr(widget, "default_network_indicator")
        assert not widget.default_status_widget.isHidden()
        assert widget.title_bar.height() == widget.COLLAPSED_SIZE.height()
        assert widget.identity_widget.isHidden()
        assert widget.status_dot.isHidden()
        assert widget.screen_assist_btn.isHidden()
        assert "AM" in widget.default_clock_label.text() or "PM" in widget.default_clock_label.text()

        widget.toggle_island()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_feature_content()
        app.processEvents()
        assert widget.is_expanded
        assert not widget.dashboard_widget.isHidden()
        assert widget.dashboard_wifi_card.isHidden()
        assert widget.dashboard_bluetooth_card.isHidden()
        assert widget.dashboard_controls_card.isHidden()
        assert widget.dashboard_stats_card.isHidden()
        assert not widget.dashboard_nav_buttons["home"].isHidden()
        assert widget.dashboard_stack.currentWidget() is widget.dashboard_pages["home"]
        launcher_labels = [button.text() for button in widget.dashboard_launcher_buttons]
        assert any("Explorer" in label for label in launcher_labels)
        assert any("Terminal" in label for label in launcher_labels)
        assert any("Settings" in label for label in launcher_labels)
        assert set(widget.dashboard_launcher_rows) == {
            "application", "script", "shortcut", "automation"}
    finally:
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_calendar_event_is_saved_listed_and_reminded():
    app = QApplication.instance() or QApplication([])
    settings = QSettings("Dexget", "DynamicIsland")
    previous = settings.value("calendar/events", "[]")
    settings.setValue("calendar/events", "[]")
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(
            ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        when = QDateTime.currentDateTime().addSecs(30)
        widget._select_calendar_date(when.date())
        widget.dashboard_event_title.setText("Submit assignment")
        widget.dashboard_event_kind.setCurrentText("Task")
        widget.dashboard_event_time.setDateTime(when)
        widget.dashboard_event_reminder.setCurrentIndex(0)
        widget._add_calendar_event()
        assert len(widget._calendar_events) == 1
        assert widget._calendar_events[0]["title"] == "Submit assignment"
        assert "Submit assignment" in json.dumps(
            json.loads(settings.value("calendar/events")))
        with patch.object(widget, "show_notification_activity") as notify:
            widget.dashboard_event_time.setDateTime(QDateTime.currentDateTime())
            widget._calendar_events[0]["time"] = QDateTime.currentDateTime().toString(
                Qt.DateFormat.ISODate)
            widget._calendar_events[0]["notified"] = False
            widget._check_calendar_reminders()
            notify.assert_called_once()
    finally:
        settings.setValue("calendar/events", previous)
        widget.media_worker.shutdown()
        widget.worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_dashboard_launcher_dispatches_without_agent_or_model():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        with patch.object(widget, "_launch_program") as launch:
            widget._run_dashboard_launcher({
                "kind": "application", "label": "Editor", "payload": "notepad.exe"})
            launch.assert_called_once_with("notepad.exe")
        button = widget._add_launcher_button({
            "kind": "shortcut", "label": "Save", "payload": "ctrl+s"})
        assert "Save" in button.text()
        assert button.toolTip() == "ctrl+s"
        assert not button.icon().isNull()
        widget._set_launcher_edit_mode(True)
        assert widget.dashboard_launcher_edit.text() == "Done"
        assert button.text().startswith("×")
        widget._set_launcher_edit_mode(False)
        assert button.text() == "Save"
        recording = {"version": 1, "actions": [
            {"type": "mouse_down", "x": 100, "y": 120,
             "button": "left", "delay": 0.1}]}
        with patch.object(widget, "_play_recorded_automation") as play:
            widget._run_dashboard_launcher({
                "kind": "automation", "label": "Join Hangout + Camera",
                "payload": __import__("json").dumps(recording)})
            play.assert_called_once()
            assert play.call_args.args[1] == recording
    finally:
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_timer_activity_counts_down_and_restores_default_surface():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.start_timer(215)
        app.processEvents()
        assert widget._timer_active
        assert widget._timer_running
        assert widget._compact_size() == widget.TIMER_SIZE
        assert widget.TIMER_SIZE.width() == 270
        assert widget.timer_pause_btn.__class__.__name__ == "TimerToggleButton"
        assert not widget.timer_status_widget.isHidden()
        assert widget.default_status_widget.isHidden()
        assert widget.timer_remaining_label.text() == "3:35"
        assert widget.close_btn.isHidden()

        widget.toggle_timer()
        assert not widget._timer_running
        assert widget.timer_pause_btn.text() == "▶"
        paused = widget._timer_remaining
        widget.toggle_timer()
        assert widget._timer_running
        assert widget.timer_pause_btn.text() == "Ⅱ"
        assert widget._timer_remaining == paused

        widget.cancel_timer()
        app.processEvents()
        assert not widget._timer_active
        assert widget.timer_status_widget.isHidden()
        assert not widget.default_status_widget.isHidden()
    finally:
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_timer_started_from_default_page_owns_compact_surface_over_media():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.update_media({
            "title": "SEM DEMORA (Slowed)", "artist": "DJ Samir",
            "app": "YouTube Music", "playing": True,
            "position": 53, "duration": 163,
        })
        widget.show_default_page()
        assert widget._default_page_override

        widget.start_timer(215)
        app.processEvents()
        assert not widget._default_page_override
        assert widget._timer_active
        assert widget._compact_size() == widget.TIMER_SIZE
        assert not widget.timer_status_widget.isHidden()
        assert widget.default_status_widget.isHidden()
        assert widget.media_feature_widget.isHidden()
        assert widget.dashboard_widget.isHidden()
        assert widget._media.get("title") == "SEM DEMORA (Slowed)"
    finally:
        widget.cancel_timer()
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_music_and_timer_are_switchable_activity_pages():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.update_media({"title": "Song", "artist": "Artist", "playing": True})
        widget.show_default_page()
        widget.start_timer(60)
        assert widget._activity_page == "timer"
        widget._cycle_activity_page(1)
        widget._page_switch_animation.setCurrentTime(
            widget._page_switch_animation.duration())
        assert widget._activity_page == "media"
        assert not widget.identity_widget.isHidden()
        assert widget.timer_status_widget.isHidden()
        assert widget._compact_size() != widget.TIMER_SIZE
        assert widget._compact_size().height() == widget.MEDIA_SIZE.height()
        widget._last_page_switch = 0
        widget._cycle_activity_page(-1)
        widget._page_switch_animation.setCurrentTime(
            widget._page_switch_animation.duration())
        assert widget._activity_page == "timer"
        assert not widget.timer_status_widget.isHidden()
        assert widget._media.get("title") == "Song"
    finally:
        widget.cancel_timer()
        widget.worker.shutdown()
        widget.media_worker.shutdown()
        widget.worker.wait(2000)
        widget.media_worker.wait(2000)
        widget.close()
        app.processEvents()


def test_activity_switch_cannot_be_interrupted_before_midpoint():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.update_media({"title": "Song", "artist": "Artist", "playing": True})
        widget.show_default_page(animate=False)
        assert widget.width() == 230
        widget._last_page_switch = 0
        widget._cycle_activity_page(1)
        first_animation = widget._page_switch_animation
        first_animation.setCurrentTime(40)
        widget._last_page_switch = 0
        widget._cycle_activity_page(-1)
        assert widget._page_switch_animation is first_animation
        first_animation.setCurrentTime(first_animation.duration())
        assert widget._activity_page == "media"
        assert widget.windowOpacity() == 1.0
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


def test_expanded_call_collapses_after_pointer_leaves_but_not_during_input():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget._call_context = "Google Meet"
        widget._refresh_call_layout()
        widget.expand_feature()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_feature_content()
        assert widget.is_expanded
        assert not widget.dashboard_widget.isHidden()
        assert widget.feature_eyebrow.isHidden()
        assert widget.feature_title.isHidden()
        assert widget.feature_primary_btn.isHidden()
        assert widget.title_bar.isHidden()

        with patch.object(widget, "_pointer_inside_island", return_value=True):
            widget._auto_collapse_expanded()
            assert widget.is_expanded

        with patch.object(widget, "_pointer_inside_island", return_value=False), \
                patch.object(widget, "_input_interaction_active", return_value=False):
            widget._auto_collapse_expanded()
            assert not widget.is_expanded
            assert widget._compact_size() == widget.CALL_SIZE

        widget.expand_island()
        with patch.object(widget, "_pointer_inside_island", return_value=False), \
                patch.object(widget, "_input_interaction_active", return_value=True):
            widget._auto_collapse_expanded()
            assert widget.is_expanded
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_activity_page_swipe_preserves_call_and_restores_it():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget._call_context = "Google Meet"
        widget._refresh_call_layout()
        assert not widget.call_mute_btn.isHidden()

        widget.show_default_page()
        app.processEvents()
        assert widget._default_page_override
        assert widget._call_context == "Google Meet"
        assert widget._compact_size().width() == 178
        assert not widget.default_status_widget.isHidden()
        assert widget.call_mute_btn.isHidden()

        widget.expand_feature()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_feature_content()
        assert not widget.dashboard_widget.isHidden()

        widget.show_activity_page()
        app.processEvents()
        assert not widget._default_page_override
        assert widget._call_context == "Google Meet"
        assert widget._compact_size() == widget.CALL_SIZE
        assert not widget.call_mute_btn.isHidden()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()


def test_default_page_expands_to_dashboard_size_while_media_continues():
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        widget.update_media({
            "title": "SEM DEMORA (Slowed)", "artist": "DJ Samir",
            "app": "YouTube Music", "playing": True,
            "position": 53, "duration": 163,
        })
        widget.show_default_page()
        assert widget._default_page_override
        assert widget._feature_expanded_size() == widget.DASHBOARD_EXPANDED_SIZE
        assert widget._expanded_size() == widget.DASHBOARD_EXPANDED_SIZE

        widget.expand_feature()
        widget._animation.setCurrentTime(widget._animation.duration())
        widget._show_feature_content()
        assert widget.dashboard_widget.isVisible()
        assert widget.media_feature_widget.isHidden()
        assert widget._media.get("title") == "SEM DEMORA (Slowed)"
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


def test_file_shelf_holds_local_file_and_restores_default_notch(tmp_path):
    app = QApplication.instance() or QApplication([])
    with patch("widget.jarvis_integration.build_agent") as build:
        build.side_effect = lambda **kwargs: Agent(
            ToolRegistry(confirm_fn=kwargs["confirm_fn"]))
        widget = JarvisWidget()
    try:
        held_file = tmp_path / "report.txt"
        held_file.write_text("Dexget file shelf", encoding="utf-8")
        second_file = tmp_path / "roadmap.pdf"
        second_file.write_bytes(b"%PDF shelf")

        assert widget._store_file_shelf([str(held_file), str(held_file)])
        assert widget._store_file_shelf([str(second_file)])
        app.processEvents()
        assert widget._file_shelf_paths == [
            str(held_file.resolve()), str(second_file.resolve())]
        assert widget._compact_size() == widget.FILE_SHELF_SIZE
        assert widget._feature_expanded_size() == widget.FILE_SHELF_EXPANDED_SIZE
        assert not widget.file_shelf_widget.isHidden()
        assert not widget.default_status_widget.isHidden()
        assert not widget.default_clock_label.isHidden()
        assert not widget.default_battery_indicator.isHidden()
        assert widget.file_shelf_widget.name_label.text() == "report.txt"
        assert widget.file_shelf_widget.count_label.text() == "2"
        assert widget.file_shelf_widget.name_label.isHidden()
        assert widget.file_shelf_widget.count_label.isHidden()
        assert widget.file_shelf_widget.hint_label.isHidden()
        assert widget.file_shelf_title.text().endswith("2")
        assert widget.file_shelf_share_btn.text() == "Share"
        assert widget.file_shelf_phone_btn.text() == "Share to phone"

        with patch.object(widget, "_start_phone_transfer") as start_transfer:
            widget._share_file_shelf_to_phone()
            assert widget._phone_transfer_view
            assert widget._feature_uses_dashboard()
            assert widget.dashboard_stack.currentWidget() is widget.dashboard_pages["transfer"]
            start_transfer.assert_called_once_with()
        widget._phone_transfer_view = False

        mime = widget._file_shelf_mime_data()
        assert mime.hasUrls()
        assert len(mime.urls()) == 2
        assert os.path.normcase(os.path.normpath(mime.urls()[0].toLocalFile())) == \
            os.path.normcase(os.path.normpath(str(held_file.resolve())))
        assert held_file.exists()

        widget._clear_file_shelf()
        app.processEvents()
        assert widget._file_shelf_paths == []
        assert widget.file_shelf_widget.isHidden()
        assert not widget.default_status_widget.isHidden()
        assert widget._compact_size() == widget.COLLAPSED_SIZE
        assert held_file.exists()
        assert second_file.exists()
    finally:
        widget.media_worker.shutdown()
        widget.media_worker.wait(2000)
        widget.worker.shutdown()
        assert widget.worker.wait(2000)
        widget.close()
        app.processEvents()
