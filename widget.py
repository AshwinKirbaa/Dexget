import sys
import threading
import queue
import asyncio
import time
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QScrollArea, 
                             QFrame, QSizePolicy, QGraphicsDropShadowEffect,
                             QGraphicsOpacityEffect)
from PyQt6.QtCore import (Qt, QPoint, QThread, pyqtSignal, QTimer, QSize,
                          QRect, QPropertyAnimation, QEasingCurve,
                          QParallelAnimationGroup,
                          QRectF, QAbstractAnimation)
from PyQt6.QtGui import (QColor, QFont, QIcon, QPainter, QBrush, QPen,
                         QPainterPath, QRegion, QCursor, QPixmap)

import jarvis_integration


class BatteryIndicator(QWidget):
    """Small Apple-style battery glyph used by the charging Live Activity."""
    def __init__(self):
        super().__init__()
        self.percent = 0
        self.low_power = False
        self.setFixedSize(42, 24)

    def set_percent(self, percent):
        self.percent = max(0, min(100, int(percent)))
        self.update()

    def set_low_power(self, enabled):
        self.low_power = bool(enabled)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = QRectF(1.5, 2.5, 35.0, 19.0)
        painter.setPen(QPen(QColor("#8b929a"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(outline, 5, 5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#8b929a"))
        painter.drawRoundedRect(QRectF(37.5, 8.0, 3.5, 8.0), 1.5, 1.5)
        fill_width = 30.0 * self.percent / 100.0
        painter.setBrush(QColor("#ff453a") if self.low_power else QColor("#32d74b"))
        painter.drawRoundedRect(QRectF(4.0, 5.0, fill_width, 14.0), 3.5, 3.5)


class EarbudsIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(46, 40)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        white = QColor("#f7f8fa")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(white)
        # Two compact AirPods-style silhouettes. The asymmetry of each stem
        # keeps the glyph recognizable at Dynamic Island scale.
        painter.drawEllipse(QRectF(4, 3, 16, 17))
        painter.drawRoundedRect(QRectF(12, 14, 6, 22), 3, 3)
        painter.drawEllipse(QRectF(26, 3, 16, 17))
        painter.drawRoundedRect(QRectF(28, 14, 6, 22), 3, 3)
        painter.setBrush(QColor("#101216"))
        painter.drawEllipse(QRectF(7, 8, 4, 5))
        painter.drawEllipse(QRectF(35, 8, 4, 5))


class ConnectionRing(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(38, 38)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(48, 209, 88, 45), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(4, 4, 30, 30))
        painter.setPen(QPen(QColor("#30d158"), 4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(4, 4, 30, 30), 38 * 16, 286 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#30d158"))
        painter.drawEllipse(QRectF(29.3, 27.0, 4.5, 4.5))

class JarvisWorker(QThread):
    state_changed = pyqtSignal(str, str) # state_name, subtitle
    message_received = pyqtSignal(str, str) # role, text
    confirmation_requested = pyqtSignal(str)
    busy_changed = pyqtSignal(bool)
    
    def __init__(self, agent=None):
        super().__init__()
        self.agent = agent
        self.vm = None
        self.listening_enabled = False
        self.commands = queue.Queue()
        self.shutdown_event = threading.Event()
        self.busy = threading.Event()
        self.confirmation_event = threading.Event()
        self.confirmation_answer = False
        self.voice_thread = None
        self.submission_lock = threading.Lock()
        self.voice_pause = threading.Event()
        
    def run(self):
        while not self.shutdown_event.is_set():
            try:
                text = self.commands.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.state_changed.emit("Processing", "Planning...")
                result = jarvis_integration.handle_command(self.agent, text, reset_cancel=False)
                if result and result.text:
                    self.message_received.emit("Jarvis", result.text)
                    if self.vm and not self.agent.registry.cancel_event.is_set():
                        from jarvis.voice.voice_manager import clean_response
                        self.vm.tts.speak(clean_response(result.text))
            except Exception as exc:
                self.message_received.emit("Jarvis", f"Task failed: {exc}")
            finally:
                self.busy.clear()
                self.busy_changed.emit(False)
                self.state_changed.emit("Idle", "Ready")

    def _listen(self):
        try:
            from jarvis.voice.voice_manager import VoiceManager
            from jarvis.voice.wake_word import strip_wake_word
            self.vm = VoiceManager(self.agent)
            while not self.shutdown_event.is_set():
                if not self.listening_enabled:
                    self.shutdown_event.wait(0.2)
                    continue
                result = self.vm.stt.listen(cancel_event=self.voice_pause)
                if result and result.get("error"):
                    raise RuntimeError(result["error"])
                if result and result.get("text") and self.listening_enabled:
                    text = result["text"]
                    self.submit_text(strip_wake_word(text) or text)
        except Exception as exc:
            self.listening_enabled = False
            self.message_received.emit("Jarvis", f"Voice unavailable: {exc}. Text input is ready.")
        finally:
            if self.vm:
                self.vm.stt.close()

    def enable_listening(self, enabled):
        self.listening_enabled = enabled
        if enabled:
            self.voice_pause.clear()
        else:
            self.voice_pause.set()
        if enabled and (self.voice_thread is None or not self.voice_thread.is_alive()):
            self.voice_thread = threading.Thread(target=self._listen, daemon=True)
            self.voice_thread.start()

    def confirm(self, prompt):
        self.confirmation_answer = False
        self.confirmation_event.clear()
        self.confirmation_requested.emit(prompt)
        while not self.confirmation_event.wait(0.1):
            if self.shutdown_event.is_set() or self.agent.registry.cancel_event.is_set():
                return False
        return self.confirmation_answer and not self.agent.registry.cancel_event.is_set()

    def answer_confirmation(self, approved):
        self.confirmation_answer = approved
        self.confirmation_event.set()

    def cancel(self):
        self.agent.cancel()
        self.answer_confirmation(False)
        if self.vm:
            self.vm.tts.stop()
        # If a command has not started yet, remove it so it cannot clear cancellation.
        try:
            self.commands.get_nowait()
            self.busy.clear()
            self.busy_changed.emit(False)
        except queue.Empty:
            pass
        self.state_changed.emit("Stopping", "Stopping after the current operation..." if self.busy.is_set() else "Stopped")

    def shutdown(self):
        self.shutdown_event.set()
        self.voice_pause.set()
        self.listening_enabled = False
        self.cancel()
        
    def submit_text(self, text, display_text=None):
        if text.lower().strip().rstrip(".!") in ("stop", "cancel", "never mind", "nevermind"):
            self.cancel()
            return True
        with self.submission_lock:
            if self.busy.is_set() or self.shutdown_event.is_set():
                return False
            self.agent.registry.cancel_event.clear()
            self.busy.set()
            self.busy_changed.emit(True)
            self.message_received.emit("User", display_text if display_text is not None else text)
            self.commands.put(text)
            return True


class ScreenAssistWorker(QThread):
    """Extract accessibility text without blocking the island animation."""
    text_ready = pyqtSignal(str)
    extraction_failed = pyqtSignal(str)

    def __init__(self, hwnd):
        super().__init__()
        self.hwnd = hwnd

    def run(self):
        try:
            from pywinauto import Desktop
            window = Desktop(backend="uia").window(handle=self.hwnd)
            parts = []
            seen = set()
            for control in [window] + window.descendants():
                try:
                    text = (control.window_text() or "").strip()
                except Exception:
                    continue
                if not text or text in seen:
                    continue
                seen.add(text)
                parts.append(text)
                if sum(len(value) for value in parts) >= 12000:
                    break
            content = "\n".join(parts).strip()
            if content:
                self.text_ready.emit(content[:12000])
            else:
                self.extraction_failed.emit(
                    "I couldn't read text from that window. Select or open the question and try again.")
        except Exception as exc:
            self.extraction_failed.emit(f"Screen Assist couldn't read the active window: {exc}")


class MediaSessionWorker(QThread):
    """Poll Windows' global media session without blocking the Qt UI."""
    media_changed = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.shutdown_event = threading.Event()
        self.actions = queue.Queue()

    def run(self):
        try:
            asyncio.run(self._run_media_loop())
        except Exception:
            self.media_changed.emit({})

    async def _run_media_loop(self):
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as SessionManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )
        manager = await SessionManager.request_async()
        previous = None
        while not self.shutdown_event.is_set():
            session = manager.get_current_session()
            while session and not self.actions.empty():
                action = self.actions.get_nowait()
                if action == "previous":
                    await session.try_skip_previous_async()
                elif action == "next":
                    await session.try_skip_next_async()
                elif action == "play_pause":
                    info = session.get_playback_info()
                    if info.playback_status == PlaybackStatus.PLAYING:
                        await session.try_pause_async()
                    else:
                        await session.try_play_async()
            current = {}
            if session:
                try:
                    props = await session.try_get_media_properties_async()
                    info = session.get_playback_info()
                    artwork = await self._read_thumbnail(props.thumbnail)
                    current = {
                        "title": (props.title or "Now playing").strip(),
                        "artist": (props.artist or props.album_artist or "").strip(),
                        "app": session.source_app_user_model_id or "Media",
                        "playing": info.playback_status == PlaybackStatus.PLAYING,
                        "artwork": artwork,
                    }
                except Exception:
                    current = {}
            if current != previous:
                previous = current
                self.media_changed.emit(current)
            await asyncio.sleep(2.0)

    @staticmethod
    async def _read_thumbnail(thumbnail):
        """Return the current media artwork as encoded image bytes."""
        if not thumbnail:
            return b""
        try:
            from winrt.windows.storage.streams import DataReader
            stream = await thumbnail.open_read_async()
            size = min(int(stream.size), 8 * 1024 * 1024)
            if size <= 0:
                return b""
            reader = DataReader(stream)
            loaded = int(await reader.load_async(size))
            data = bytearray(loaded)
            reader.read_bytes(data)
            reader.close()
            stream.close()
            return bytes(data)
        except Exception:
            return b""

    def control(self, action):
        self.actions.put(action)

    def shutdown(self):
        self.shutdown_event.set()

class MessageWidget(QWidget):
    def __init__(self, role, text):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 5)
        
        self.label = QLabel(text)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        font = QFont("Segoe UI", 10)
        self.label.setFont(font)
        self.label.setMargin(10)
        
        if role == "User":
            self.label.setStyleSheet("background-color: rgba(60, 120, 200, 150); color: white; border-radius: 10px;")
            layout.addStretch()
            layout.addWidget(self.label, stretch=4)
        else:
            self.label.setStyleSheet("background-color: rgba(50, 50, 50, 200); color: white; border-radius: 10px;")
            layout.addWidget(self.label, stretch=4)
            layout.addStretch()
            
        self.setLayout(layout)

class JarvisWidget(QWidget):
    HIDDEN_SIZE = QSize(120, 4)
    MINIMIZE_SIZE = QSize(120, 32)
    COLLAPSED_SIZE = QSize(300, 48)
    MEDIA_SIZE = QSize(520, 60)
    CHARGING_SIZE = QSize(360, 56)
    LOW_POWER_SIZE = QSize(350, 56)
    HEADSET_SIZE = QSize(350, 56)
    NOTIFICATION_SIZE = QSize(370, 64)
    MEDIA_MIN_WIDTH = 400
    MEDIA_BASE_WIDTH = 300
    EXPANDED_SIZE = QSize(440, 430)
    TOP_MARGIN = 8
    HOT_ZONE_WIDTH = 140
    HOT_ZONE_HEIGHT = 12
    COMPACT_TRANSITION_MS = 320
    PANEL_TRANSITION_MS = 380

    def __init__(self):
        super().__init__()
        self.is_expanded = False
        self._animation = None
        self._animation_target = None
        self._transition_generation = 0
        self._visibility_generation = 0
        self._is_hiding = False
        self._hot_zone_armed = True
        self._content_animation = None
        self._media = {}
        self._media_manually_hidden = False
        self._auto_hidden = False
        self._hover_leave_at = None
        self._assistant_state = "Idle"
        self._assistant_subtitle = "Ready"
        self._last_media_key = None
        self._pulse_phase = False
        self._charging_active = False
        self._pre_charging_expanded = False
        self._last_power_plugged = None
        self._low_power_active = False
        self._last_energy_saver = None
        self._notification_active = False
        self._notification_listener = None
        self._known_notification_ids = set()
        self._last_external_hwnd = None
        self.screen_assist_worker = None
        self._screen_context = None
        self._headset_active = False
        self._last_audio_device_id = None
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self.collapse_island)
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(100)
        self._hover_timer.timeout.connect(self._check_hot_zone)
        self._hover_timer.start()
        self._media_pulse_timer = QTimer(self)
        self._media_pulse_timer.setInterval(1200)
        self._media_pulse_timer.timeout.connect(self._pulse_media_indicator)
        self._charging_hide_timer = QTimer(self)
        self._charging_hide_timer.setSingleShot(True)
        self._charging_hide_timer.timeout.connect(self.finish_charging_activity)
        self._battery_timer = QTimer(self)
        self._battery_timer.setInterval(5000)
        self._battery_timer.timeout.connect(self._check_battery_state)
        self._battery_timer.start()
        self._low_power_hide_timer = QTimer(self)
        self._low_power_hide_timer.setSingleShot(True)
        self._low_power_hide_timer.timeout.connect(self.finish_low_power_activity)
        self._headset_hide_timer = QTimer(self)
        self._headset_hide_timer.setSingleShot(True)
        self._headset_hide_timer.timeout.connect(self.finish_headset_activity)
        self._audio_device_timer = QTimer(self)
        self._audio_device_timer.setInterval(5000)
        self._audio_device_timer.timeout.connect(self._check_audio_device)
        self._audio_device_timer.start()
        self._notification_hide_timer = QTimer(self)
        self._notification_hide_timer.setSingleShot(True)
        self._notification_hide_timer.timeout.connect(self.finish_notification_activity)
        self._notification_timer = QTimer(self)
        self._notification_timer.setInterval(3000)
        self._notification_timer.timeout.connect(self._poll_notifications)
        self._foreground_timer = QTimer(self)
        self._foreground_timer.setInterval(750)
        self._foreground_timer.timeout.connect(self._track_foreground_window)
        self._foreground_timer.start()
        self.initUI()
        # Copilot/startup presents only the compact island. The conversation
        # panel opens later when the user clicks the island.
        self.scroll_area.hide()
        self.input_frame.hide()
        
        self.worker = JarvisWorker()
        self.agent = jarvis_integration.build_agent(
            on_progress=lambda msg: self.worker.state_changed.emit("Processing", msg),
            confirm_fn=self.worker.confirm,
        )
        self.worker.agent = self.agent
        self.worker.state_changed.connect(self.update_state)
        self.worker.message_received.connect(self.add_message)
        self.worker.confirmation_requested.connect(self.show_confirmation)
        self.worker.busy_changed.connect(self.set_busy)
        self.worker.finished.connect(self.close)
        self._closing = False
        self.worker.start()
        self.media_worker = MediaSessionWorker()
        self.media_worker.media_changed.connect(self.update_media)
        self.media_worker.start()
        if self.agent.registry.unavailable:
            self.add_message("Jarvis", "Unavailable capabilities: " +
                             "; ".join(f"{name}: {error}" for name, error in self.agent.registry.unavailable.items()))
        QTimer.singleShot(0, self._place_top_center)
        QTimer.singleShot(3500, self.collapse_island)
        QTimer.singleShot(5000, self._start_notification_listener)

    def initUI(self):
        # Frameless window and Tool flag so it doesn't show in the taskbar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.EXPANDED_SIZE)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Main Container with Glassmorphism ---
        self.container = QFrame()
        self.container.setObjectName("Container")
        self._apply_default_container_style()
        # Avoid QGraphicsDropShadowEffect here. On a translucent top-level
        # Windows window it re-rasterizes the entire surface on every resize
        # frame and produces visible flashes during pill-to-panel expansion.
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # --- Title Bar (Draggable) ---
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(48)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(14, 0, 12, 0)

        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(18)
        self.status_dot.setStyleSheet("color: #39e58c; font-size: 15px;")

        self.album_art = QLabel()
        self.album_art.setFixedSize(40, 40)
        self.album_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.album_art.setStyleSheet("background: #202329; border-radius: 5px;")
        self.album_art.hide()

        self.identity_widget = QWidget()
        identity_layout = QVBoxLayout(self.identity_widget)
        identity_layout.setContentsMargins(0, 7, 0, 7)
        identity_layout.setSpacing(0)
        self.name_label = QLabel("DEXGET")
        self.name_label.setMaximumWidth(200)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: white; letter-spacing: 1px;")
        
        self.status_label = QLabel("Ready")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color: #9da7b3;")
        identity_layout.addWidget(self.name_label)
        identity_layout.addWidget(self.status_label)

        self.charging_label = QLabel("Charging")
        self.charging_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.charging_label.setStyleSheet("color: white;")
        self.charging_percent = QLabel("0%")
        self.charging_percent.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.charging_percent.setStyleSheet("color: #32d74b;")
        self.battery_indicator = BatteryIndicator()
        self.charging_label.hide()
        self.charging_percent.hide()
        self.battery_indicator.hide()

        self.low_power_label = QLabel("Low Battery")
        self.low_power_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.low_power_label.setStyleSheet("color: white;")
        self.low_power_percent = QLabel("0%")
        self.low_power_percent.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.low_power_percent.setStyleSheet("color: #ff6961;")
        self.low_power_battery = BatteryIndicator()
        self.low_power_battery.set_low_power(True)
        self.low_power_label.hide()
        self.low_power_percent.hide()
        self.low_power_battery.hide()

        self.notification_icon = QLabel("✉")
        self.notification_icon.setFixedSize(26, 26)
        self.notification_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_icon.setFont(QFont("Segoe UI Symbol", 13, QFont.Weight.DemiBold))
        self.notification_icon.setStyleSheet(
            "background: transparent; color: #aeb5bf;")
        self.notification_identity = QWidget()
        notification_layout = QVBoxLayout(self.notification_identity)
        notification_layout.setContentsMargins(0, 5, 0, 5)
        notification_layout.setSpacing(0)
        self.notification_title = QLabel("Notification")
        self.notification_title.setMaximumWidth(290)
        self.notification_title.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.notification_title.setStyleSheet("color: white;")
        self.notification_body = QLabel("")
        self.notification_body.setMaximumWidth(290)
        self.notification_body.setFont(QFont("Segoe UI", 9))
        self.notification_body.setStyleSheet("color: #aeb5bf;")
        notification_layout.addWidget(self.notification_title)
        notification_layout.addWidget(self.notification_body)
        self.notification_icon.hide()
        self.notification_identity.hide()

        self.earbuds_indicator = EarbudsIndicator()
        self.headset_identity = QWidget()
        headset_identity_layout = QVBoxLayout(self.headset_identity)
        headset_identity_layout.setContentsMargins(0, 7, 0, 7)
        headset_identity_layout.setSpacing(0)
        self.headset_name = QLabel("Headset")
        self.headset_name.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.headset_name.setStyleSheet("color: white;")
        self.headset_name.setMaximumWidth(190)
        self.headset_status = QLabel("Connected")
        self.headset_status.setFont(QFont("Segoe UI", 9))
        self.headset_status.setStyleSheet("color: #9da7b3;")
        headset_identity_layout.addWidget(self.headset_name)
        headset_identity_layout.addWidget(self.headset_status)
        self.connection_ring = ConnectionRing()
        self.earbuds_indicator.hide()
        self.headset_identity.hide()
        self.connection_ring.hide()

        self.expand_btn = QPushButton("⌄")
        self.expand_btn.setFixedSize(28, 28)
        self.expand_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none;
                          color: #b9c0c8; font-size: 16px; }
            QPushButton:hover { color: white; }
        """)
        self.expand_btn.clicked.connect(self.toggle_island)

        self.previous_btn = self._media_button("|◀")
        self.play_pause_btn = self._media_button("▶", primary=True)
        self.next_btn = self._media_button("▶|")
        self.media_hide_btn = self._media_button("−")
        self.previous_btn.clicked.connect(lambda: self.media_worker.control("previous"))
        self.play_pause_btn.clicked.connect(lambda: self.media_worker.control("play_pause"))
        self.next_btn.clicked.connect(lambda: self.media_worker.control("next"))
        self.media_hide_btn.clicked.connect(self.hide_media_island)

        self.screen_assist_btn = QPushButton("✦")
        self.screen_assist_btn.setToolTip("Answer the question visible in the active window")
        self.screen_assist_btn.setFixedSize(28, 28)
        self.screen_assist_btn.setFont(QFont("Segoe UI Symbol", 13, QFont.Weight.DemiBold))
        self.screen_assist_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #8ed8ff; }
            QPushButton:hover { color: white; background: rgba(90, 180, 255, 35); border-radius: 14px; }
            QPushButton:pressed { color: #49aef0; }
            QPushButton:disabled { color: #59616b; }
        """)
        self.screen_assist_btn.clicked.connect(self.start_screen_assist)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #A0A0A0;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff4444;
            }
        """)
        self.close_btn.clicked.connect(QApplication.quit)
        
        title_layout.addWidget(self.status_dot)
        title_layout.addWidget(self.album_art)
        # The metadata block owns the remaining width. A separate stretch here
        # collapses this layout to zero because its labels use Ignored sizing.
        title_layout.addWidget(self.identity_widget, 1)
        title_layout.addWidget(self.charging_label)
        title_layout.addWidget(self.low_power_label)
        title_layout.addWidget(self.notification_identity)
        title_layout.addWidget(self.earbuds_indicator)
        title_layout.addWidget(self.headset_identity)
        title_layout.addStretch()
        title_layout.addWidget(self.notification_icon)
        title_layout.addWidget(self.charging_percent)
        title_layout.addWidget(self.battery_indicator)
        title_layout.addWidget(self.low_power_percent)
        title_layout.addWidget(self.low_power_battery)
        title_layout.addWidget(self.connection_ring)
        title_layout.addWidget(self.previous_btn)
        title_layout.addWidget(self.play_pause_btn)
        title_layout.addWidget(self.next_btn)
        title_layout.addWidget(self.media_hide_btn)
        title_layout.addWidget(self.screen_assist_btn)
        title_layout.addWidget(self.close_btn)
        self._set_media_controls_visible(False)
        
        # Event filters for dragging
        self.title_bar.mousePressEvent = self.title_mousePressEvent
        self.title_bar.mouseReleaseEvent = self.title_mouseReleaseEvent
        
        # --- Chat History Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 30);
                border-radius: 4px;
            }
        """)
        
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setContentsMargins(15, 15, 15, 15)
        self.chat_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.chat_container)
        self.scroll_opacity = QGraphicsOpacityEffect(self.scroll_area)
        self.scroll_opacity.setOpacity(1.0)
        self.scroll_area.setGraphicsEffect(self.scroll_opacity)
        
        # --- Input Area ---
        self.input_frame = QFrame()
        self.input_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 40, 200);
                border-radius: 10px;
                margin: 10px;
            }
        """)
        self.input_opacity = QGraphicsOpacityEffect(self.input_frame)
        self.input_opacity.setOpacity(1.0)
        self.input_frame.setGraphicsEffect(self.input_opacity)
        input_layout = QHBoxLayout(self.input_frame)
        input_layout.setContentsMargins(10, 5, 10, 5)
        
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedSize(30, 30)
        self.mic_btn.setCheckable(True)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
                color: #E0E0E0;
            }
            QPushButton:checked {
                color: #ff4444;
            }
        """)
        self.mic_btn.clicked.connect(self.toggle_mic)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                font-size: 14px;
                padding: 5px;
                color: #FFFFFF;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        
        self.send_btn = QPushButton("↑")
        self.send_btn.setFixedSize(30, 30)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border-radius: 15px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
        """)
        self.send_btn.clicked.connect(self.send_message)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            "QPushButton { color: white; background: #9b3434; border-radius: 5px; padding: 5px 9px; }"
            "QPushButton:disabled { color: #888; background: #383838; }")
        self.stop_btn.clicked.connect(lambda: self.worker.cancel())
        
        input_layout.addWidget(self.mic_btn)
        input_layout.addWidget(self.stop_btn)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        
        # Assemble
        container_layout.addWidget(self.title_bar)
        container_layout.addWidget(self.scroll_area)
        container_layout.addWidget(self.input_frame)
        
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
        
        self.confirmation_panel = QFrame()
        approval_layout = QVBoxLayout(self.confirmation_panel)
        self.confirmation_label = QLabel()
        self.confirmation_label.setTextFormat(Qt.TextFormat.PlainText)
        self.confirmation_label.setWordWrap(True)
        self.confirmation_label.setStyleSheet("color: white;")
        approval_layout.addWidget(self.confirmation_label)
        approve = QPushButton("Allow action")
        deny = QPushButton("Cancel task")
        approve.clicked.connect(lambda: self.resolve_confirmation(True))
        deny.clicked.connect(lambda: self.resolve_confirmation(False))
        approval_layout.addWidget(approve)
        approval_layout.addWidget(deny)
        container_layout.addWidget(self.confirmation_panel)
        self.confirmation_panel.hide()
        self.add_message("Jarvis", "Describe a desktop or browser task. I’ll show progress here. Use Stop to cancel. Enable the microphone for voice input.")

    def _target_geometry(self, size):
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = area.x() + (area.width() - size.width()) // 2
        y = area.y() if size == self.HIDDEN_SIZE else area.y() + self.TOP_MARGIN
        return QRect(x, y, size.width(), size.height())

    def _apply_default_container_style(self):
        self.container.setStyleSheet("""
            #Container {
                background-color: rgba(12, 14, 18, 244);
                border-radius: 28px;
                border: 1px solid rgba(255, 255, 255, 48);
            }
        """)

    def _apply_notification_container_style(self):
        self.container.setStyleSheet("""
            #Container {
                background-color: rgba(12, 14, 18, 244);
                border-radius: 28px;
                border: 1px solid rgba(255, 255, 255, 48);
            }
        """)

    def _media_button(self, text, primary=False):
        button = QPushButton(text)
        button.setFixedSize(32 if primary else 28, 32)
        button.setFont(QFont("Segoe UI Symbol", 15 if primary else 12,
                             QFont.Weight.DemiBold))
        button.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: white; }
            QPushButton:hover { color: #70cfff; }
            QPushButton:pressed { color: #2d9cff; }
        """)
        return button

    def _set_media_controls_visible(self, visible):
        self.album_art.setVisible(visible)
        self.previous_btn.setVisible(visible)
        self.play_pause_btn.setVisible(visible)
        self.next_btn.setVisible(visible)
        self.media_hide_btn.setVisible(visible)

    def _compact_size(self):
        if self._notification_active:
            return self.NOTIFICATION_SIZE
        if self._headset_active:
            return self.HEADSET_SIZE
        if self._low_power_active:
            return self.LOW_POWER_SIZE
        if self._charging_active:
            return self.CHARGING_SIZE
        if not self._media:
            return self.COLLAPSED_SIZE
        title = self._media.get("title", "Now playing")
        artist = self._media.get("artist") or self._media.get("app", "Media")
        text_width = max(
            self.name_label.fontMetrics().horizontalAdvance(title),
            self.status_label.fontMetrics().horizontalAdvance(artist),
        )
        text_width = max(80, min(self.name_label.maximumWidth(), text_width + 8))
        width = max(self.MEDIA_MIN_WIDTH,
                    min(self.MEDIA_SIZE.width(), self.MEDIA_BASE_WIDTH + text_width))
        return QSize(width, self.MEDIA_SIZE.height())

    def _expanded_size(self):
        """Preserve the content-aware media width while opening the panel."""
        compact_width = self._compact_size().width()
        return QSize(max(self.EXPANDED_SIZE.width(), compact_width),
                     self.EXPANDED_SIZE.height())

    def _place_top_center(self):
        size = self._expanded_size() if self.is_expanded else self._compact_size()
        self.setGeometry(self._target_geometry(size))

    def _animate_to(self, size, duration=None, curve=QEasingCurve.Type.OutCubic):
        duration = duration or self.COMPACT_TRANSITION_MS
        target = self._target_geometry(size)
        if (self._animation and self._animation_target == target
                and self._animation.state() == QAbstractAnimation.State.Running):
            return self._transition_generation
        if self.geometry() == target:
            self._animation_target = target
            return self._transition_generation
        if self._animation:
            self._animation.stop()
        self._transition_generation += 1
        self._animation = QPropertyAnimation(self, b"geometry", self)
        self._animation_target = target
        self._animation.setDuration(duration)
        self._animation.setEasingCurve(curve)
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(target)
        self._animation.start()
        return self._transition_generation

    def _present_compact(self, size, duration=None):
        """Reveal at a deterministic geometry, then perform one fluid resize."""
        self._visibility_generation += 1
        self._is_hiding = False
        was_hidden = self.isHidden() or self._auto_hidden or self.windowOpacity() < 0.1
        if self._animation:
            self._animation.stop()
        self._animation_target = None
        self.setWindowOpacity(1.0)
        if was_hidden:
            start = QSize(max(120, int(size.width() * 0.68)),
                          max(34, size.height() - 8))
            # Set the first painted geometry before show(), avoiding a frame at
            # the previous/default size followed by a second corrective resize.
            self.setGeometry(self._target_geometry(start))
        self.show()
        self.raise_()
        self._animate_to(size, duration or self.COMPACT_TRANSITION_MS)

    def _fade_expanded_content(self):
        if not self.is_expanded:
            return
        if self._content_animation:
            self._content_animation.stop()
        scroll_fade = QPropertyAnimation(self.scroll_opacity, b"opacity")
        scroll_fade.setDuration(190)
        scroll_fade.setStartValue(0.0)
        scroll_fade.setEndValue(1.0)
        input_fade = QPropertyAnimation(self.input_opacity, b"opacity")
        input_fade.setDuration(190)
        input_fade.setStartValue(0.0)
        input_fade.setEndValue(1.0)
        group = QParallelAnimationGroup(self)
        group.addAnimation(scroll_fade)
        group.addAnimation(input_fade)
        self._content_animation = group
        group.start()

    def _show_expanded_content(self):
        if not self.is_expanded:
            return
        self.scroll_area.show()
        self.input_frame.show()
        self._fade_expanded_content()

    def expand_island(self, focus_input=False):
        self._collapse_timer.stop()
        self._auto_hidden = False
        self._media_manually_hidden = False
        self.setWindowOpacity(1.0)
        self.is_expanded = True
        self.scroll_opacity.setOpacity(0.0)
        self.input_opacity.setOpacity(0.0)
        self.scroll_area.hide()
        self.input_frame.hide()
        if not self.confirmation_panel.isHidden() or self.confirmation_label.text():
            self.confirmation_panel.setVisible(not self.confirmation_panel.isHidden())
        self.expand_btn.setText("⌃")
        # Expand directly from the already content-sized media pill. Using a
        # fixed width here caused a second horizontal resize and visible flash.
        generation = self._animate_to(
            self._expanded_size(), self.PANEL_TRANSITION_MS)
        # Let the black island surface establish first; adding the complex
        # scroll/input layout at the same instant as the native resize causes
        # a one-frame flash on DWM layered windows.
        QTimer.singleShot(
            150,
            lambda: self._show_expanded_content()
            if (self.is_expanded and generation == self._transition_generation)
            else None,
        )
        if focus_input:
            QTimer.singleShot(
                235,
                lambda: self.input_field.setFocus()
                if (self.is_expanded and generation == self._transition_generation)
                else None,
            )

    def collapse_island(self):
        if not hasattr(self, "worker") or self.worker.busy.is_set() or not self.confirmation_panel.isHidden():
            return
        if self.input_field.hasFocus() and self.input_field.text():
            return
        if self._assistant_state == "Idle" and not self._media:
            self.hide_idle_island()
            return
        self.is_expanded = False
        self.scroll_area.hide()
        self.input_frame.hide()
        self.expand_btn.setText("⌄")
        self._animate_to(self._compact_size(), self.COMPACT_TRANSITION_MS)

    def hide_idle_island(self):
        if (self.worker.busy.is_set()
                or (self._media and self._media.get("playing") and not self._media_manually_hidden)
                or not self.confirmation_panel.isHidden()):
            return
        self.is_expanded = False
        self._auto_hidden = True
        self._hover_leave_at = None
        self.scroll_area.hide()
        self.input_frame.hide()
        self.expand_btn.setText("⌄")
        self.setWindowOpacity(0.03)
        self._animate_to(self.HIDDEN_SIZE, self.COMPACT_TRANSITION_MS)

    def hide_media_island(self):
        """Hide the UI without stopping either background worker."""
        self._media_manually_hidden = True
        self._is_hiding = True
        # Require the pointer to leave and re-enter the hot zone. Otherwise a
        # minimize click near the top center can instantly reopen the island.
        self._hot_zone_armed = False
        self.is_expanded = False
        self._auto_hidden = True
        self._hover_leave_at = None
        self.scroll_area.hide()
        self.input_frame.hide()
        if self._animation:
            self._animation.stop()
        self._animation_target = None
        self._visibility_generation += 1
        generation = self._visibility_generation
        self.setWindowOpacity(1.0)
        # Morph toward the top edge, then hide once. Animating native window
        # opacity in parallel with geometry makes Windows recompose the layered
        # surface twice per frame and causes flashes on some GPUs.
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        minimize_target = QRect(
            area.x() + (area.width() - self.MINIMIZE_SIZE.width()) // 2,
            area.y() - self.MINIMIZE_SIZE.height(),
            self.MINIMIZE_SIZE.width(),
            self.MINIMIZE_SIZE.height(),
        )
        geometry = QPropertyAnimation(self, b"geometry", self)
        geometry.setDuration(self.COMPACT_TRANSITION_MS)
        geometry.setEasingCurve(QEasingCurve.Type.OutCubic)
        geometry.setStartValue(self.geometry())
        geometry.setEndValue(minimize_target)
        geometry.finished.connect(self._complete_media_hide)
        self._animation = geometry
        self._animation_target = minimize_target
        geometry.start()
        # A guarded fallback covers animation-driver interruption (display
        # sleep, shell restart, or Qt event-loop replacement) without allowing
        # an old timer to hide a newer, already-visible activity.
        QTimer.singleShot(
            self.COMPACT_TRANSITION_MS + 80,
            lambda: self._complete_media_hide()
            if (generation == self._visibility_generation and self._auto_hidden)
            else None,
        )

    def _complete_media_hide(self):
        self._is_hiding = False
        if self._auto_hidden:
            self.hide()

    def reveal_idle_island(self):
        if not self._auto_hidden:
            return
        self._auto_hidden = False
        self._media_manually_hidden = False
        self._hover_leave_at = None
        self._present_compact(self._compact_size())

    def _check_hot_zone(self):
        if (self._is_hiding or self.is_expanded or self.worker.busy.is_set()
                or (self._media and self._media.get("playing")
                    and not self._media_manually_hidden)):
            return
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        cursor = QCursor.pos()
        center = area.x() + area.width() // 2
        in_hot_zone = (
            center - self.HOT_ZONE_WIDTH // 2 <= cursor.x() <= center + self.HOT_ZONE_WIDTH // 2
            and area.y() <= cursor.y() <= area.y() + self.HOT_ZONE_HEIGHT
        )
        if not in_hot_zone:
            self._hot_zone_armed = True
        if self._auto_hidden and in_hot_zone and self._hot_zone_armed:
            self._hot_zone_armed = False
            self.reveal_idle_island()
        elif not self._auto_hidden:
            if in_hot_zone or self.geometry().contains(cursor):
                self._hover_leave_at = None
            elif self._assistant_state == "Idle":
                if self._hover_leave_at is None:
                    self._hover_leave_at = time.monotonic()
                elif time.monotonic() - self._hover_leave_at >= 1.0:
                    if self._media and not self._media.get("playing"):
                        self.hide_media_island()
                    else:
                        self.hide_idle_island()

    def toggle_island(self):
        if self.is_expanded:
            self.collapse_island()
        else:
            self.expand_island(True)

    def activate_island(self):
        if self.isMinimized():
            self.showNormal()
        self._collapse_timer.stop()
        self._auto_hidden = False
        self._media_manually_hidden = False
        self.is_expanded = False
        self.scroll_area.hide()
        self.input_frame.hide()
        self._present_compact(self._compact_size())
        self.activateWindow()

    def activate_media_island(self):
        """Show the compact live activity when playback becomes active."""
        self._collapse_timer.stop()
        self._auto_hidden = False
        self._media_manually_hidden = False
        self.is_expanded = False
        self.scroll_area.hide()
        self.input_frame.hide()
        self._present_compact(self._compact_size())

    def _pulse_media_indicator(self):
        if not self._media or not self._media.get("playing"):
            return
        self._pulse_phase = not self._pulse_phase
        color = "#a9ecff" if self._pulse_phase else "#55d6ff"
        size = 14 if self._pulse_phase else 12
        self.status_dot.setStyleSheet(f"color: {color}; font-size: {size}px;")

    def _check_battery_state(self):
        try:
            import psutil
            battery = psutil.sensors_battery()
        except Exception:
            battery = None
        if battery is None:
            return
        plugged = bool(battery.power_plugged)
        if self._last_power_plugged is False and plugged:
            self.show_charging_activity(battery.percent)
        elif self._charging_active and plugged:
            self._update_charging_percent(battery.percent)
        self._last_power_plugged = plugged
        saver = self._energy_saver_enabled()
        if self._last_energy_saver is False and saver:
            self.show_low_power_activity(battery.percent)
        elif self._low_power_active and saver:
            self._update_low_power_percent(battery.percent)
        self._last_energy_saver = saver

    @staticmethod
    def _energy_saver_enabled():
        """Return the Windows Energy Saver flag from GetSystemPowerStatus."""
        try:
            import ctypes

            class SystemPowerStatus(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]

            status = SystemPowerStatus()
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                return False
            return bool(status.SystemStatusFlag)
        except Exception:
            return False

    @staticmethod
    def _is_headset_name(name):
        lowered = (name or "").lower()
        return any(word in lowered for word in (
            "headphone", "headset", "earphone", "earbud", "buds", "airpods",
        ))

    def _check_audio_device(self):
        try:
            from pycaw.pycaw import AudioUtilities
            device = AudioUtilities.GetSpeakers()
            device_id = device.id if device else None
            name = device.FriendlyName if device else ""
        except Exception:
            return
        if (self._last_audio_device_id is not None
                and device_id != self._last_audio_device_id
                and self._is_headset_name(name)):
            self.show_headset_activity(name)
        self._last_audio_device_id = device_id

    def _track_foreground_window(self):
        try:
            import ctypes
            hwnd = int(ctypes.windll.user32.GetForegroundWindow())
            own_hwnd = int(self.winId())
            if hwnd and hwnd != own_hwnd:
                self._last_external_hwnd = hwnd
        except Exception:
            pass

    @staticmethod
    def _proctoring_active():
        blocked = {
            "safeexambrowser.exe", "safexambrowserclient.exe",
            "safeexambrowser.client.exe", "seb.exe", "sebwindowsclient.exe",
            "lockdownbrowser.exe", "respondus.exe",
            "proctorio.exe", "proctortrack.exe", "examsoft.exe", "examplify.exe",
        }
        try:
            import psutil
            return any((process.info.get("name") or "").lower() in blocked
                       for process in psutil.process_iter(["name"]))
        except Exception:
            return False

    def start_screen_assist(self):
        if self._proctoring_active():
            self.add_message(
                "Jarvis",
                "Screen Assist is disabled while exam or proctoring software is running.")
            self.expand_island()
            return
        if self.screen_assist_worker and self.screen_assist_worker.isRunning():
            return
        self._track_foreground_window()
        if not self._last_external_hwnd:
            self.add_message("Jarvis", "Open the question window, then press Screen Assist again.")
            self.expand_island()
            return
        self.screen_assist_btn.setEnabled(False)
        self.update_state("Processing", "Reading the active window...")
        worker = ScreenAssistWorker(self._last_external_hwnd)
        worker.text_ready.connect(self._screen_context_ready)
        worker.extraction_failed.connect(self._screen_assist_failed)
        worker.finished.connect(lambda: self.screen_assist_btn.setEnabled(True))
        self.screen_assist_worker = worker
        worker.start()

    def _screen_context_ready(self, content):
        # Capture is intentionally separate from model execution. The user can
        # now ask a specific question, which is submitted together with this
        # context only when they press Enter/send.
        self._screen_context = content
        self.update_state("Idle", "Screen captured — type your question")
        self.input_field.setPlaceholderText("Ask about the captured screen...")
        self.add_message(
            "Jarvis",
            "Screen content captured. Type what you want to ask, then press Enter.")
        self.expand_island(focus_input=True)

    def _screen_assist_failed(self, message):
        self._screen_context = None
        self.input_field.setPlaceholderText("Type a message...")
        self.add_message("Jarvis", message)
        self.update_state("Idle", "Ready")
        self.expand_island()

    def _start_notification_listener(self):
        try:
            asyncio.run(self._initialize_notification_listener())
        except Exception:
            self._notification_listener = None

    async def _initialize_notification_listener(self):
        from winrt.windows.ui.notifications import NotificationKinds
        from winrt.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus,
        )
        listener = UserNotificationListener.current
        access = listener.get_access_status()
        if access == UserNotificationListenerAccessStatus.UNSPECIFIED:
            access = await listener.request_access_async()
        if access != UserNotificationListenerAccessStatus.ALLOWED:
            return
        current = await listener.get_notifications_async(NotificationKinds.TOAST)
        self._known_notification_ids = {item.id for item in current}
        self._notification_listener = listener
        self._notification_timer.start()

    def _poll_notifications(self):
        if self._notification_listener is None:
            return
        try:
            asyncio.run(self._read_new_notifications())
        except Exception:
            return

    async def _read_new_notifications(self):
        from winrt.windows.ui.notifications import NotificationKinds
        items = await self._notification_listener.get_notifications_async(
            NotificationKinds.TOAST)
        current_ids = {item.id for item in items}
        new_items = [item for item in items
                     if item.id not in self._known_notification_ids]
        self._known_notification_ids = current_ids
        if not new_items:
            return
        item = new_items[-1]
        app_name, title, body = self._notification_text(item)
        if app_name.lower() not in ("jarvis", "dexget"):
            self.show_notification_activity(app_name, title, body)

    @staticmethod
    def _notification_text(item):
        try:
            app_name = item.app_info.display_info.display_name
        except Exception:
            app_name = "Windows"
        texts = []
        try:
            from winrt.windows.ui.notifications import KnownNotificationBindings
            binding = item.notification.visual.get_binding(
                KnownNotificationBindings.toast_generic)
            if binding:
                texts = [element.text.strip() for element in binding.get_text_elements()
                         if element.text and element.text.strip()]
        except Exception:
            pass
        title = texts[0] if texts else "New notification"
        body = " · ".join(texts[1:]) if len(texts) > 1 else app_name
        return app_name or "Windows", title, body

    def _update_charging_percent(self, percent):
        value = max(0, min(100, int(round(percent))))
        self.charging_percent.setText(f"{value}%")
        self.battery_indicator.set_percent(value)

    def show_charging_activity(self, percent):
        if self._notification_active:
            self.finish_notification_activity(restore=False)
        if self._low_power_active:
            self.finish_low_power_activity(restore=False)
        if self._headset_active:
            self.finish_headset_activity(restore=False)
        self._pre_charging_expanded = self.is_expanded
        self._charging_active = True
        self._collapse_timer.stop()
        self._auto_hidden = False
        self._media_manually_hidden = False
        self.is_expanded = False
        self.scroll_area.hide()
        self.input_frame.hide()
        self.status_dot.hide()
        self.album_art.hide()
        self.identity_widget.hide()
        self._set_media_controls_visible(False)
        self.close_btn.hide()
        self.screen_assist_btn.hide()
        self.charging_label.show()
        self.charging_percent.show()
        self.battery_indicator.show()
        self._update_charging_percent(percent)
        self._present_compact(self.CHARGING_SIZE)
        self._charging_hide_timer.start(4200)

    def finish_charging_activity(self, restore=True):
        if not self._charging_active:
            return
        self._charging_active = False
        self.charging_label.hide()
        self.charging_percent.hide()
        self.battery_indicator.hide()
        self.status_dot.show()
        self.identity_widget.show()
        self.close_btn.show()
        self.screen_assist_btn.show()
        if not restore:
            return
        if self._media:
            self._set_media_controls_visible(True)
        if self._pre_charging_expanded:
            self.expand_island()
        elif self._media and self._media.get("playing"):
            self.activate_media_island()
        else:
            self.hide_media_island()

    def show_headset_activity(self, name):
        if self._notification_active:
            self.finish_notification_activity(restore=False)
        if self._low_power_active:
            self.finish_low_power_activity(restore=False)
        if self._charging_active:
            self._charging_hide_timer.stop()
            self.finish_charging_activity(restore=False)
        self._pre_charging_expanded = self.is_expanded
        self._headset_active = True
        self._collapse_timer.stop()
        self._auto_hidden = False
        self._media_manually_hidden = False
        self.is_expanded = False
        self.scroll_area.hide()
        self.input_frame.hide()
        self.status_dot.hide()
        self.album_art.hide()
        self.identity_widget.hide()
        self._set_media_controls_visible(False)
        self.close_btn.hide()
        self.screen_assist_btn.hide()
        self.earbuds_indicator.show()
        self.headset_identity.show()
        self.connection_ring.show()
        display_name = (name or "Headset").strip()
        for prefix in ("Headphones (", "Headset (", "Speakers ("):
            if display_name.startswith(prefix) and display_name.endswith(")"):
                display_name = display_name[len(prefix):-1]
                break
        self.headset_name.setText(display_name[:34] or "Headset")
        self._present_compact(self.HEADSET_SIZE)
        self._headset_hide_timer.start(4200)

    def finish_headset_activity(self, restore=True):
        if not self._headset_active:
            return
        self._headset_active = False
        self.earbuds_indicator.hide()
        self.headset_identity.hide()
        self.connection_ring.hide()
        self.status_dot.show()
        self.identity_widget.show()
        self.close_btn.show()
        self.screen_assist_btn.show()
        if self._media:
            self._set_media_controls_visible(True)
        if not restore:
            return
        if self._pre_charging_expanded:
            self.expand_island()
        elif self._media and self._media.get("playing"):
            self.activate_media_island()
        else:
            self.hide_media_island()

    def _update_low_power_percent(self, percent):
        value = max(0, min(100, int(round(percent))))
        self.low_power_percent.setText(f"{value}%")
        self.low_power_battery.set_percent(value)

    def show_low_power_activity(self, percent):
        if self._notification_active:
            self.finish_notification_activity(restore=False)
        if self._charging_active:
            self._charging_hide_timer.stop()
            self.finish_charging_activity(restore=False)
        if self._headset_active:
            self._headset_hide_timer.stop()
            self.finish_headset_activity(restore=False)
        self._pre_charging_expanded = self.is_expanded
        self._low_power_active = True
        self._collapse_timer.stop()
        self._auto_hidden = False
        self.is_expanded = False
        self.scroll_area.hide()
        self.input_frame.hide()
        self.status_dot.hide()
        self.album_art.hide()
        self.identity_widget.hide()
        self._set_media_controls_visible(False)
        self.close_btn.hide()
        self.screen_assist_btn.hide()
        self.low_power_label.show()
        self.low_power_percent.show()
        self.low_power_battery.show()
        self._update_low_power_percent(percent)
        self._present_compact(self.LOW_POWER_SIZE)
        self._low_power_hide_timer.start(4200)

    def finish_low_power_activity(self, restore=True):
        if not self._low_power_active:
            return
        self._low_power_active = False
        self.low_power_label.hide()
        self.low_power_percent.hide()
        self.low_power_battery.hide()
        self.status_dot.show()
        self.identity_widget.show()
        self.close_btn.show()
        self.screen_assist_btn.show()
        if self._media:
            self._set_media_controls_visible(True)
        if not restore:
            return
        if self._pre_charging_expanded:
            self.expand_island()
        elif self._media and self._media.get("playing"):
            self.activate_media_island()
        else:
            self.hide_media_island()

    def show_notification_activity(self, app_name, title, body):
        if self._charging_active:
            self._charging_hide_timer.stop()
            self.finish_charging_activity(restore=False)
        if self._headset_active:
            self._headset_hide_timer.stop()
            self.finish_headset_activity(restore=False)
        if self._low_power_active:
            self._low_power_hide_timer.stop()
            self.finish_low_power_activity(restore=False)
        self._pre_charging_expanded = self.is_expanded
        self._notification_active = True
        self._collapse_timer.stop()
        self._auto_hidden = False
        self.is_expanded = False
        self.scroll_area.hide()
        self.input_frame.hide()
        self.status_dot.hide()
        self.album_art.hide()
        self.identity_widget.hide()
        self._set_media_controls_visible(False)
        self.close_btn.hide()
        self.screen_assist_btn.hide()
        app_name = (app_name or "Windows").strip()
        self.notification_icon.setText("✉")
        self.notification_title.setText((title or "New notification")[:52])
        message = body if body and body != app_name else app_name
        self.notification_body.setText(f'“{message[:62]}”  · now')
        self._apply_notification_container_style()
        self.title_bar.setFixedHeight(self.NOTIFICATION_SIZE.height())
        self.notification_icon.show()
        self.notification_identity.show()
        self._present_compact(self.NOTIFICATION_SIZE)
        self._notification_hide_timer.start(5200)

    def finish_notification_activity(self, restore=True):
        if not self._notification_active:
            return
        self._notification_active = False
        self.notification_icon.hide()
        self.notification_identity.hide()
        self._apply_default_container_style()
        self.title_bar.setFixedHeight(48)
        self.status_dot.show()
        self.identity_widget.show()
        self.close_btn.show()
        self.screen_assist_btn.show()
        if self._media:
            self._set_media_controls_visible(True)
        if not restore:
            return
        if self._pre_charging_expanded:
            self.expand_island()
        elif self._media and self._media.get("playing"):
            self.activate_media_island()
        else:
            self.hide_media_island()

    def enterEvent(self, event):
        self.reveal_idle_island()
        self._hover_leave_at = None
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_expanded and not self._media:
            self._hover_leave_at = time.monotonic()
        super().leaveEvent(event)

    def title_mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._title_press_pos = event.globalPosition().toPoint()

    def title_mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, "_title_press_pos"):
            if (event.globalPosition().toPoint() - self._title_press_pos).manhattanLength() < 6:
                self.toggle_island()

    def toggle_mic(self):
        self.expand_island()
        if self.mic_btn.isChecked():
            self.status_label.setText("Mic ON - Listening")
            self.worker.enable_listening(True)
        else:
            self.status_label.setText("Mic OFF")
            self.worker.enable_listening(False)

    def update_state(self, state, subtitle):
        self._assistant_state = state
        self._assistant_subtitle = subtitle
        if not self._media:
            self.name_label.setText("DEXGET")
            self.status_label.setText(subtitle[:70])
            self.status_label.setToolTip(subtitle)
        colors = {
            "Processing": "#4aa8ff", "Stopping": "#ffb347", "Idle": "#39e58c"
        }
        self.status_dot.setStyleSheet(f"color: {colors.get(state, '#39e58c')}; font-size: 15px;")
        if state == "Processing":
            self.expand_island()
        if state in ("Idle", "Stopping"):
            self.confirmation_panel.hide()
        if state == "Idle":
            self._collapse_timer.start(4500)

    def update_media(self, media):
        previous_key = self._last_media_key
        was_playing = bool(self._media.get("playing"))
        self._media = media or {}
        playing_now = False
        if self._media:
            if not self._media_manually_hidden:
                self._auto_hidden = False
                self.setWindowOpacity(1.0)
            title = self._media.get("title", "Now playing")
            artist = self._media.get("artist") or self._media.get("app", "Media")
            self._last_media_key = (title, artist)
            self.name_label.setText(title[:34])
            self.name_label.setToolTip(title)
            self.status_label.setText(artist[:42])
            self.status_label.setToolTip(artist)
            playing = bool(self._media.get("playing"))
            playing_now = playing
            if playing and not self._media_pulse_timer.isActive():
                self._media_pulse_timer.start()
            elif not playing:
                self._media_pulse_timer.stop()
            self.play_pause_btn.setText("❚❚" if playing else "▶")
            artwork = self._media.get("artwork") or b""
            pixmap = QPixmap()
            if artwork and pixmap.loadFromData(artwork):
                self.album_art.setPixmap(pixmap.scaled(
                    self.album_art.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation))
                self.album_art.setText("")
            else:
                self.album_art.setPixmap(QPixmap())
                self.album_art.setText("♪")
                self.album_art.setStyleSheet(
                    "background: #202329; border-radius: 5px; color: #8f99a6; font-size: 18px;")
            self.status_dot.setStyleSheet(
                f"color: {'#55d6ff' if playing else '#ffb347'}; font-size: 15px;"
            )
            self._set_media_controls_visible(True)
        else:
            self._media_pulse_timer.stop()
            self._last_media_key = None
            self.name_label.setText("DEXGET")
            self.status_label.setText(self._assistant_subtitle[:70])
            self.status_label.setToolTip(self._assistant_subtitle)
            self._set_media_controls_visible(False)
            if self._assistant_state == "Idle":
                self._collapse_timer.start(1800)
        if playing_now and not was_playing:
            self.activate_media_island()
        elif (not playing_now and
              (was_playing or (self._media and not self._auto_hidden
                               and not self._media_manually_hidden))):
            self.hide_media_island()
        elif not self.is_expanded and not self._media_manually_hidden:
            # Track changes resize once to the final content-aware width.
            # The old grow-then-settle bump caused a visible double resize.
            self._animate_to(self._compact_size())

    def set_busy(self, busy):
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        if busy:
            self.expand_island()

    def show_confirmation(self, prompt):
        if self.agent.registry.cancel_event.is_set():
            self.worker.answer_confirmation(False)
            return
        self.confirmation_label.setText(prompt)
        self.confirmation_panel.show()
        self.expand_island()
        self.status_label.setText("Approval needed")

    def resolve_confirmation(self, approved):
        self.confirmation_panel.hide()
        self.worker.answer_confirmation(approved)

    def closeEvent(self, event):
        if self.worker.isRunning():
            self._closing = True
            if hasattr(self, "media_worker"):
                self.media_worker.shutdown()
            if self.screen_assist_worker and self.screen_assist_worker.isRunning():
                self.screen_assist_worker.requestInterruption()
                self.screen_assist_worker.wait(1500)
            self.worker.shutdown()
            self.hide()
            event.ignore()
        else:
            event.accept()

    def add_message(self, role, text):
        if hasattr(self, "worker") and (self.worker.busy.is_set() or role == "User"):
            self.expand_island()
        msg_widget = MessageWidget(role, text)
        self.chat_layout.addWidget(msg_widget)
        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def send_message(self):
        text = self.input_field.text().strip()
        if text:
            submitted_text = text
            if self._screen_context:
                submitted_text = (
                    "Answer the user's question using the captured active-window content below. "
                    "Give a direct, clear answer. If programming is requested, provide complete "
                    "runnable code with a short explanation. Do not operate the computer or change "
                    "files; only answer the question.\n\n"
                    f"USER QUESTION:\n{text}\n\nCAPTURED WINDOW CONTENT:\n{self._screen_context}"
                )
            if self.worker.submit_text(submitted_text, display_text=text):
                self.input_field.clear()
                self._screen_context = None
                self.input_field.setPlaceholderText("Type a message...")

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._place_top_center)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # WA_TranslucentBackground plus the rounded container already clips the
        # visible pixels. Rebuilding a native HRGN mask for every geometry
        # animation frame causes a black flash/flicker on Windows DWM.
        if not self.mask().isEmpty():
            self.clearMask()

    def _corner_radius(self):
        if self.height() <= 6:
            return 2.0
        elif self.is_expanded:
            return 24.0
        return min(self.height() / 2.0, 26.0)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = JarvisWidget()
    ex.show()
    sys.exit(app.exec())
