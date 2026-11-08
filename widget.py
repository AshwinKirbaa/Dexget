import sys
import threading
import queue
import asyncio
import time
import os
import glob
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QScrollArea, 
                        QFrame, QSizePolicy, QGraphicsDropShadowEffect, QInputDialog,
                             QGraphicsOpacityEffect, QSlider, QGridLayout,
                             QStackedWidget, QSystemTrayIcon, QMenu)
from PyQt6.QtCore import (Qt, QPoint, QPointF, QThread, pyqtSignal, QTimer, QSize,
                          QRect, QPropertyAnimation, QEasingCurve,
                          QParallelAnimationGroup, QVariantAnimation,
                          QRectF, QAbstractAnimation, QSettings, QEvent)
from PyQt6.QtGui import (QColor, QFont, QIcon, QPainter, QBrush, QPen,
                         QPainterPath, QRegion, QCursor, QPixmap, QAction)

import jarvis_integration


class MediaControlButton(QPushButton):
    """Font-independent Apple-style previous/play-pause/next control."""
    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.playing = False
        self.setFixedSize(48, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def set_playing(self, playing):
        self.playing = bool(playing)
        self.update()

    @staticmethod
    def _triangle(painter, points):
        path = QPainterPath()
        path.moveTo(points[0])
        path.lineTo(points[1])
        path.lineTo(points[2])
        path.closeSubpath()
        painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#8ddcff") if self.isDown() else QColor("#ffffff")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "play_pause":
            if self.playing:
                painter.drawRoundedRect(QRectF(cx - 8, cy - 11, 6, 22), 1.5, 1.5)
                painter.drawRoundedRect(QRectF(cx + 2, cy - 11, 6, 22), 1.5, 1.5)
            else:
                self._triangle(painter, (
                    QPointF(cx - 6, cy - 11), QPointF(cx - 6, cy + 11),
                    QPointF(cx + 11, cy)))
        elif self.kind == "previous":
            self._triangle(painter, (
                QPointF(cx - 1, cy - 9), QPointF(cx - 1, cy + 9),
                QPointF(cx - 14, cy)))
            self._triangle(painter, (
                QPointF(cx + 13, cy - 9), QPointF(cx + 13, cy + 9),
                QPointF(cx, cy)))
        else:
            self._triangle(painter, (
                QPointF(cx + 1, cy - 9), QPointF(cx + 1, cy + 9),
                QPointF(cx + 14, cy)))
            self._triangle(painter, (
                QPointF(cx - 13, cy - 9), QPointF(cx - 13, cy + 9),
                QPointF(cx, cy)))


class MediaWaveformIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.playing = False
        self.setFixedSize(25, 24)

    def set_playing(self, playing):
        self.playing = bool(playing)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white") if self.playing else QColor("#7b838d"),
                            2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        heights = (7, 13, 18, 12, 8)
        for index, height in enumerate(heights):
            x = 3 + index * 4.5
            painter.drawLine(QPointF(x, 12 - height / 2), QPointF(x, 12 + height / 2))


class TimerToggleButton(QPushButton):
    """Font-independent circular pause/resume control for timer activities."""
    def __init__(self):
        super().__init__("Ⅱ")
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            background = QColor("#74420f")
            foreground = QColor("#a8a8a8")
        elif self.isDown():
            background = QColor("#954706")
            foreground = QColor("#ffffff")
        elif self.underMouse():
            background = QColor("#d66b10")
            foreground = QColor("#ffffff")
        else:
            background = QColor("#c65d00")
            foreground = QColor("#ffffff")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawEllipse(QRectF(0.5, 0.5, 39.0, 39.0))
        painter.setBrush(foreground)
        cx, cy = 20.0, 20.0
        if self.text() == "▶":
            path = QPainterPath()
            path.moveTo(cx - 4.5, cy - 8.0)
            path.lineTo(cx - 4.5, cy + 8.0)
            path.lineTo(cx + 8.0, cy)
            path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawRoundedRect(QRectF(cx - 7.0, cy - 8.5, 5.0, 17.0), 1.2, 1.2)
            painter.drawRoundedRect(QRectF(cx + 2.0, cy - 8.5, 5.0, 17.0), 1.2, 1.2)


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


class WifiStatusIndicator(QWidget):
    """Compact network glyph for the idle Dynamic Island."""
    def __init__(self):
        super().__init__()
        self.connected = False
        self.setFixedSize(76, 28)

    def set_connected(self, connected):
        self.connected = bool(connected)
        self.setToolTip("Internet connected" if self.connected else "Internet offline")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#f5f7fa") if self.connected else QColor("#ff6961")
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        # Keep the glyph centered inside a field equal in width to the battery
        # field so the clock remains geometrically centered on the screen.
        cx = self.width() / 2
        for width, y in ((20.0, 6.0), (14.0, 9.5), (8.0, 13.0)):
            path = QPainterPath()
            path.moveTo(cx - width / 2, y)
            path.quadTo(cx, y - width * 0.43, cx + width / 2, y)
            painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(cx, 19.5), 1.8, 1.8)


class CompactBatteryStatus(QWidget):
    """Battery outline, live charge fill and percentage for the idle island."""
    def __init__(self):
        super().__init__()
        self.percent = None
        self.charging = False
        self.setFixedSize(76, 28)

    def set_status(self, percent, charging=False):
        self.percent = None if percent is None else max(0, min(100, int(percent)))
        self.charging = bool(charging)
        detail = "Battery unavailable" if self.percent is None else f"Battery {self.percent}%"
        self.setToolTip(detail + (" (charging)" if self.charging else ""))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = QColor("#f5f7fa")
        body = QRectF(3.0, 8.0, 23.0, 12.0)
        painter.setPen(QPen(outline, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body, 3.0, 3.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(outline)
        painter.drawRoundedRect(QRectF(27.0, 11.0, 2.5, 6.0), 1.1, 1.1)
        if self.percent is not None and self.percent > 0:
            fill_color = QColor("#34c759")
            if self.percent <= 10 and not self.charging:
                fill_color = QColor("#ff453a")
            elif self.percent <= 20 and not self.charging:
                fill_color = QColor("#ffd60a")
            fill_width = max(2.0, 19.0 * self.percent / 100.0)
            painter.setBrush(fill_color)
            painter.drawRoundedRect(QRectF(5.0, 10.0, fill_width, 8.0), 2.0, 2.0)
        painter.setPen(outline)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        text = "--%" if self.percent is None else f"{self.percent}%"
        painter.drawText(QRectF(33.0, 0.0, 42.0, 28.0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         text)


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
        next_metadata_poll = 0.0
        cached_artwork_key = None
        cached_artwork = b""
        while not self.shutdown_event.is_set():
            session = manager.get_current_session()
            # Commands are intentionally serviced independently from the
            # heavier metadata poll.  The former two-second combined loop made
            # play/pause/seek feel unresponsive.
            while session and not self.actions.empty():
                queued = self.actions.get_nowait()
                action, value = queued if isinstance(queued, tuple) else (queued, None)
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
                elif action == "seek" and value is not None:
                    await session.try_change_playback_position_async(
                        int(max(0.0, float(value)) * 10_000_000))
            now = asyncio.get_running_loop().time()
            if now >= next_metadata_poll:
                next_metadata_poll = now + 0.45
                current = {}
                if session:
                    try:
                        props = await session.try_get_media_properties_async()
                        info = session.get_playback_info()
                        timeline = session.get_timeline_properties()
                        start = self._duration_seconds(timeline.start_time)
                        end = self._duration_seconds(timeline.end_time)
                        position = max(0.0, self._duration_seconds(timeline.position) - start)
                        duration = max(0.0, end - start)
                        artwork_key = (
                            props.title, props.artist, props.album_artist,
                            session.source_app_user_model_id,
                        )
                        if artwork_key != cached_artwork_key:
                            cached_artwork = await self._read_thumbnail(props.thumbnail)
                            cached_artwork_key = artwork_key
                        current = {
                            "title": (props.title or "Now playing").strip(),
                            "artist": (props.artist or props.album_artist or "").strip(),
                            "app": session.source_app_user_model_id or "Media",
                            "playing": info.playback_status == PlaybackStatus.PLAYING,
                            "artwork": cached_artwork,
                            "position": position,
                            "duration": duration,
                        }
                    except Exception:
                        current = {}
                if current != previous:
                    previous = current
                    self.media_changed.emit(current)
            await asyncio.sleep(0.05)

    @staticmethod
    def _duration_seconds(value):
        if hasattr(value, "total_seconds"):
            return float(value.total_seconds())
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

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

    def control(self, action, value=None):
        self.actions.put((action, value) if value is not None else action)

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


class DashboardSystemWorker(QThread):
    """Fetch slower Windows control-center values away from the UI thread."""
    info_ready = pyqtSignal(dict)

    def run(self):
        data = {}
        try:
            import psutil
            data["cpu"] = int(psutil.cpu_percent())
            data["ram"] = int(psutil.virtual_memory().percent)
            battery = psutil.sensors_battery()
            data["battery"] = int(battery.percent) if battery else None
        except Exception:
            pass
        self.info_ready.emit(data)

class JarvisWidget(QWidget):
    HIDDEN_SIZE = QSize(120, 4)
    MINIMIZE_SIZE = QSize(120, 32)
    # The idle surface contains only network, clock and battery status. Keep
    # it tight instead of reserving the wider legacy identity/close controls.
    COLLAPSED_SIZE = QSize(300, 52)
    MEDIA_SIZE = QSize(520, 60)
    CHARGING_SIZE = QSize(360, 56)
    LOW_POWER_SIZE = QSize(350, 56)
    HEADSET_SIZE = QSize(350, 56)
    NOTIFICATION_SIZE = QSize(370, 64)
    CALL_SIZE = QSize(360, 52)
    TIMER_SIZE = QSize(270, 58)
    MEDIA_MIN_WIDTH = 400
    MEDIA_BASE_WIDTH = 300
    EXPANDED_SIZE = QSize(440, 430)
    FEATURE_EXPANDED_SIZE = QSize(440, 230)
    DASHBOARD_EXPANDED_SIZE = QSize(520, 260)
    MEDIA_FEATURE_MIN_WIDTH = 390
    MEDIA_FEATURE_MAX_WIDTH = 560
    MEDIA_FEATURE_HEIGHT = 160
    TOP_MARGIN = 8
    HOT_ZONE_WIDTH = 140
    HOT_ZONE_HEIGHT = 12
    COMPACT_TRANSITION_MS = 320
    PANEL_TRANSITION_MS = 380

    def __init__(self):
        super().__init__()
        self.is_expanded = False
        self._expanded_view = "feature"
        self._feature_action = None
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
        self._foreground_title = ""
        self._foreground_process = ""
        self._call_context = None
        self._call_muted = False
        self._call_miss_count = 0
        self._timer_active = False
        self._timer_running = False
        self._timer_remaining = 0.0
        self._timer_deadline = None
        self._timer_generation = 0
        self._discord_log_path = None
        self._discord_log_offset = 0
        self._discord_rtc_active = False
        self._default_page_override = False
        self._activity_page = "default"
        self._swipe_start_pos = None
        self._global_swipe_start = None
        self._last_page_switch = 0.0
        self._page_switch_animation = None
        QApplication.instance().installEventFilter(self)
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
        self._call_timer = QTimer(self)
        self._call_timer.setInterval(2000)
        self._call_timer.timeout.connect(self._check_call_context)
        self._call_timer.start()
        self._call_hide_timer = QTimer(self)
        self._call_hide_timer.setSingleShot(True)
        self._call_hide_timer.timeout.connect(self.hide_call_island)
        self._feature_collapse_timer = QTimer(self)
        self._feature_collapse_timer.setSingleShot(True)
        self._feature_collapse_timer.timeout.connect(self._auto_collapse_expanded)
        self._last_input_activity = 0.0
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._update_default_status)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(200)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self.initUI()
        self._init_system_tray()
        self._update_default_status()
        self._sync_compact_surface()
        self._status_timer.start()
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
        self.main_layout = main_layout
        
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
        # Keep compact-bar contents on one composited layer. During a hide
        # transition that layer fades before the surface becomes too narrow,
        # so Qt never visibly reflows the cover and controls into a pile.
        self.title_bar_opacity = QGraphicsOpacityEffect(self.title_bar)
        self.title_bar_opacity.setOpacity(1.0)
        self.title_bar.setGraphicsEffect(self.title_bar_opacity)
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

        self.call_mute_btn = QPushButton("Mute")
        self.call_mute_btn.setToolTip("Mute this computer's microphone")
        self.call_mute_btn.setFixedSize(64, 30)
        self.call_mute_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.call_mute_btn.setStyleSheet("""
            QPushButton { background: rgba(255, 255, 255, 18);
                          border: 1px solid rgba(255, 255, 255, 32);
                          border-radius: 15px; color: white; }
            QPushButton:hover { background: rgba(255, 255, 255, 32); }
            QPushButton:pressed { background: rgba(255, 69, 58, 70); }
        """)
        self.call_mute_btn.clicked.connect(self.toggle_call_mute)
        self.call_mute_btn.hide()
        
        # Retained as a hidden compatibility handle for older integrations.
        # Closing Dexget now lives exclusively in its system-tray menu.
        self.close_btn = QPushButton("✕", self)
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
        self.close_btn.clicked.connect(self.force_close)
        self.close_btn.hide()

        self.default_status_widget = QWidget()
        default_status_layout = QHBoxLayout(self.default_status_widget)
        default_status_layout.setContentsMargins(0, 0, 0, 0)
        default_status_layout.setSpacing(8)
        self.default_network_indicator = WifiStatusIndicator()
        self.default_clock_label = QLabel("12:00 AM")
        self.default_battery_indicator = CompactBatteryStatus()
        self.default_clock_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.default_clock_label.setStyleSheet("color: white;")
        self.default_clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_clock_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        default_status_layout.addWidget(self.default_network_indicator)
        default_status_layout.addWidget(self.default_clock_label, 1)
        default_status_layout.addWidget(self.default_battery_indicator)
        self.default_status_widget.hide()

        self.timer_status_widget = QWidget()
        timer_status_layout = QHBoxLayout(self.timer_status_widget)
        timer_status_layout.setContentsMargins(0, 0, 0, 0)
        timer_status_layout.setSpacing(10)
        self.timer_pause_btn = TimerToggleButton()
        self.timer_pause_btn.setToolTip("Pause timer")
        self.timer_cancel_btn = QPushButton("×")
        self.timer_cancel_btn.setFixedSize(40, 40)
        self.timer_cancel_btn.setToolTip("Cancel timer")
        self.timer_cancel_btn.setStyleSheet("""
            QPushButton { background: #62646a; color: white; border: none;
                          border-radius: 20px; font-size: 27px; font-weight: 300; }
            QPushButton:hover { background: #74767d; }
            QPushButton:pressed { background: #4d4f54; }
        """)
        self.timer_caption_label = QLabel("Timer")
        self.timer_caption_label.setFont(QFont("Segoe UI", 9))
        self.timer_caption_label.setStyleSheet("color: #ff9f0a;")
        self.timer_remaining_label = QLabel("0:00")
        self.timer_remaining_label.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
        self.timer_remaining_label.setStyleSheet("color: #ff8a00;")
        self.timer_remaining_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        timer_status_layout.addWidget(self.timer_pause_btn)
        timer_status_layout.addWidget(self.timer_cancel_btn)
        timer_status_layout.addSpacing(6)
        timer_status_layout.addWidget(self.timer_caption_label)
        timer_status_layout.addWidget(self.timer_remaining_label)
        self.timer_pause_btn.clicked.connect(self.toggle_timer)
        self.timer_cancel_btn.clicked.connect(self.cancel_timer)
        self.timer_status_widget.hide()
        
        title_layout.addWidget(self.status_dot)
        title_layout.addWidget(self.album_art)
        # The metadata block owns the remaining width. A separate stretch here
        # collapses this layout to zero because its labels use Ignored sizing.
        title_layout.addWidget(self.identity_widget, 1)
        title_layout.addWidget(self.default_status_widget, 1)
        title_layout.addWidget(self.timer_status_widget, 1)
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
        title_layout.addWidget(self.call_mute_btn)
        title_layout.addWidget(self.screen_assist_btn)
        self._set_media_controls_visible(False)
        
        # Event filters for dragging
        self.title_bar.mousePressEvent = self.title_mousePressEvent
        self.title_bar.mouseReleaseEvent = self.title_mouseReleaseEvent
        
        # --- Contextual feature surface ---
        self.feature_panel = QFrame()
        self.feature_panel.setStyleSheet("""
            QFrame#FeaturePanel { background: transparent; }
            QLabel#FeatureEyebrow { color: #7ecfff; font-size: 10px;
                                    font-weight: 700; letter-spacing: 1px; }
            QLabel#FeatureTitle { color: white; font-size: 20px; font-weight: 650; }
            QLabel#FeatureDetail { color: #aeb5bf; font-size: 12px; }
        """)
        self.feature_panel.setObjectName("FeaturePanel")
        self.feature_panel.mousePressEvent = self.feature_mousePressEvent
        self.feature_panel.mouseReleaseEvent = self.feature_mouseReleaseEvent
        feature_layout = QVBoxLayout(self.feature_panel)
        feature_layout.setContentsMargins(22, 14, 22, 14)
        feature_layout.setSpacing(7)
        self.feature_eyebrow = QLabel("DEXGET")
        self.feature_eyebrow.setObjectName("FeatureEyebrow")
        self.feature_title = QLabel("Ready")
        self.feature_title.setObjectName("FeatureTitle")
        self.feature_title.setWordWrap(True)
        self.feature_detail = QLabel("Choose a feature or open Dexget AI.")
        self.feature_detail.setObjectName("FeatureDetail")
        self.feature_detail.setWordWrap(True)

        # Dedicated expanded media player.  It is laid out before the window
        # grows, so the island opens directly at its final Apple-style shape.
        self.media_feature_widget = QFrame()
        self.media_feature_widget.setObjectName("MediaFeaturePlayer")
        self.media_feature_widget.setStyleSheet("""
            QFrame#MediaFeaturePlayer { background: transparent; }
            QLabel#MediaFeatureTitle { color: white; font-size: 14px; font-weight: 700; }
            QLabel#MediaFeatureArtist { color: #aeb5bf; font-size: 11px; }
            QLabel#MediaFeatureTime { color: #9aa1aa; font-size: 8px; }
            QSlider::groove:horizontal { height: 3px; background: #50555d; border-radius: 1px; }
            QSlider::sub-page:horizontal { background: white; border-radius: 1px; }
            QSlider::handle:horizontal { background: white; width: 6px; margin: -2px 0;
                                         border-radius: 3px; }
        """)
        media_player_layout = QVBoxLayout(self.media_feature_widget)
        media_player_layout.setContentsMargins(0, 0, 0, 0)
        media_player_layout.setSpacing(6)
        media_header = QHBoxLayout()
        media_header.setSpacing(10)
        self.media_feature_art = QLabel("♪")
        self.media_feature_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.media_feature_art.setFixedSize(60, 60)
        self.media_feature_art.setStyleSheet(
            "background: #202329; border-radius: 8px; color: #8f99a6; font-size: 20px;")
        media_identity = QVBoxLayout()
        media_identity.setSpacing(2)
        self.media_feature_title = QLabel("Now playing")
        self.media_feature_title.setObjectName("MediaFeatureTitle")
        self.media_feature_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.media_feature_artist = QLabel("Media")
        self.media_feature_artist.setObjectName("MediaFeatureArtist")
        self.media_feature_artist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        media_identity.addStretch()
        media_identity.addWidget(self.media_feature_title)
        media_identity.addWidget(self.media_feature_artist)
        media_identity.addStretch()
        self.media_feature_visualizer = MediaWaveformIndicator()
        media_header.addWidget(self.media_feature_art)
        media_header.addLayout(media_identity, 1)
        media_header.addWidget(self.media_feature_visualizer)
        media_player_layout.addLayout(media_header)

        timeline_layout = QHBoxLayout()
        timeline_layout.setSpacing(7)
        self.media_elapsed_label = QLabel("0:00")
        self.media_elapsed_label.setObjectName("MediaFeatureTime")
        self.media_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.media_seek_slider.setRange(0, 0)
        self.media_seek_slider.sliderReleased.connect(self._seek_expanded_media)
        self.media_total_label = QLabel("0:00")
        self.media_total_label.setObjectName("MediaFeatureTime")
        timeline_layout.addWidget(self.media_elapsed_label)
        timeline_layout.addWidget(self.media_seek_slider, 1)
        timeline_layout.addWidget(self.media_total_label)
        media_player_layout.addLayout(timeline_layout)

        media_controls = QHBoxLayout()
        media_controls.setSpacing(22)
        media_controls.addStretch()
        self.media_feature_previous_btn = MediaControlButton("previous")
        self.media_feature_play_btn = MediaControlButton("play_pause")
        self.media_feature_next_btn = MediaControlButton("next")
        for button in (self.media_feature_previous_btn, self.media_feature_play_btn,
                       self.media_feature_next_btn):
            button.setToolTip({
                self.media_feature_previous_btn: "Previous",
                self.media_feature_play_btn: "Play or pause",
                self.media_feature_next_btn: "Next",
            }[button])
        self.media_feature_previous_btn.clicked.connect(
            lambda: self._control_expanded_media("previous"))
        self.media_feature_play_btn.clicked.connect(
            lambda: self._control_expanded_media("play_pause"))
        self.media_feature_next_btn.clicked.connect(
            lambda: self._control_expanded_media("next"))
        media_controls.addWidget(self.media_feature_previous_btn)
        media_controls.addWidget(self.media_feature_play_btn)
        media_controls.addWidget(self.media_feature_next_btn)
        media_controls.addStretch()
        media_player_layout.addLayout(media_controls)
        self.media_feature_widget.hide()

        # Full control-center dashboard inspired by the compact Windows
        # Dynamic Island references: one cohesive black surface, contextual
        # pages, and no nested legacy cards or duplicated title bar.
        self.dashboard_widget = QFrame()
        self.dashboard_widget.setObjectName("Dashboard")
        self.dashboard_widget.setStyleSheet("""
            QFrame#Dashboard { background: transparent; }
            QLabel { color: #f5f5f7; }
            QPushButton { color: #d7d7dc; background: transparent; border: none;
                          border-radius: 12px; padding: 7px 12px; font-size: 12px; }
            QPushButton:hover { background: #202124; color: white; }
            QPushButton:checked { background: #2b2c30; color: white; }
            QLineEdit { color: white; background: #151517; border: none;
                        border-radius: 11px; padding: 10px 14px; font-size: 13px; }
            QSlider::groove:horizontal { height: 7px; background: #36373b;
                                         border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #ffcf00; border-radius: 3px; }
            QSlider::handle:horizontal { background: white; width: 18px;
                                         margin: -6px 0; border-radius: 9px; }
        """)
        dashboard_layout = QVBoxLayout(self.dashboard_widget)
        dashboard_layout.setContentsMargins(8, 0, 8, 0)
        dashboard_layout.setSpacing(8)

        nav = QHBoxLayout()
        nav.setSpacing(5)
        self.dashboard_nav_buttons = {}
        nav_items = (("home", "⌂"), ("clipboard", "▣"),
                     ("tasks", "✓"), ("focus", "◷"))
        for key, icon in nav_items:
            button = QPushButton(icon)
            button.setCheckable(True)
            button.setFixedSize(40, 36)
            button.setFont(QFont("Segoe UI Symbol", 16))
            button.clicked.connect(lambda checked=False, page=key: self._show_dashboard_page(page))
            nav.addWidget(button)
            self.dashboard_nav_buttons[key] = button
        nav.addStretch(1)
        handle = QLabel("━━━━")
        handle.setStyleSheet("color:#414247; font-size:13px;")
        nav.addWidget(handle)
        nav.addStretch(1)
        for key, icon in (("search", "⌕"), ("alerts", "♢"), ("settings", "☷")):
            button = QPushButton(icon)
            button.setCheckable(key in ("search", "settings"))
            button.setFixedSize(40, 36)
            button.setFont(QFont("Segoe UI Symbol", 16))
            if key == "alerts":
                button.clicked.connect(lambda: self._launch_uri("ms-settings:notifications"))
            else:
                button.clicked.connect(lambda checked=False, page=key: self._show_dashboard_page(page))
                self.dashboard_nav_buttons[key] = button
            nav.addWidget(button)
        dashboard_layout.addLayout(nav)

        self.dashboard_stack = QStackedWidget()
        self.dashboard_pages = {}
        dashboard_layout.addWidget(self.dashboard_stack, 1)

        def page_frame(name):
            page = QFrame()
            page.setObjectName("DashboardPage")
            self.dashboard_pages[name] = page
            self.dashboard_stack.addWidget(page)
            return page

        def card(title, subtitle, accent="#0a84ff"):
            frame = QFrame()
            frame.setStyleSheet("QFrame { background:#151517; border-radius:14px; }")
            row = QHBoxLayout(frame)
            row.setContentsMargins(14, 10, 14, 10)
            glyph = QLabel("●")
            glyph.setStyleSheet(f"color:{accent}; font-size:20px;")
            text_box = QVBoxLayout()
            heading = QLabel(title)
            heading.setStyleSheet("font-size:14px; font-weight:700;")
            detail = QLabel(subtitle)
            detail.setStyleSheet("color:#92939a; font-size:11px;")
            text_box.addWidget(heading)
            text_box.addWidget(detail)
            row.addWidget(glyph)
            row.addLayout(text_box, 1)
            return frame, heading, detail, row

        home = page_frame("home")
        home_grid = QGridLayout(home)
        home_grid.setContentsMargins(0, 0, 0, 0)
        home_grid.setSpacing(9)
        wifi_card, self.dashboard_wifi_title, self.dashboard_wifi_detail, wifi_row = card(
            "Wi-Fi", "Checking connection…")
        self.dashboard_wifi_card = wifi_card
        wifi_open = QPushButton("Networks  ›")
        wifi_open.clicked.connect(lambda: self._launch_uri("ms-settings:network-wifi"))
        wifi_row.addWidget(wifi_open)
        home_grid.addWidget(wifi_card, 0, 0)
        bluetooth_card, _, self.dashboard_bluetooth_detail, bluetooth_row = card(
            "Bluetooth", "Devices", "#0a84ff")
        self.dashboard_bluetooth_card = bluetooth_card
        bluetooth_open = QPushButton("Devices  ›")
        bluetooth_open.clicked.connect(lambda: self._launch_uri("ms-settings:bluetooth"))
        bluetooth_row.addWidget(bluetooth_open)
        home_grid.addWidget(bluetooth_card, 1, 0)

        controls = QFrame()
        self.dashboard_controls_card = controls
        controls.setStyleSheet("QFrame { background:#151517; border-radius:14px; }")
        controls_layout = QGridLayout(controls)
        controls_layout.setContentsMargins(14, 9, 14, 9)
        controls_layout.addWidget(QLabel("🔊"), 0, 0)
        self.dashboard_volume = QSlider(Qt.Orientation.Horizontal)
        self.dashboard_volume.setRange(0, 100)
        self.dashboard_volume.sliderReleased.connect(self._apply_dashboard_volume)
        controls_layout.addWidget(self.dashboard_volume, 0, 1)
        self.dashboard_volume_value = QLabel("--")
        controls_layout.addWidget(self.dashboard_volume_value, 0, 2)
        controls_layout.addWidget(QLabel("☀"), 1, 0)
        self.dashboard_brightness = QSlider(Qt.Orientation.Horizontal)
        self.dashboard_brightness.setRange(0, 100)
        self.dashboard_brightness.sliderReleased.connect(self._apply_dashboard_brightness)
        controls_layout.addWidget(self.dashboard_brightness, 1, 1)
        self.dashboard_brightness_value = QLabel("--")
        controls_layout.addWidget(self.dashboard_brightness_value, 1, 2)
        home_grid.addWidget(controls, 0, 1, 2, 1)

        stats = QFrame()
        self.dashboard_stats_card = stats
        stats.setStyleSheet("QFrame { background:#151517; border-radius:14px; }")
        stats_layout = QHBoxLayout(stats)
        self.dashboard_cpu = QLabel("CPU  --%")
        self.dashboard_ram = QLabel("RAM  --%")
        self.dashboard_battery = QLabel("Battery  --%")
        for label in (self.dashboard_cpu, self.dashboard_ram, self.dashboard_battery):
            label.setStyleSheet("font-size:13px; font-weight:650;")
            stats_layout.addWidget(label)
        stats_layout.addStretch()
        focus_button = QPushButton("☾  Focus")
        focus_button.clicked.connect(lambda: self._show_dashboard_page("focus"))
        stats_layout.addWidget(focus_button)
        # CPU, RAM and battery summary section intentionally removed.
        stats.hide()
        self.dashboard_wifi_card.hide()
        self.dashboard_bluetooth_card.hide()
        self.dashboard_controls_card.hide()
        home_grid.setColumnStretch(0, 1)
        home_grid.setColumnStretch(1, 1)

        tasks = page_frame("tasks")
        tasks_layout = QVBoxLayout(tasks)
        tasks_layout.setContentsMargins(0, 0, 0, 0)
        task_tabs = QHBoxLayout()
        task_tabs.addWidget(QLabel("Tasks     Notes"))
        task_tabs.addStretch()
        self.dashboard_task_count = QLabel("0 to do")
        task_tabs.addWidget(self.dashboard_task_count)
        tasks_layout.addLayout(task_tabs)
        task_entry_row = QHBoxLayout()
        self.dashboard_task_entry = QLineEdit()
        self.dashboard_task_entry.setPlaceholderText("New task")
        self.dashboard_task_entry.returnPressed.connect(self._add_dashboard_task)
        add_task = QPushButton("＋ Add")
        add_task.clicked.connect(self._add_dashboard_task)
        task_entry_row.addWidget(self.dashboard_task_entry, 1)
        task_entry_row.addWidget(add_task)
        tasks_layout.addLayout(task_entry_row)
        self.dashboard_task_list = QVBoxLayout()
        tasks_layout.addLayout(self.dashboard_task_list)
        tasks_layout.addStretch()

        clipboard = page_frame("clipboard")
        clipboard_layout = QVBoxLayout(clipboard)
        clipboard_layout.setContentsMargins(0, 0, 0, 0)
        self.dashboard_clipboard_entry = QLineEdit()
        self.dashboard_clipboard_entry.setPlaceholderText(
            "Paste from clipboard history or a pinned snippet")
        clipboard_layout.addWidget(self.dashboard_clipboard_entry)
        clipboard_header = QHBoxLayout()
        clipboard_header.addWidget(QLabel("Pinned"))
        clipboard_header.addStretch()
        pin_current = QPushButton("Pin current clipboard")
        pin_current.clicked.connect(self._pin_current_clipboard)
        clipboard_header.addWidget(pin_current)
        clipboard_layout.addLayout(clipboard_header)
        self.dashboard_clipboard_list = QVBoxLayout()
        clipboard_layout.addLayout(self.dashboard_clipboard_list)
        clipboard_layout.addStretch()

        focus = page_frame("focus")
        focus_layout = QVBoxLayout(focus)
        focus_layout.setContentsMargins(0, 0, 0, 0)
        focus_layout.addWidget(QLabel("Focus     Timer     Stopwatch"))
        self.dashboard_focus_name = QLineEdit()
        self.dashboard_focus_name.setPlaceholderText("What are you working on?")
        focus_layout.addWidget(self.dashboard_focus_name)
        focus_options = QHBoxLayout()
        for minutes in (25, 50):
            button = QPushButton(f"{minutes} min")
            button.clicked.connect(lambda checked=False, value=minutes: self._set_focus_minutes(value))
            focus_options.addWidget(button)
        custom_focus = QPushButton("Custom")
        custom_focus.clicked.connect(self.prompt_timer)
        focus_options.addWidget(custom_focus)
        focus_options.addStretch()
        self.dashboard_start_focus = QPushButton("▶  Start focus")
        self.dashboard_start_focus.setStyleSheet(
            "background:#a77cff; color:white; border-radius:18px; font-weight:700;")
        self.dashboard_start_focus.clicked.connect(self._start_focus_timer)
        focus_options.addWidget(self.dashboard_start_focus)
        focus_layout.addLayout(focus_options)
        focus_layout.addStretch()

        search = page_frame("search")
        search_layout = QVBoxLayout(search)
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.dashboard_search_entry = QLineEdit()
        self.dashboard_search_entry.setPlaceholderText("Search, calculate, or ask Dexget")
        self.dashboard_search_entry.returnPressed.connect(self._run_dashboard_search)
        search_layout.addWidget(self.dashboard_search_entry)
        self.dashboard_search_result = QLabel("Type a calculation or search query")
        self.dashboard_search_result.setStyleSheet(
            "background:#19191c; border-radius:12px; padding:14px; font-size:14px;")
        search_layout.addWidget(self.dashboard_search_result)
        search_layout.addStretch()

        settings = page_frame("settings")
        settings_layout = QGridLayout(settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_actions = (
            ("Battery settings", "ms-settings:batterysaver"),
            ("Notifications", "ms-settings:notifications"),
            ("Dynamic Island preferences", "ms-settings:appsfeatures"),
        )
        for index, (text_value, uri) in enumerate(settings_actions):
            button = QPushButton(text_value)
            button.setFixedHeight(48)
            button.setStyleSheet("background:#18181b; text-align:left; padding-left:16px;")
            button.clicked.connect(lambda checked=False, target=uri: self._launch_uri(target))
            settings_layout.addWidget(button, index // 2, index % 2)

        self.dashboard_settings = settings
        self.dashboard_added_widgets = {}
        self.dashboard_optional_buttons = {}
        self.dashboard_buttons = self.dashboard_nav_buttons
        self._focus_minutes = 25
        self._load_dashboard_tasks()
        self._load_pinned_clipboard()
        # Start on the lightweight summary page; system controls that the user
        # removed are neither shown nor queried.
        self.dashboard_stack.setCurrentWidget(self.dashboard_pages["home"])
        self.dashboard_nav_buttons["home"].setChecked(True)
        self.dashboard_widget.hide()

        feature_actions = QHBoxLayout()
        feature_actions.setSpacing(8)
        self.feature_primary_btn = QPushButton("Screen Assist")
        self.feature_primary_btn.setFixedHeight(34)
        self.feature_primary_btn.clicked.connect(self._run_feature_action)
        self.feature_ai_btn = QPushButton("✦  Dexget AI")
        self.feature_ai_btn.setFixedHeight(34)
        self.feature_ai_btn.clicked.connect(self.open_ai_panel)
        self.feature_ai_btn.hide()
        for button in (self.feature_primary_btn, self.feature_ai_btn):
            button.setStyleSheet("""
                QPushButton { color: white; background: rgba(255,255,255,18);
                              border: 1px solid rgba(255,255,255,35);
                              border-radius: 17px; padding: 0 15px; }
                QPushButton:hover { background: rgba(74,144,226,90); }
                QPushButton:pressed { background: rgba(74,144,226,130); }
            """)
        feature_actions.addWidget(self.feature_primary_btn)
        feature_actions.addStretch()
        feature_layout.addWidget(self.feature_eyebrow)
        feature_layout.addWidget(self.feature_title)
        feature_layout.addWidget(self.feature_detail)
        feature_layout.addWidget(self.media_feature_widget)
        feature_layout.addWidget(self.dashboard_widget)
        feature_layout.addStretch()
        feature_layout.addLayout(feature_actions)
        self.feature_panel.hide()

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
        self.input_field.textEdited.connect(self._mark_input_activity)
        
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
        container_layout.addWidget(self.feature_panel)
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
        # Anchor all width variants to the monitor's actual centre.  Using the
        # window's transient screen during a resize could retain an off-centre
        # native frame when a long title changed the island width.
        screen = QApplication.primaryScreen() or self.screen()
        area = screen.availableGeometry()
        x = area.x() + (area.width() - size.width()) // 2
        y = area.y() if size == self.HIDDEN_SIZE else area.y() + self.TOP_MARGIN
        return QRect(x, y, size.width(), size.height())

    @staticmethod
    def _centered_frame(center_x, y, width, height):
        return QRect(round(center_x - width / 2.0), y, width, height)

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

    def _is_default_activity(self):
        return not any((self._media, self._notification_active,
                        self._headset_active, self._low_power_active,
                        self._charging_active, self._call_context,
                        self._timer_active))

    def _displaying_default_page(self):
        return self._default_page_override or self._is_default_activity()

    def _sync_compact_surface(self):
        default = bool((self._default_page_override or
                        (self._activity_page == "default" and self._is_default_activity()))
                       and not any((self._notification_active, self._headset_active,
                                    self._low_power_active, self._charging_active)))
        timer_visible = bool(self._activity_page == "timer" and self._timer_active and not any((
            self._notification_active, self._headset_active,
            self._low_power_active, self._charging_active)))
        self.default_status_widget.setVisible(default)
        self.timer_status_widget.setVisible(timer_visible)
        if timer_visible:
            self.status_dot.hide()
            self.identity_widget.hide()
            self.screen_assist_btn.hide()
            self.close_btn.hide()
            self.call_mute_btn.hide()
            self._set_media_controls_visible(False)
            return
        if default:
            self.name_label.clear()
            self.status_label.clear()
            self.status_dot.hide()
            self.album_art.hide()
            self.identity_widget.hide()
            self.screen_assist_btn.hide()
            self.close_btn.hide()
            self.call_mute_btn.hide()
            self._set_media_controls_visible(False)
        elif self._activity_page in ("media", "timer") and (self._media or self._call_context):
            self.default_status_widget.hide()
            self.status_dot.show()
            self.identity_widget.show()
            if self._activity_page == "media" and self._media:
                self.name_label.setText(self._media.get("title") or "Now playing")
                self.status_label.setText(
                    self._media.get("artist") or self._media.get("app", "Media"))
            self.close_btn.hide()

    def _update_default_status(self):
        if not hasattr(self, "default_clock_label"):
            return
        from datetime import datetime
        self.default_clock_label.setText(datetime.now().strftime("%I:%M %p").lstrip("0"))
        connected = False
        try:
            import ctypes
            flags = ctypes.c_ulong()
            connected = bool(ctypes.windll.wininet.InternetGetConnectedState(
                ctypes.byref(flags), 0))
        except Exception:
            pass
        self.default_network_indicator.set_connected(connected)
        try:
            import psutil
            battery = psutil.sensors_battery()
            percent = int(round(battery.percent)) if battery else None
            charging = bool(battery.power_plugged) if battery else False
        except Exception:
            percent = None
            charging = False
        self.default_battery_indicator.set_status(percent, charging)

    @staticmethod
    def _format_countdown(seconds):
        total = max(0, int(seconds + 0.999))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (f"{hours}:{minutes:02d}:{seconds:02d}" if hours
                else f"{minutes}:{seconds:02d}")

    def prompt_timer(self):
        minutes, accepted = QInputDialog.getInt(
            self, "Start timer", "Timer length in minutes:", 5, 1, 1440, 1)
        if accepted:
            self.start_timer(minutes * 60)

    def start_timer(self, seconds):
        seconds = max(1.0, float(seconds))
        # A timer started from the default page becomes the active service;
        # do not leave the page override in place or it will inherit the
        # background media player's geometry and surface routing.
        self._default_page_override = False
        self._activity_page = "timer"
        self._expanded_view = "feature"
        # Tear down any expanded media/dashboard content before presenting the
        # timer activity.  This keeps the timer as a distinct island activity
        # instead of leaving the previous media panel underneath it.
        self.feature_panel.hide()
        self.media_feature_widget.hide()
        self.dashboard_widget.hide()
        self.title_bar.show()
        self._timer_generation += 1
        self._timer_active = True
        self._timer_running = True
        self._timer_remaining = seconds
        self._timer_deadline = time.monotonic() + seconds
        self.timer_caption_label.setText("Timer")
        self.timer_pause_btn.setText("Ⅱ")
        self.timer_pause_btn.setToolTip("Pause timer")
        self.timer_remaining_label.setText(self._format_countdown(seconds))
        self._countdown_timer.start()
        self._collapse_timer.stop()
        self._feature_collapse_timer.stop()
        self.is_expanded = False
        self._present_compact(self.TIMER_SIZE)

    def _tick_countdown(self):
        if not self._timer_active or not self._timer_running:
            return
        self._timer_remaining = max(
            0.0, (self._timer_deadline or time.monotonic()) - time.monotonic())
        self.timer_remaining_label.setText(
            self._format_countdown(self._timer_remaining))
        if self._timer_remaining <= 0:
            self._timer_running = False
            self._timer_deadline = None
            self._countdown_timer.stop()
            self.timer_caption_label.setText("Timer done")
            self.timer_pause_btn.setText("▶")
            self.timer_pause_btn.setEnabled(False)
            QApplication.beep()
            generation = self._timer_generation
            QTimer.singleShot(
                8000,
                lambda: self.cancel_timer()
                if generation == self._timer_generation else None)

    def toggle_timer(self):
        if not self._timer_active or self._timer_remaining <= 0:
            return
        if self._timer_running:
            self._timer_remaining = max(
                0.0, (self._timer_deadline or time.monotonic()) - time.monotonic())
            self._timer_running = False
            self._timer_deadline = None
            self._countdown_timer.stop()
            self.timer_pause_btn.setText("▶")
            self.timer_pause_btn.setToolTip("Resume timer")
        else:
            self._timer_running = True
            self._timer_deadline = time.monotonic() + self._timer_remaining
            self._countdown_timer.start()
            self.timer_pause_btn.setText("Ⅱ")
            self.timer_pause_btn.setToolTip("Pause timer")
        self.timer_remaining_label.setText(
            self._format_countdown(self._timer_remaining))

    def cancel_timer(self):
        if not self._timer_active:
            return
        self._timer_generation += 1
        self._countdown_timer.stop()
        self._timer_active = False
        self._timer_running = False
        self._timer_remaining = 0.0
        self._timer_deadline = None
        self._activity_page = "media" if (self._media or self._call_context) else "default"
        self.timer_pause_btn.setEnabled(True)
        self.timer_status_widget.hide()
        self._sync_compact_surface()
        if self._media and self._media.get("playing"):
            self.activate_media_island()
        else:
            self._present_compact(self._compact_size())
            self._collapse_timer.start(1800)

    @staticmethod
    def _launch_uri(uri):
        try:
            os.startfile(uri)
        except Exception:
            pass

    @staticmethod
    def _launch_program(program):
        try:
            import subprocess
            subprocess.Popen([program])
        except Exception:
            pass

    def _toggle_dashboard_settings(self):
        self._show_dashboard_page("settings")
        self._keep_feature_open()

    def _set_dashboard_preference(self, key, enabled):
        QSettings("Dexget", "DynamicIsland").setValue(
            f"dashboard/{key}", bool(enabled))
        if key in self.dashboard_added_widgets:
            self.dashboard_added_widgets[key].setVisible(bool(enabled))
        self._keep_feature_open()

    def _show_dashboard_page(self, name):
        page = self.dashboard_pages.get(name)
        if page is None:
            return
        self.dashboard_stack.setCurrentWidget(page)
        for key, button in self.dashboard_nav_buttons.items():
            button.setChecked(key == name)
        if name == "home":
            self._refresh_dashboard_system_info()
        elif name == "clipboard":
            self.dashboard_clipboard_entry.setText(
                QApplication.clipboard().text()[:300])
        elif name == "search":
            QTimer.singleShot(80, self.dashboard_search_entry.setFocus)
        self._keep_feature_open()

    def _refresh_dashboard_system_info(self):
        # Never wait for PowerShell, WinRT, WMI, or audio COM calls on the Qt
        # event loop. The panel opens using its last values and is refreshed
        # asynchronously as soon as Windows answers.
        worker = getattr(self, "_dashboard_info_worker", None)
        if worker is None:
            worker = DashboardSystemWorker(self)
            worker.info_ready.connect(self._apply_dashboard_system_info)
            self._dashboard_info_worker = worker
        if not worker.isRunning():
            worker.start()

    def _apply_dashboard_system_info(self, data):
        if "cpu" in data:
            self.dashboard_cpu.setText(f"CPU  {data['cpu']}%")
        if "ram" in data:
            self.dashboard_ram.setText(f"RAM  {data['ram']}%")
        if "battery" in data:
            battery = data["battery"]
            self.dashboard_battery.setText(
                f"Battery  {battery}%" if battery is not None else "Battery  --%")
        if "wifi" in data:
            wifi = str(data["wifi"])
            self.dashboard_wifi_detail.setText(
                "Connected" if wifi.upper() == "ON" else wifi.title())
        if "bluetooth" in data:
            self.dashboard_bluetooth_detail.setText(
                str(data["bluetooth"]).title())
        if "volume" in data:
            self.dashboard_volume.setValue(data["volume"])
            self.dashboard_volume_value.setText(str(data["volume"]))
        if "brightness" in data:
            self.dashboard_brightness.setValue(data["brightness"])
            self.dashboard_brightness_value.setText(str(data["brightness"]))

    def _apply_dashboard_volume(self):
        value = self.dashboard_volume.value()
        self.dashboard_volume_value.setText(str(value))
        try:
            from jarvis.capabilities.windows_system import volume_set
            volume_set(value)
        except Exception:
            pass

    def _apply_dashboard_brightness(self):
        value = self.dashboard_brightness.value()
        self.dashboard_brightness_value.setText(str(value))
        try:
            from jarvis.capabilities.windows_system import brightness_set
            brightness_set(value)
        except Exception:
            pass

    def _load_dashboard_tasks(self):
        tasks = QSettings("Dexget", "DynamicIsland").value(
            "dashboard/tasks", [], type=list) or []
        for text_value in tasks:
            self._append_dashboard_task(str(text_value), persist=False)
        self._update_dashboard_task_count()

    def _dashboard_task_texts(self):
        return [button.text()[2:] for button in self.dashboard_task_buttons]

    def _append_dashboard_task(self, text_value, persist=True):
        text_value = text_value.strip()
        if not text_value:
            return
        button = QPushButton(f"○ {text_value}")
        button.setStyleSheet("text-align:left; font-size:14px; padding:5px 8px;")
        button.clicked.connect(lambda checked=False, item=button: self._complete_dashboard_task(item))
        self.dashboard_task_list.addWidget(button)
        if not hasattr(self, "dashboard_task_buttons"):
            self.dashboard_task_buttons = []
        self.dashboard_task_buttons.append(button)
        if persist:
            self._save_dashboard_tasks()
        self._update_dashboard_task_count()

    def _add_dashboard_task(self):
        text_value = self.dashboard_task_entry.text()
        self.dashboard_task_entry.clear()
        self._append_dashboard_task(text_value)

    def _complete_dashboard_task(self, button):
        if button in self.dashboard_task_buttons:
            self.dashboard_task_buttons.remove(button)
        button.deleteLater()
        self._save_dashboard_tasks()
        self._update_dashboard_task_count()

    def _save_dashboard_tasks(self):
        QSettings("Dexget", "DynamicIsland").setValue(
            "dashboard/tasks", self._dashboard_task_texts())

    def _update_dashboard_task_count(self):
        count = len(getattr(self, "dashboard_task_buttons", []))
        self.dashboard_task_count.setText(f"{count} to do")

    def _load_pinned_clipboard(self):
        self.dashboard_clipboard_buttons = []
        values = QSettings("Dexget", "DynamicIsland").value(
            "dashboard/clipboard", [], type=list) or []
        for text_value in values:
            self._append_clipboard_pin(str(text_value), persist=False)

    def _pin_current_clipboard(self):
        text_value = QApplication.clipboard().text().strip()
        if text_value:
            self._append_clipboard_pin(text_value)

    def _append_clipboard_pin(self, text_value, persist=True):
        if any(button.property("clipText") == text_value
               for button in self.dashboard_clipboard_buttons):
            return
        button = QPushButton(f"📌  {text_value[:82]}")
        button.setProperty("clipText", text_value)
        button.setStyleSheet("background:#1b1b1e; text-align:left; padding:9px 12px;")
        button.clicked.connect(
            lambda checked=False, value=text_value: QApplication.clipboard().setText(value))
        self.dashboard_clipboard_list.addWidget(button)
        self.dashboard_clipboard_buttons.append(button)
        if persist:
            QSettings("Dexget", "DynamicIsland").setValue(
                "dashboard/clipboard",
                [item.property("clipText") for item in self.dashboard_clipboard_buttons])

    def _set_focus_minutes(self, minutes):
        self._focus_minutes = int(minutes)
        self.dashboard_start_focus.setText(f"▶  Start {minutes} min focus")

    def _start_focus_timer(self):
        self.start_timer(self._focus_minutes * 60)

    def _run_dashboard_search(self):
        query = self.dashboard_search_entry.text().strip()
        if not query:
            return
        try:
            import ast
            import operator
            operators = {
                ast.Add: operator.add, ast.Sub: operator.sub,
                ast.Mult: operator.mul, ast.Div: operator.truediv,
                ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                ast.Pow: operator.pow, ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }
            def evaluate(node):
                if isinstance(node, ast.Expression):
                    return evaluate(node.body)
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                if isinstance(node, ast.BinOp) and type(node.op) in operators:
                    return operators[type(node.op)](evaluate(node.left), evaluate(node.right))
                if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
                    return operators[type(node.op)](evaluate(node.operand))
                raise ValueError
            result = evaluate(ast.parse(query, mode="eval"))
            self.dashboard_search_result.setText(f"{result:g}\n{query}")
        except Exception:
            self.dashboard_search_result.setText(
                f'Search the web for “{query}”  ›')
            import urllib.parse
            self.dashboard_search_result.mousePressEvent = lambda event, q=query: self._launch_uri(
                "https://www.google.com/search?q=" + urllib.parse.quote_plus(q))

    def _compact_size(self):
        if self._displaying_default_page():
            # Wi-Fi icon, centered clock, battery icon and close affordance
            # need a stable canvas; deriving this from a hidden/transitioning
            # widget size hint clips the battery on first reveal.
            return QSize(330, self.COLLAPSED_SIZE.height())
        if self._notification_active:
            return self.NOTIFICATION_SIZE
        if self._headset_active:
            return self.HEADSET_SIZE
        if self._low_power_active:
            return self.LOW_POWER_SIZE
        if self._charging_active:
            return self.CHARGING_SIZE
        if self._timer_active and self._activity_page == "timer":
            return self.TIMER_SIZE
        if self._call_context and not self._media:
            return self.CALL_SIZE
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
        if self._default_page_override:
            return QSize(self.DASHBOARD_EXPANDED_SIZE)
        compact_width = self._compact_size().width()
        return QSize(max(self.EXPANDED_SIZE.width(), compact_width),
                     self.EXPANDED_SIZE.height())

    def _feature_expanded_size(self):
        # Size from the page the user is viewing, not merely from background
        # activity. A swiped-away media session must not lend its player size
        # to the default dashboard page.
        if self._displaying_default_page():
            return QSize(self.DASHBOARD_EXPANDED_SIZE)
        if self._media:
            title = self._media.get("title") or "Now playing"
            artist = self._media.get("artist") or self._media.get("app") or "Media"
            text_width = max(
                self.media_feature_title.fontMetrics().horizontalAdvance(title),
                self.media_feature_artist.fontMetrics().horizontalAdvance(artist),
            )
            # margins + artwork + gaps + waveform; clamp so unusually long
            # metadata stays readable without taking over the screen.
            width = 44 + 60 + 10 + text_width + 12 + 25
            width = max(self.MEDIA_FEATURE_MIN_WIDTH,
                        min(self.MEDIA_FEATURE_MAX_WIDTH, width))
            return QSize(width, self.MEDIA_FEATURE_HEIGHT)
        return QSize(max(self.FEATURE_EXPANDED_SIZE.width(),
                         self._compact_size().width()),
                     self.FEATURE_EXPANDED_SIZE.height())

    def _place_top_center(self):
        if self.is_expanded and self._expanded_view == "feature":
            size = self._feature_expanded_size()
        elif self.is_expanded:
            size = self._expanded_size()
        else:
            size = self._compact_size()
        self.setGeometry(self._target_geometry(size))
        self._apply_rounded_window_mask(size)

    def _animate_surface_to(self, size, duration=None,
                            curve=QEasingCurve.Type.OutCubic,
                            on_finished=None, commit_window=True,
                            start_size=None, fade_title_bar=False,
                            hide_before_final_frame=False):
        """Morph the visible island without resizing its native window per frame."""
        duration = duration or self.COMPACT_TRANSITION_MS
        target = self._target_geometry(size)
        if (self._animation and self._animation_target == target and
                self._animation.state() == QAbstractAnimation.State.Running):
            return self._transition_generation
        if self._animation:
            self._animation.stop()
        self._transition_generation += 1
        generation = self._transition_generation
        start_size = QSize(start_size or self.container.size())
        if start_size.width() < 1 or start_size.height() < 1:
            start_size = QSize(size)

        canvas = QSize(max(start_size.width(), size.width()),
                       max(start_size.height(), size.height()))
        self.main_layout.setAlignment(
            self.container,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.container.setFixedSize(start_size)
        # This native geometry change is visually invisible: the child surface
        # retains its old centered screen rectangle inside the new canvas.
        self.setGeometry(self._target_geometry(canvas))
        self.main_layout.activate()
        # Establish rounded native clipping before the first animation paint.
        # Waiting until the completion callback exposes one square frame.
        self._apply_rounded_window_mask(canvas)

        native_hide_issued = False

        def update_surface(progress):
            nonlocal native_hide_issued
            progress = float(progress)
            width = round(start_size.width() +
                          (size.width() - start_size.width()) * progress)
            height = round(start_size.height() +
                           (size.height() - start_size.height()) * progress)
            self.container.setFixedSize(width, height)
            if fade_title_bar:
                # Finish the content fade in the first 28% of the morph. The
                # remainder is a clean black pill contracting around its
                # centre, rather than controls being relaid out every frame.
                self.title_bar_opacity.setOpacity(
                    max(0.0, 1.0 - (progress / 0.28)))
            if (hide_before_final_frame and progress >= 0.97
                    and not native_hide_issued):
                # Remove the native surface before Windows can paint the last
                # tiny rectangle. The visual morph is already 97% complete,
                # so this avoids an after-image without changing its motion.
                native_hide_issued = True
                self.hide()
            self.main_layout.activate()

        def finish_surface():
            if generation != self._transition_generation:
                return
            if commit_window:
                # Keep the final child surface locked to the exact geometry
                # used by the animation. Releasing its constraints here let a
                # long QLabel size hint expand from the left edge, producing a
                # visibly off-centre third/final frame.
                self.setGeometry(target)
                self.main_layout.setAlignment(
                    self.container,
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
                self.container.setFixedSize(size)
                self.main_layout.activate()
                # setGeometry triggers resizeEvent, which clears the old mask;
                # replace it synchronously before Windows gets another paint.
                self._apply_rounded_window_mask(size)
                QTimer.singleShot(
                    0,
                    lambda: self._reassert_centered_surface(generation, size),
                )
            if on_finished:
                on_finished()

        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setEasingCurve(curve)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.valueChanged.connect(update_surface)
        animation.finished.connect(finish_surface)
        self._animation = animation
        self._animation_target = target
        animation.start()
        return generation

    def _reassert_centered_surface(self, generation, size):
        """Correct any queued Qt size-hint pass after the morph completes."""
        if generation != self._transition_generation or self.isHidden():
            return
        target = self._target_geometry(size)
        self.setGeometry(target)
        self.container.setFixedSize(size)
        self.main_layout.setAlignment(
            self.container,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.main_layout.activate()
        self._apply_rounded_window_mask(size)

    def _apply_rounded_window_mask(self, size):
        """Clip the settled native window to the same curve as its surface."""
        if size.width() <= 0 or size.height() <= 0:
            return
        radius = min(size.height() / 2.0, 28.0)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0.0, 0.0, float(size.width()), float(size.height())),
            radius, radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _animate_to(self, size, duration=None, curve=QEasingCurve.Type.OutCubic):
        return self._animate_surface_to(size, duration, curve)

    def _present_compact(self, size, duration=None):
        """Reveal or morph a compact activity around a fixed screen center."""
        # Compact and expanded surfaces are mutually exclusive.  Keeping this
        # invariant here prevents late media-session updates from stacking the
        # compact header above an already-visible expanded player.
        self.feature_panel.hide()
        self.scroll_area.hide()
        self.input_frame.hide()
        self.title_bar.show()
        self._sync_compact_surface()
        self._visibility_generation += 1
        self._is_hiding = False
        was_hidden = self.isHidden() or self._auto_hidden or self.windowOpacity() < 0.1
        if self._animation:
            self._animation.stop()
        self._reset_container_constraints()
        self._animation_target = None
        self.title_bar_opacity.setOpacity(1.0)
        self.setWindowOpacity(1.0)
        if was_hidden:
            start = QSize(self.MINIMIZE_SIZE)
            self.setGeometry(self._target_geometry(size))
            self.main_layout.setAlignment(
                self.container,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.container.setFixedSize(start)
        else:
            start = QSize(self.container.size())
        self.show()
        self.raise_()
        return self._animate_surface_to(
            size, duration or self.COMPACT_TRANSITION_MS,
            start_size=start)

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
        """Open the Dexget AI conversation explicitly."""
        self._expanded_view = "ai"
        self._collapse_timer.stop()
        self._auto_hidden = False
        self._media_manually_hidden = False
        self.setWindowOpacity(1.0)
        self.is_expanded = True
        self.scroll_opacity.setOpacity(0.0)
        self.input_opacity.setOpacity(0.0)
        self.scroll_area.hide()
        self.input_frame.hide()
        self.feature_panel.hide()
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
        self._feature_collapse_timer.stop()
        if not hasattr(self, "worker") or self.worker.busy.is_set() or not self.confirmation_panel.isHidden():
            return
        if self.input_field.hasFocus() and self.input_field.text():
            return
        if self._assistant_state == "Idle" and self._is_default_activity():
            self.hide_idle_island()
            return
        self.is_expanded = False
        self.title_bar.show()
        self.scroll_area.hide()
        self.input_frame.hide()
        self.feature_panel.hide()
        self.expand_btn.setText("⌄")
        self._animate_to(self._compact_size(), self.COMPACT_TRANSITION_MS)

    def hide_idle_island(self):
        if (self.worker.busy.is_set()
                or self._call_context
                or self._timer_active
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
        if self._call_context and not self._media:
            self._refresh_call_layout()
            return
        self._media_manually_hidden = True
        self._is_hiding = True
        # Require the pointer to leave and re-enter the hot zone. Otherwise a
        # minimize click near the top center can instantly reopen the island.
        self._hot_zone_armed = False
        self.is_expanded = False
        self.feature_panel.hide()
        self.title_bar.show()
        self._auto_hidden = True
        self._hover_leave_at = None
        self.scroll_area.hide()
        self.input_frame.hide()
        self._visibility_generation += 1
        generation = self._visibility_generation
        self.setWindowOpacity(1.0)
        # The native window remains stationary; only the center-aligned black
        # surface contracts. Hide after the surface reaches its pill state.
        self._animate_surface_to(
            self.MINIMIZE_SIZE,
            self.COMPACT_TRANSITION_MS,
            on_finished=self._complete_media_hide,
            commit_window=False,
            start_size=QSize(self.size()),
            fade_title_bar=True,
            hide_before_final_frame=True,
        )
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
        if self._call_context and not self._media:
            self._refresh_call_layout()
            return
        if self._auto_hidden:
            self.hide()
            # Restore while hidden so the next reveal starts fully formed.
            self.title_bar_opacity.setOpacity(1.0)
            self._reset_container_constraints()

    def _reset_container_constraints(self):
        self.container.setMinimumSize(0, 0)
        self.container.setMaximumSize(16777215, 16777215)
        self.main_layout.setAlignment(self.container, Qt.AlignmentFlag(0))

    def reveal_idle_island(self):
        if not self._auto_hidden:
            return
        self._auto_hidden = False
        self._media_manually_hidden = False
        self._hover_leave_at = None
        self._present_compact(self._compact_size())
        if self._call_context and not self._media:
            self._call_hide_timer.start(4500)

    def _check_hot_zone(self):
        if (self._is_hiding or self.is_expanded or self.worker.busy.is_set()
                or self._timer_active
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
            self.expand_feature()

    def _feature_snapshot(self):
        if self._activity_page == "timer" and self._timer_active:
            return ("TIMER", self.timer_remaining_label.text(),
                    "Running" if self._timer_running else "Paused",
                    "Pause" if self._timer_running else "Resume",
                    self.toggle_timer)
        if self._default_page_override:
            return ("DEXGET", "Ready", "Capture the current screen or open Dexget AI.",
                    "Screen Assist", self.start_screen_assist)
        if self._notification_active:
            return ("NOTIFICATION", self.notification_title.text(),
                    self.notification_body.text(), "Dismiss",
                    lambda: self.finish_notification_activity())
        if self._headset_active:
            return ("AUDIO DEVICE", self.headset_name.text(), "Connected",
                    "Audio settings", lambda: self.worker.submit_text(
                        "open sound settings", display_text="Open sound settings"))
        if self._low_power_active:
            return ("BATTERY", "Low power mode", self.low_power_percent.text(),
                    "Battery settings", lambda: self.worker.submit_text(
                        "open battery settings", display_text="Open battery settings"))
        if self._charging_active:
            return ("BATTERY", "Charging", self.charging_percent.text(),
                    "Battery settings", lambda: self.worker.submit_text(
                        "open battery settings", display_text="Open battery settings"))
        if self._timer_active and self._activity_page == "timer":
            return ("TIMER", self.timer_remaining_label.text(),
                    "Running" if self._timer_running else "Paused",
                    "Pause" if self._timer_running else "Resume",
                    self.toggle_timer)
        if self._call_context:
            state = "Microphone muted" if self._call_muted else "Microphone active"
            return ("LIVE CALL", f"{self._call_context} Call", state,
                    "Unmute" if self._call_muted else "Mute", self.toggle_call_mute)
        if self._media:
            title = self._media.get("title", "Now playing")
            artist = self._media.get("artist") or self._media.get("app", "Media")
            return ("NOW PLAYING", title, artist,
                    "Pause" if self._media.get("playing") else "Play",
                    lambda: self.media_worker.control("play_pause"))
        return ("DEXGET", "Ready", "Capture the current screen or open Dexget AI.",
                "Screen Assist", self.start_screen_assist)

    def _prepare_feature_panel(self):
        eyebrow, title, detail, action_text, action = self._feature_snapshot()
        self.feature_eyebrow.setText(eyebrow)
        self.feature_title.setText(title)
        self.feature_detail.setText(detail)
        self.feature_primary_btn.setText(action_text)
        self._feature_action = action
        # Contextual activities stay focused on their own controls.  Dexget AI
        # is intentionally available only from the default compact island.
        self.feature_ai_btn.hide()
        dashboard_mode = self._displaying_default_page()
        media_mode = bool(self._media) and not dashboard_mode
        for widget in (self.feature_eyebrow, self.feature_title,
                       self.feature_detail, self.feature_primary_btn):
            widget.setVisible(not media_mode and not dashboard_mode)
        self.media_feature_widget.setVisible(media_mode)
        self.dashboard_widget.setVisible(dashboard_mode)
        if media_mode:
            self._update_media_feature_panel()
        elif dashboard_mode:
            self._refresh_dashboard_system_info()

    @staticmethod
    def _format_media_time(seconds):
        seconds = max(0, int(seconds or 0))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (f"{hours}:{minutes:02d}:{seconds:02d}" if hours
                else f"{minutes}:{seconds:02d}")

    def _update_media_feature_panel(self):
        if not self._media:
            return
        title = self._media.get("title") or "Now playing"
        artist = self._media.get("artist") or self._media.get("app") or "Media"
        self.media_feature_title.setText(title)
        self.media_feature_title.setToolTip(title)
        self.media_feature_artist.setText(artist)
        self.media_feature_artist.setToolTip(artist)
        playing = bool(self._media.get("playing"))
        self.media_feature_play_btn.set_playing(playing)
        self.media_feature_visualizer.set_playing(playing)
        position = max(0, int(self._media.get("position") or 0))
        duration = max(position, int(self._media.get("duration") or 0))
        if not self.media_seek_slider.isSliderDown():
            self.media_seek_slider.setRange(0, duration)
            self.media_seek_slider.setValue(min(position, duration))
        self.media_elapsed_label.setText(self._format_media_time(position))
        remaining = max(0, duration - position)
        self.media_total_label.setText(
            f"-{self._format_media_time(remaining)}" if duration else "0:00")
        artwork = self._media.get("artwork") or b""
        pixmap = QPixmap()
        if artwork and pixmap.loadFromData(artwork):
            self.media_feature_art.setPixmap(pixmap.scaled(
                self.media_feature_art.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation))
            self.media_feature_art.setText("")
        else:
            self.media_feature_art.setPixmap(QPixmap())
            self.media_feature_art.setText("♪")

    def _keep_feature_open(self):
        if self.is_expanded and self._expanded_view == "feature":
            if self._pointer_inside_island():
                self._feature_collapse_timer.stop()
            else:
                self._feature_collapse_timer.start(1200)

    def _control_expanded_media(self, action):
        if action == "play_pause" and self._media:
            # Give immediate visual feedback while Windows processes the GSMTC
            # command, then reconcile with the next authoritative poll.
            self._media["playing"] = not bool(self._media.get("playing"))
            self._update_media_feature_panel()
        self.media_worker.control(action)
        self._keep_feature_open()

    def _seek_expanded_media(self):
        self.media_worker.control("seek", self.media_seek_slider.value())
        self.media_elapsed_label.setText(
            self._format_media_time(self.media_seek_slider.value()))
        self._keep_feature_open()

    def _run_feature_action(self):
        if self._feature_action:
            self._feature_action()
        self._prepare_feature_panel()

    def _show_feature_content(self):
        if self.is_expanded and self._expanded_view == "feature":
            self.title_bar.setVisible(
                not bool(self._media) and not self._displaying_default_page())
            self.feature_panel.show()

    def expand_feature(self):
        """Expand the activity represented by the compact island."""
        self._collapse_timer.stop()
        self._call_hide_timer.stop()
        self._auto_hidden = False
        self._media_manually_hidden = False
        self.setWindowOpacity(1.0)
        self.is_expanded = True
        self._expanded_view = "feature"
        self.scroll_area.hide()
        self.input_frame.hide()
        self.feature_panel.hide()
        self._prepare_feature_panel()
        # The expanded player is a single unified surface; do not stack the
        # compact media pill above it and duplicate artwork/title/controls.
        self.title_bar.setVisible(
            not bool(self._media) and not self._displaying_default_page())
        generation = self._animate_to(
            self._feature_expanded_size(), self.PANEL_TRANSITION_MS)
        QTimer.singleShot(
            150,
            lambda: self._show_feature_content()
            if (self.is_expanded and self._expanded_view == "feature"
                and generation == self._transition_generation)
            else None,
        )
        # The panel remains open for direct interaction. leaveEvent starts the
        # delayed collapse only after the pointer exits the whole island.
        self._feature_collapse_timer.stop()

    def _mark_input_activity(self, _text=None):
        self._last_input_activity = time.monotonic()
        self._feature_collapse_timer.stop()

    def _pointer_inside_island(self):
        local = self.mapFromGlobal(QCursor.pos())
        return self.rect().contains(local)

    def _input_interaction_active(self):
        if not self.input_field.hasFocus():
            return False
        # Preserve an unsent draft indefinitely. An empty field is protected
        # only while the user is actively typing, so merely retaining keyboard
        # focus cannot pin the island open after the pointer leaves.
        return bool(self.input_field.text()) or (
            time.monotonic() - self._last_input_activity < 1.8)

    def _auto_collapse_expanded(self):
        """Collapse only after interaction has genuinely left the island."""
        if not self.is_expanded:
            return
        if (self._pointer_inside_island() or self._input_interaction_active()
                or self.worker.busy.is_set()
                or not self.confirmation_panel.isHidden()):
            self._feature_collapse_timer.start(900)
            return
        if self._expanded_view == "feature":
            self._auto_collapse_feature()
        else:
            self.collapse_island()

    def _auto_collapse_feature(self):
        """Return a temporary feature surface to its compact live activity."""
        if not self.is_expanded or self._expanded_view != "feature":
            return
        self.is_expanded = False
        self.feature_panel.hide()
        self.title_bar.show()
        self.scroll_area.hide()
        self.input_frame.hide()
        self._animate_to(self._compact_size(), self.COMPACT_TRANSITION_MS)
        if self._call_context and not self._media:
            self._call_hide_timer.start(4500)
        elif not self._media and self._assistant_state == "Idle":
            self._collapse_timer.start(1400)

    def open_ai_panel(self):
        """Switch from a feature surface to the automation conversation."""
        self._feature_collapse_timer.stop()
        self._expanded_view = "ai"
        self.feature_panel.hide()
        self.title_bar.show()
        self.scroll_opacity.setOpacity(0.0)
        self.input_opacity.setOpacity(0.0)
        generation = self._animate_to(self._expanded_size(), self.PANEL_TRANSITION_MS)
        QTimer.singleShot(
            150,
            lambda: self._show_expanded_content()
            if (self.is_expanded and self._expanded_view == "ai"
                and generation == self._transition_generation)
            else None,
        )
        QTimer.singleShot(235, lambda: self.input_field.setFocus()
                          if self.is_expanded and self._expanded_view == "ai"
                          else None)

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
                length = int(ctypes.windll.user32.GetWindowTextLengthW(hwnd))
                buffer = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                self._foreground_title = buffer.value
                pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    import psutil
                    self._foreground_process = psutil.Process(pid.value).name()
                except Exception:
                    self._foreground_process = ""
        except Exception:
            pass

    @staticmethod
    def _active_microphone_clients():
        """Return Windows capability entries currently using the microphone."""
        try:
            import winreg
            root_path = (r"Software\Microsoft\Windows\CurrentVersion"
                         r"\CapabilityAccessManager\ConsentStore\microphone")
            root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, root_path)
        except Exception:
            return set()

        active = set()

        def walk(key, path, depth=0):
            try:
                start = int(winreg.QueryValueEx(key, "LastUsedTimeStart")[0])
                try:
                    stop = int(winreg.QueryValueEx(key, "LastUsedTimeStop")[0])
                except OSError:
                    stop = 0
                # Windows documents LastUsedTimeStop == 0 as the live-use
                # marker. Comparing start/stop timestamps also catches stale
                # history left by apps such as Discord after a call ends.
                if start > 0 and stop == 0:
                    active.add(path.lower())
            except (OSError, TypeError, ValueError):
                pass
            if depth >= 2:
                return
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(key, index)
                    child = winreg.OpenKey(key, name)
                    try:
                        walk(child, f"{path}\\{name}", depth + 1)
                    finally:
                        child.Close()
                    index += 1
                except OSError:
                    break

        try:
            walk(root, "microphone")
        finally:
            root.Close()
        return active

    def _detect_call_application(self):
        clients = " ".join(self._active_microphone_clients())
        title = self._foreground_title.lower()
        process = self._foreground_process.lower()
        candidates = (
            ("Discord", ("discord",)),
            ("WhatsApp", ("whatsapp",)),
            ("Microsoft Teams", ("ms-teams", "msteams", "teams.exe")),
            ("Zoom", ("zoom",)),
            ("Telegram", ("telegram",)),
        )
        active_labels = {
            label for label, tokens in candidates
            if any(token in clients for token in tokens)
        }
        # Discord initializes microphone capture while merely sitting on its
        # Friends page. Require its WebRTC transport to have actually reached
        # RTC_CONNECTED before treating that capture as a call.
        if "Discord" in active_labels and not self._discord_rtc_connected():
            active_labels.discard("Discord")
        # Once a call has been positively identified, keep its controls while
        # the same app retains live microphone access even if the user changes
        # windows. Initial activation is stricter and must match the foreground
        # app, preventing background/tray apps from claiming the island.
        if self._call_context in active_labels:
            return self._call_context
        browser_active = any(token in clients for token in (
            "chrome", "msedge", "brave", "firefox", "opera"))
        if browser_active and ("google meet" in title or "meet -" in title
                               or "meet.google" in title):
            return "Google Meet"
        combined = f"{process} {title}"
        for label, tokens in candidates:
            if label in active_labels and any(
                    token.replace(".exe", "") in combined for token in tokens):
                return label
        return None

    def _discord_rtc_connected(self):
        """Track Discord's current WebRTC connection from its append-only log."""
        try:
            appdata = os.environ.get("APPDATA", "")
            files = glob.glob(os.path.join(
                appdata, "discord", "logs", "discord-webrtc*"))
            # Exclude rotated "discord-last-*" logs; they describe a previous
            # Discord process and otherwise resurrect an old call state.
            files = [path for path in files
                     if not os.path.basename(path).startswith("discord-last-")]
            if not files:
                self._discord_rtc_active = False
                return False
            path = max(files, key=os.path.getmtime)
            size = os.path.getsize(path)
            if path != self._discord_log_path or size < self._discord_log_offset:
                self._discord_log_path = path
                self._discord_log_offset = 0
                self._discord_rtc_active = False
            with open(path, "rb") as stream:
                stream.seek(self._discord_log_offset)
                chunk = stream.read()
                self._discord_log_offset = stream.tell()
            text = chunk.decode("utf-8", errors="ignore").lower()
            for line in text.splitlines():
                if ("=> rtc_connected" in line
                        or "=> connected" in line and "rtc media connection" in line):
                    self._discord_rtc_active = True
                elif any(marker in line for marker in (
                        "=> rtc_disconnected", "=> disconnected",
                        "disconnecting from rtc", "rtc connection destroyed")):
                    self._discord_rtc_active = False
            return self._discord_rtc_active
        except (OSError, ValueError):
            self._discord_rtc_active = False
            return False

    def _check_call_context(self):
        application = self._detect_call_application()
        if application:
            self._call_miss_count = 0
        elif self._call_context:
            # CapabilityAccessManager may briefly drop microphone ownership
            # between Discord/WebRTC capture transitions. Require three
            # consecutive misses before ending an established call activity.
            self._call_miss_count += 1
            if self._call_miss_count < 3:
                return
            self._call_miss_count = 0
        if application == self._call_context:
            if (application and self.call_mute_btn.isHidden() and not self._media
                    and not self._notification_active and not self._charging_active
                    and not self._low_power_active and not self._headset_active):
                self._refresh_call_layout()
            return
        self._call_context = application
        self._refresh_call_layout()

    def _refresh_call_layout(self):
        if self._call_context:
            if (self._media or self._notification_active or self._charging_active
                    or self._low_power_active or self._headset_active):
                return
            self._collapse_timer.stop()
            self._auto_hidden = False
            self._is_hiding = False
            self._media_manually_hidden = False
            self.name_label.setText(f"{self._call_context} Call")
            self.status_label.setText(
                "Microphone muted" if self._call_muted else "Microphone active")
            self.status_dot.setStyleSheet(
                f"color: {'#ff453a' if self._call_muted else '#30d158'}; font-size: 15px;")
            self.call_mute_btn.setText("Unmute" if self._call_muted else "Mute")
            if self._default_page_override:
                self.call_mute_btn.hide()
                self._sync_compact_surface()
                return
            self.call_mute_btn.show()
            self.screen_assist_btn.hide()
            if not self.is_expanded:
                self._present_compact(self.CALL_SIZE)
                self._call_hide_timer.start(4500)
            return
        self._call_hide_timer.stop()
        self.call_mute_btn.hide()
        self.screen_assist_btn.show()
        if not self._media:
            self.name_label.setText("DEXGET")
            self.status_label.setText(self._assistant_subtitle[:70])
            self.status_dot.setStyleSheet("color: #39e58c; font-size: 15px;")
            if not self.is_expanded:
                self._animate_to(self.COLLAPSED_SIZE)
                self._collapse_timer.start(1400)

    def hide_call_island(self):
        """Minimize a call activity while continuing to track the call."""
        if (not self._call_context or self._media or self.is_expanded
                or self.worker.busy.is_set() or self._notification_active
                or self._charging_active or self._low_power_active
                or self._headset_active):
            return
        self._is_hiding = True
        self._auto_hidden = True
        self._hot_zone_armed = False
        self._hover_leave_at = None
        self._visibility_generation += 1
        generation = self._visibility_generation
        self._animate_surface_to(
            self.MINIMIZE_SIZE,
            self.COMPACT_TRANSITION_MS,
            on_finished=self._complete_call_hide,
            commit_window=False,
            start_size=QSize(self.size()),
            fade_title_bar=True,
            hide_before_final_frame=True,
        )
        QTimer.singleShot(
            self.COMPACT_TRANSITION_MS + 80,
            lambda: self._complete_call_hide()
            if (generation == self._visibility_generation and self._auto_hidden)
            else None,
        )

    def _complete_call_hide(self):
        self._is_hiding = False
        if self._auto_hidden and self._call_context and not self._media:
            self.hide()
            self.title_bar_opacity.setOpacity(1.0)
            self._reset_container_constraints()

    @staticmethod
    def _set_input_muted(muted):
        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            device = AudioUtilities.GetMicrophone()
            interface = device.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            endpoint = cast(interface, POINTER(IAudioEndpointVolume))
            endpoint.SetMute(bool(muted), None)
            return True
        except Exception:
            return False

    def toggle_call_mute(self):
        target = not self._call_muted
        if not self._set_input_muted(target):
            self.status_label.setText("Could not change microphone")
            return
        self._call_muted = target
        self._refresh_call_layout()

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
        self.close_btn.hide()
        self.screen_assist_btn.show()
        if not restore:
            return
        if self._media:
            self._set_media_controls_visible(not self._default_page_override)
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
        self.close_btn.hide()
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
        self.close_btn.hide()
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
        self.close_btn.hide()
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
        self._feature_collapse_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_expanded:
            self._feature_collapse_timer.start(1100)
        elif not self._media and not self._call_context:
            self._hover_leave_at = time.monotonic()
        super().leaveEvent(event)

    def _hide_activity_page_widgets(self):
        for widget in (self.charging_label, self.charging_percent,
                       self.battery_indicator, self.low_power_label,
                       self.low_power_percent, self.low_power_battery,
                       self.notification_icon, self.notification_identity,
                       self.earbuds_indicator, self.headset_identity,
                       self.connection_ring, self.timer_status_widget):
            widget.hide()
        self.status_dot.hide()
        self.identity_widget.hide()
        self.call_mute_btn.hide()
        self._set_media_controls_visible(False)

    def _restore_activity_page_widgets(self):
        self.default_status_widget.hide()
        self.screen_assist_btn.hide()
        if self._notification_active:
            self.notification_icon.show()
            self.notification_identity.show()
        elif self._headset_active:
            self.earbuds_indicator.show()
            self.headset_identity.show()
            self.connection_ring.show()
        elif self._low_power_active:
            self.low_power_label.show()
            self.low_power_percent.show()
            self.low_power_battery.show()
        elif self._charging_active:
            self.charging_label.show()
            self.charging_percent.show()
            self.battery_indicator.show()
        elif self._timer_active and self._activity_page == "timer":
            self.timer_status_widget.show()
        elif self._media and self._activity_page == "media":
            self.status_dot.show()
            self.identity_widget.show()
            self._set_media_controls_visible(True)
            self.call_mute_btn.setVisible(bool(self._call_context))
        elif self._call_context:
            self.status_dot.show()
            self.identity_widget.show()
            self.call_mute_btn.show()

    def show_default_page(self, animate=True):
        """Page away from a live activity without stopping the activity."""
        if self._is_default_activity():
            return
        self._default_page_override = True
        self._activity_page = "default"
        self._call_hide_timer.stop()
        self._collapse_timer.stop()
        self._feature_collapse_timer.stop()
        self.is_expanded = False
        self._expanded_view = "feature"
        self.feature_panel.hide()
        self.scroll_area.hide()
        self.input_frame.hide()
        self.title_bar.show()
        self._hide_activity_page_widgets()
        self._sync_compact_surface()
        self._update_default_status()
        size = self._compact_size()
        if animate:
            self._animate_to(size, self.COMPACT_TRANSITION_MS)
        else:
            self._set_activity_geometry(size)

    def show_activity_page(self, animate=True):
        """Show the music/call activity page without stopping other activities."""
        self._default_page_override = False
        self._activity_page = "media" if (self._media or self._call_context) else "timer"
        self.is_expanded = False
        self.feature_panel.hide()
        self.scroll_area.hide()
        self.input_frame.hide()
        self.title_bar.show()
        self._sync_compact_surface()
        self._restore_activity_page_widgets()
        size = self._compact_size()
        if animate:
            self._animate_to(size, self.COMPACT_TRANSITION_MS)
        else:
            self._set_activity_geometry(size)
        if self._call_context and not self._media:
            self._call_hide_timer.start(4500)

    def _cycle_activity_page(self, direction):
        if (self._page_switch_animation and
                self._page_switch_animation.state() == QAbstractAnimation.State.Running):
            return
        now = time.monotonic()
        if now - self._last_page_switch < 0.16:
            return
        self._last_page_switch = now
        pages = ["default"]
        if self._timer_active:
            pages.append("timer")
        if self._media or self._call_context:
            pages.append("media")
        current = self._activity_page if self._activity_page in pages else pages[0]
        index = (pages.index(current) + direction) % len(pages)
        target = pages[index]
        self._animate_activity_page_switch(target, direction)

    def _apply_activity_page(self, target):
        if target == "default":
            self.show_default_page(animate=False)
        elif target == "timer":
            self._default_page_override = False
            self._activity_page = "timer"
            self.is_expanded = False
            self.feature_panel.hide()
            self._sync_compact_surface()
            self._set_activity_geometry(self.TIMER_SIZE)
        else:
            self.show_activity_page(animate=False)

    def _animate_activity_page_switch(self, target, direction):
        """Slide between independent activity pages like Windows desktops."""
        if target == self._activity_page:
            return
        if self._animation:
            self._animation.stop()

        animation = QVariantAnimation(self)
        self._page_switch_animation = animation
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(140)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        swapped = False

        def update(progress):
            nonlocal swapped
            progress = float(progress)
            if progress < 0.5:
                phase = progress / 0.5
                self.setWindowOpacity(max(0.0, 1.0 - phase))
                return
            if not swapped:
                swapped = True
                self.setWindowOpacity(0.0)
                self._apply_activity_page(target)
            phase = (progress - 0.5) / 0.5
            self.setWindowOpacity(min(1.0, phase))

        def finish():
            self.setWindowOpacity(1.0)
            self._place_top_center()
            self.raise_()
            self._page_switch_animation = None
            QTimer.singleShot(0, self._reapply_current_activity_mask)

        animation.valueChanged.connect(update)
        animation.finished.connect(finish)
        animation.start()

    def _reapply_current_activity_mask(self):
        """Restore rounded clipping after a compositor opacity transition."""
        if self.is_expanded:
            return
        size = self._compact_size()
        self.container.setFixedSize(size)
        self.setGeometry(self._target_geometry(size))
        self.main_layout.activate()
        self._apply_rounded_window_mask(size)
        self.update()

    def _set_activity_geometry(self, size):
        """Commit a page switch in one paint, avoiding intermediate flicker."""
        if self._animation:
            self._animation.stop()
        self._transition_generation += 1
        self.setUpdatesEnabled(False)
        self.is_expanded = False
        self.container.setFixedSize(size)
        self.main_layout.activate()
        self.setGeometry(self._target_geometry(size))
        self.main_layout.activate()
        self._apply_rounded_window_mask(size)
        self.setUpdatesEnabled(True)
        self.update()
        self.show()
        QTimer.singleShot(0, self._reapply_current_activity_mask)

    def _begin_page_swipe(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._swipe_start_pos = event.globalPosition().toPoint()

    def _finish_page_swipe(self, event, allow_click=False):
        if event.button() != Qt.MouseButton.LeftButton or self._swipe_start_pos is None:
            return
        start = self._swipe_start_pos
        self._swipe_start_pos = None
        delta_x = event.globalPosition().toPoint().x() - start.x()
        if delta_x <= -55:
            self._cycle_activity_page(-1)
        elif delta_x >= 55:
            self._cycle_activity_page(1)
        elif allow_click and abs(delta_x) < 6:
            self.toggle_island()

    def wheelEvent(self, event):
        horizontal = event.pixelDelta().x() or event.angleDelta().x()
        if horizontal <= -20:
            self._cycle_activity_page(-1)
            event.accept()
            return
        if horizontal >= 20:
            self._cycle_activity_page(1)
            event.accept()
            return
        super().wheelEvent(event)

    def eventFilter(self, watched, event):
        # Child labels/buttons consume mouse events before the title bar gets
        # them. Capture the gesture globally while it starts inside the island
        # so paging works regardless of which part of the compact pill is hit.
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            point = event.globalPosition().toPoint()
            if self.isVisible() and self.geometry().contains(point):
                self._global_swipe_start = point
        elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            start = self._global_swipe_start
            self._global_swipe_start = None
            if start is not None:
                point = event.globalPosition().toPoint()
                delta_x = point.x() - start.x()
                if abs(delta_x) >= 55 and self.isVisible():
                    self._swipe_start_pos = None
                    self._cycle_activity_page(1 if delta_x > 0 else -1)
                    return True
        return super().eventFilter(watched, event)

    def title_mousePressEvent(self, event):
        self._begin_page_swipe(event)

    def title_mouseReleaseEvent(self, event):
        self._finish_page_swipe(event, allow_click=True)

    def feature_mousePressEvent(self, event):
        self._begin_page_swipe(event)

    def feature_mouseReleaseEvent(self, event):
        self._finish_page_swipe(event)

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
        previous_display = (
            self._media.get("title"), self._media.get("artist"),
            self._media.get("app"), self._media.get("playing"),
            self._media.get("artwork"),
        )
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
            # A running timer owns the compact island even if Windows keeps
            # publishing media-session metadata in the background.
            if self._timer_active:
                self._sync_compact_surface()
            if self.is_expanded and self._expanded_view == "feature":
                self._update_media_feature_panel()
                if previous_key != self._last_media_key:
                    self._animate_to(
                        self._feature_expanded_size(), self.PANEL_TRANSITION_MS)
        else:
            self._media_pulse_timer.stop()
            self._last_media_key = None
            self._set_media_controls_visible(False)
            if self._call_context:
                self._refresh_call_layout()
            else:
                self.name_label.setText("DEXGET")
                self.status_label.setText(self._assistant_subtitle[:70])
                self.status_label.setToolTip(self._assistant_subtitle)
            if self._assistant_state == "Idle" and not self._call_context:
                self._collapse_timer.start(1800)
        if self._default_page_override:
            if self._is_default_activity():
                self._default_page_override = False
            self._sync_compact_surface()
            return
        if playing_now and not was_playing:
            if self.is_expanded and self._expanded_view == "feature":
                # A play action inside the expanded player must update it in
                # place, not resurrect the compact header underneath it.
                self.title_bar.hide()
                self.feature_panel.show()
                self._update_media_feature_panel()
                self._keep_feature_open()
            else:
                self.activate_media_island()
        elif (not playing_now and not self._call_context and
              (was_playing or (self._media and not self._auto_hidden
                               and not self._media_manually_hidden))):
            self.hide_media_island()
        current_display = (
            self._media.get("title"), self._media.get("artist"),
            self._media.get("app"), self._media.get("playing"),
            self._media.get("artwork"),
        )
        if (not playing_now and was_playing and self.is_expanded
                and self._expanded_view == "feature"):
            self._auto_collapse_feature()
        elif (not self.is_expanded and not self._media_manually_hidden
              and current_display != previous_display):
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

    @staticmethod
    def _tray_icon():
        """Create a crisp Dexget service icon without an external asset."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#3d4652"), 2.0))
        painter.setBrush(QColor("#0b0e12"))
        painter.drawEllipse(QRectF(4, 4, 56, 56))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#65d8ff"))
        diamond = QPainterPath()
        diamond.moveTo(32, 12)
        diamond.lineTo(38, 26)
        diamond.lineTo(52, 32)
        diamond.lineTo(38, 38)
        diamond.lineTo(32, 52)
        diamond.lineTo(26, 38)
        diamond.lineTo(12, 32)
        diamond.lineTo(26, 26)
        diamond.closeSubpath()
        painter.drawPath(diamond)
        painter.end()
        return QIcon(pixmap)

    def _init_system_tray(self):
        """Keep lifecycle controls in the Windows notification/service area."""
        app = QApplication.instance()
        if app:
            app.setQuitOnLastWindowClosed(False)
            if app.windowIcon().isNull():
                app.setWindowIcon(self._tray_icon())

        self.tray_menu = QMenu()
        self.tray_open_action = QAction("Open Dynamic Island", self)
        self.tray_open_action.triggered.connect(self.activate_island)
        self.tray_menu.addAction(self.tray_open_action)
        self.tray_menu.addSeparator()
        self.tray_force_close_action = QAction("Force close Dexget", self)
        self.tray_force_close_action.triggered.connect(self.force_close)
        self.tray_menu.addAction(self.tray_force_close_action)

        self.tray_icon = QSystemTrayIcon(self._tray_icon(), self)
        self.tray_icon.setToolTip("Dexget — running in the background")
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.activate_island()

    def force_close(self):
        """Terminate the background service from the explicit tray command."""
        if getattr(self, "_force_closing", False):
            return
        self._force_closing = True
        self._closing = True
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        for timer in (self._status_timer, self._call_timer, self._hover_timer,
                      self._feature_collapse_timer, self._countdown_timer):
            timer.stop()
        if hasattr(self, "media_worker") and self.media_worker.isRunning():
            self.media_worker.shutdown()
            self.media_worker.wait(2000)
        if self.screen_assist_worker and self.screen_assist_worker.isRunning():
            self.screen_assist_worker.requestInterruption()
            self.screen_assist_worker.wait(1500)
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.shutdown()
            self.worker.wait(2500)
        self.close()
        app = QApplication.instance()
        if app:
            app.quit()

    def closeEvent(self, event):
        worker_running = hasattr(self, "worker") and self.worker.isRunning()
        if not getattr(self, "_force_closing", False) and worker_running:
            # Ordinary close/minimize requests keep the tray service alive.
            self.hide()
            event.ignore()
            return
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
        # Apply the mask in the same event that makes the native window
        # visible, eliminating the initial rectangular flash.
        self._place_top_center()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Clear the settled mask while morphing so Windows does not rebuild an
        # HRGN on every animation frame. _reassert_centered_surface restores a
        # single rounded native mask after the final geometry is established.
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
