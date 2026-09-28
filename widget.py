import sys
import threading
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QScrollArea, 
                             QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QBrush, QPen

import jarvis_integration
from jarvis.voice.voice_manager import VoiceManager, clean_response

class JarvisWorker(QThread):
    state_changed = pyqtSignal(str, str) # state_name, subtitle
    message_received = pyqtSignal(str, str) # role, text
    
    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.vm = None
        self.listening_enabled = False
        
    def run(self):
        class WidgetVoiceManager(VoiceManager):
            def __init__(self, agent, worker_ref):
                super().__init__(agent)
                self.worker_ref = worker_ref

            def process_voice_command(self, text: str):
                from jarvis_integration import handle_command
                from jarvis.voice.wake_word import strip_wake_word
                
                # If we are in "Mic On" mode, we might not strictly require a wake word
                # But let's check if they used it. If not, we just treat the text as direct input
                # since the mic was explicitly turned on.
                command = strip_wake_word(text)
                if command is None:
                    command = text # If no wake word, just use the transcribed text
                    
                if not command.strip():
                    return
                    
                self.worker_ref.message_received.emit("User", command)
                self.worker_ref.state_changed.emit("Processing", "Thinking...")
                
                if command.lower() in ["stop", "cancel", "never mind", "nevermind"]:
                    self.tts.stop()
                    self.worker_ref.state_changed.emit("Speaking", "Stopped.")
                    self.worker_ref.message_received.emit("Jarvis", "Stopped.")
                    self.tts.speak("Stopped.")
                    return

                result = handle_command(self.agent, command)
                
                if result and result.text:
                    spoken_text = clean_response(result.text)
                    if spoken_text:
                        self.worker_ref.message_received.emit("Jarvis", spoken_text)
                        self.worker_ref.state_changed.emit("Speaking", "Speaking...")
                        self.tts.speak(spoken_text)

            def run_continuous(self):
                while True:
                    if not self.worker_ref.listening_enabled:
                        import time
                        time.sleep(0.5)
                        continue
                        
                    try:
                        self.worker_ref.state_changed.emit("Listening", "Listening...")
                        res = self.stt.listen()
                        if not self.worker_ref.listening_enabled:
                            continue
                            
                        if not res:
                            continue
                        if "error" in res:
                            continue
                            
                        text = res.get("text", "")
                        if text:
                            self.process_voice_command(text)
                    except Exception as e:
                        print(f"Voice Exception: {e}")
                        break

        self.vm = WidgetVoiceManager(self.agent, self)
        self.vm.run_continuous()
        
    def submit_text(self, text):
        def worker_task():
            self.message_received.emit("User", text)
            self.state_changed.emit("Processing", "Thinking...")
            
            from jarvis_integration import handle_command
            result = handle_command(self.agent, text)
            
            if result and result.text:
                spoken_text = clean_response(result.text)
                if spoken_text:
                    self.message_received.emit("Jarvis", spoken_text)
                    self.state_changed.emit("Speaking", "Speaking...")
                    self.vm.tts.speak(spoken_text)
            self.state_changed.emit("Idle", "Ready")
            
        threading.Thread(target=worker_task, daemon=True).start()

class MessageWidget(QWidget):
    def __init__(self, role, text):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 5)
        
        self.label = QLabel(text)
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
        
        # Start Jarvis
        def on_progress(msg: str):
            pass 
            
        self.agent = jarvis_integration.build_agent(on_progress=on_progress)
        self.worker = JarvisWorker(self.agent)
        self.worker.state_changed.connect(self.update_state)
        self.worker.message_received.connect(self.add_message)
        self.worker.start()

    def initUI(self):
        # Frameless window and Tool flag so it doesn't show in the taskbar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
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
        
        input_layout.addWidget(self.mic_btn)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        
        # Assemble
        container_layout.addWidget(self.title_bar)
        container_layout.addWidget(self.scroll_area)
        container_layout.addWidget(input_frame)
        
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
        
        self.add_message("Jarvis", "Hello! I am ready. You can type to me, or click the 🎤 to speak. I will respond with voice either way.")

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
            self.worker.listening_enabled = True
        else:
            self.status_label.setText("Mic OFF")
            self.worker.listening_enabled = False

    def update_state(self, state, subtitle):
        if state == "Listening" and self.worker.listening_enabled:
            self.status_label.setText("Listening...")
        elif state == "Processing":
            self.status_label.setText("Thinking...")
        elif state == "Speaking":
            self.status_label.setText("Speaking...")
        else:
            self.status_label.setText("Ready")

    def add_message(self, role, text):
        msg_widget = MessageWidget(role, text)
        self.chat_layout.addWidget(msg_widget)
        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def send_message(self):
        text = self.input_field.text().strip()
        if text:
            self.input_field.clear()
            self.worker.submit_text(text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = JarvisWidget()
    ex.show()
    sys.exit(app.exec())
