import sys
import threading
import queue
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QScrollArea, 
                             QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QBrush, QPen

import jarvis_integration

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
        
    def submit_text(self, text):
        if text.lower().strip().rstrip(".!") in ("stop", "cancel", "never mind", "nevermind"):
            self.cancel()
            return True
        with self.submission_lock:
            if self.busy.is_set() or self.shutdown_event.is_set():
                return False
            self.agent.registry.cancel_event.clear()
            self.busy.set()
            self.busy_changed.emit(True)
            self.message_received.emit("User", text)
            self.commands.put(text)
            return True

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
    def __init__(self):
        super().__init__()
        self.initUI()
        
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
        if self.agent.registry.unavailable:
            self.add_message("Jarvis", "Unavailable capabilities: " +
                             "; ".join(f"{name}: {error}" for name, error in self.agent.registry.unavailable.items()))

    def initUI(self):
        # Frameless window and Tool flag so it doesn't show in the taskbar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(400, 400)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Main Container with Glassmorphism ---
        self.container = QFrame()
        self.container.setObjectName("Container")
        self.container.setStyleSheet("""
            #Container {
                background-color: rgba(20, 20, 20, 220);
                border-radius: 15px;
                border: 1px solid rgba(255, 255, 255, 40);
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # --- Title Bar (Draggable) ---
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(40)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        
        self.status_label = QLabel("JARVIS Ready")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.status_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #E0E0E0;")
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
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
        close_btn.clicked.connect(QApplication.quit)
        
        title_layout.addWidget(self.status_label)
        title_layout.addStretch()
        title_layout.addWidget(close_btn)
        
        # Event filters for dragging
        self.title_bar.mousePressEvent = self.title_mousePressEvent
        self.title_bar.mouseMoveEvent = self.title_mouseMoveEvent
        
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
        
        # --- Input Area ---
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 40, 200);
                border-radius: 10px;
                margin: 10px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
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
        container_layout.addWidget(input_frame)
        
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

    def title_mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def title_mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def toggle_mic(self):
        if self.mic_btn.isChecked():
            self.status_label.setText("Mic ON - Listening")
            self.worker.enable_listening(True)
        else:
            self.status_label.setText("Mic OFF")
            self.worker.enable_listening(False)

    def update_state(self, state, subtitle):
        self.status_label.setText(subtitle[:70])
        self.status_label.setToolTip(subtitle)
        if state in ("Idle", "Stopping"):
            self.confirmation_panel.hide()

    def set_busy(self, busy):
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def show_confirmation(self, prompt):
        if self.agent.registry.cancel_event.is_set():
            self.worker.answer_confirmation(False)
            return
        self.confirmation_label.setText(prompt)
        self.confirmation_panel.show()
        self.status_label.setText("Approval needed")

    def resolve_confirmation(self, approved):
        self.confirmation_panel.hide()
        self.worker.answer_confirmation(approved)

    def closeEvent(self, event):
        if self.worker.isRunning():
            self._closing = True
            self.worker.shutdown()
            self.hide()
            event.ignore()
        else:
            event.accept()

    def add_message(self, role, text):
        msg_widget = MessageWidget(role, text)
        self.chat_layout.addWidget(msg_widget)
        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def send_message(self):
        text = self.input_field.text().strip()
        if text:
            if self.worker.submit_text(text):
                self.input_field.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = JarvisWidget()
    ex.show()
    sys.exit(app.exec())
