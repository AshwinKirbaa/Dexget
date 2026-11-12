"""Dedicated preferences application for the Dexget Dynamic Island."""

import sys
import time

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QMainWindow, QPushButton, QScrollArea, QSlider, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)


DEFAULTS = {
    "features/media": True,
    "features/notifications": True,
    "features/charging": True,
    "features/low_battery": True,
    "features/headset": True,
    "features/timer": True,
    "features/file_shelf": True,
    "features/clipboard": True,
    "features/calendar": True,
    "features/phone_transfer": True,
    "behavior/hover_reveal": True,
    "behavior/auto_collapse": True,
    "behavior/auto_collapse_ms": 1800,
    "behavior/notification_ms": 5200,
    "behavior/always_on_top": True,
    "behavior/start_collapsed": True,
    "sound/enabled": True,
    "sound/notification": "SystemNotification",
    "appearance/theme": "Midnight",
    "appearance/accent": "Sky",
    "appearance/opacity": 100,
    "appearance/corner_radius": 24,
    "appearance/compact_width": 178,
    "appearance/compact_height": 34,
    "appearance/top_offset": 0,
    "appearance/animation_ms": 320,
    "appearance/font_scale": 100,
    "layout/show_clock": True,
    "layout/show_battery": True,
    "layout/show_status_dot": True,
    "layout/show_album_art": True,
    "layout/media_controls": "Previous · Play/Pause · Next",
}


class NotchSettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = QSettings("Dexget", "DynamicIsland")
        self.controls = {}
        self.setWindowTitle("Dexget Notch Settings")
        self.resize(820, 620)
        self.setMinimumSize(680, 520)
        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(14)

        title = QLabel("Dynamic Island")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        subtitle = QLabel(
            "Customize features, behavior, sound, appearance and layout.")
        subtitle.setObjectName("muted")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._features_page(), "Features")
        tabs.addTab(self._behavior_page(), "Behavior")
        tabs.addTab(self._sound_page(), "Sound")
        tabs.addTab(self._appearance_page(), "Appearance")
        tabs.addTab(self._layout_page(), "Layout")
        outer.addWidget(tabs, 1)

        actions = QHBoxLayout()
        reset = QPushButton("Restore defaults")
        reset.clicked.connect(self._reset)
        preview = QPushButton("Preview sound")
        preview.clicked.connect(self._preview_sound)
        apply_button = QPushButton("Apply")
        apply_button.setObjectName("primary")
        apply_button.clicked.connect(self._save)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        actions.addWidget(reset)
        actions.addStretch()
        actions.addWidget(preview)
        actions.addWidget(close)
        actions.addWidget(apply_button)
        outer.addLayout(actions)
        self.setCentralWidget(root)
        self.setStyleSheet(self._stylesheet())

    @staticmethod
    def _stylesheet():
        return """
            QWidget { background:#0c0e12; color:#f5f7fb; font:10pt 'Segoe UI'; }
            QLabel#muted { color:#929aa7; }
            QTabWidget::pane { border:1px solid #282d36; border-radius:14px; top:-1px; }
            QTabBar::tab { background:#12151b; color:#9da5b2; padding:10px 18px; margin-right:4px; border-radius:8px; }
            QTabBar::tab:selected { background:#252b35; color:white; }
            QFrame#card { background:#12151a; border:1px solid #252a32; border-radius:12px; }
            QCheckBox { spacing:10px; padding:7px 2px; }
            QCheckBox::indicator { width:18px; height:18px; }
            QComboBox, QSpinBox { background:#1b1f26; border:1px solid #303641; border-radius:8px; padding:7px 10px; min-width:170px; }
            QSlider::groove:horizontal { height:5px; background:#303640; border-radius:2px; }
            QSlider::handle:horizontal { width:16px; margin:-6px 0; background:#65d8ff; border-radius:8px; }
            QPushButton { background:#1b1f26; border:1px solid #323844; border-radius:9px; padding:8px 16px; }
            QPushButton:hover { background:#252b35; }
            QPushButton#primary { background:#168bd2; border-color:#36a9ef; font-weight:600; }
        """

    def _page(self, intro):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        label = QLabel(intro)
        label.setObjectName("muted")
        label.setWordWrap(True)
        layout.addWidget(label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll, layout

    def _features_page(self):
        page, layout = self._page("Choose which live activities and tools may appear in the notch.")
        options = (
            ("media", "Now playing and media controls"),
            ("notifications", "Laptop notifications"),
            ("charging", "Charging activity"),
            ("low_battery", "Low-battery warning"),
            ("headset", "Headset connection"),
            ("timer", "Timers and focus sessions"),
            ("file_shelf", "Drag-and-drop file shelf"),
            ("clipboard", "Clipboard history"),
            ("calendar", "Calendar and reminders"),
            ("phone_transfer", "Phone pairing and file transfer"),
        )
        for key, text in options:
            control = QCheckBox(text)
            self.controls[f"features/{key}"] = control
            layout.addWidget(control)
        layout.addStretch()
        return page

    def _behavior_page(self):
        page, layout = self._page("Control when the notch appears, expands and hides.")
        form = QFormLayout()
        self._check(form, "behavior/hover_reveal", "Reveal from top-edge hover")
        self._check(form, "behavior/auto_collapse", "Automatically collapse inactive panels")
        self._check(form, "behavior/always_on_top", "Keep notch above other windows")
        self._check(form, "behavior/start_collapsed", "Start in compact mode")
        self._spin(form, "behavior/auto_collapse_ms", "Auto-collapse delay", 400, 15000, " ms")
        self._spin(form, "behavior/notification_ms", "Notification display time", 1500, 30000, " ms")
        layout.addLayout(form)
        layout.addStretch()
        return page

    def _sound_page(self):
        page, layout = self._page("Use the Windows sound theme or silence notch notifications.")
        form = QFormLayout()
        self._check(form, "sound/enabled", "Play notification sounds")
        combo = QComboBox()
        combo.addItems(("SystemNotification", "SystemAsterisk", "SystemExclamation", "SystemHand"))
        self.controls["sound/notification"] = combo
        form.addRow("Notification sound", combo)
        layout.addLayout(form)
        layout.addStretch()
        return page

    def _appearance_page(self):
        page, layout = self._page("Tune the physical notch shape and motion.")
        form = QFormLayout()
        self._combo(form, "appearance/theme", "Theme", ("Midnight", "Black", "Graphite", "Glass"))
        self._combo(form, "appearance/accent", "Accent", ("Sky", "Green", "Orange", "Purple", "White"))
        self._slider(form, "appearance/opacity", "Opacity", 70, 100, "%")
        self._spin(form, "appearance/corner_radius", "Corner radius", 8, 40, " px")
        self._spin(form, "appearance/compact_width", "Compact width", 140, 360, " px")
        self._spin(form, "appearance/compact_height", "Compact height", 28, 64, " px")
        self._spin(form, "appearance/top_offset", "Top offset", 0, 80, " px")
        self._spin(form, "appearance/animation_ms", "Animation duration", 0, 900, " ms")
        self._slider(form, "appearance/font_scale", "Text scale", 80, 140, "%")
        layout.addLayout(form)
        layout.addStretch()
        return page

    def _layout_page(self):
        page, layout = self._page("Select the information and controls used by compact activities.")
        form = QFormLayout()
        self._check(form, "layout/show_clock", "Show clock in idle notch")
        self._check(form, "layout/show_battery", "Show battery in idle notch")
        self._check(form, "layout/show_status_dot", "Show activity status dot")
        self._check(form, "layout/show_album_art", "Show album artwork")
        self._combo(form, "layout/media_controls", "Media control order", (
            "Previous · Play/Pause · Next",
            "Play/Pause · Previous · Next",
            "Previous · Next · Play/Pause",
        ))
        layout.addLayout(form)
        layout.addStretch()
        return page

    def _check(self, form, key, text):
        control = QCheckBox(text)
        self.controls[key] = control
        form.addRow(control)

    def _spin(self, form, key, text, minimum, maximum, suffix=""):
        control = QSpinBox()
        control.setRange(minimum, maximum)
        control.setSuffix(suffix)
        self.controls[key] = control
        form.addRow(text, control)

    def _slider(self, form, key, text, minimum, maximum, suffix):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        value = QLabel()
        value.setFixedWidth(50)
        slider.valueChanged.connect(lambda number, label=value: label.setText(f"{number}{suffix}"))
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value)
        self.controls[key] = slider
        form.addRow(text, row)

    def _combo(self, form, key, text, items):
        control = QComboBox()
        control.addItems(items)
        self.controls[key] = control
        form.addRow(text, control)

    def _load(self):
        for key, default in DEFAULTS.items():
            control = self.controls[key]
            value = self.store.value(f"preferences/{key}", default)
            if isinstance(control, QCheckBox):
                control.setChecked(str(value).lower() not in ("false", "0", "no"))
            elif isinstance(control, (QSpinBox, QSlider)):
                control.setValue(int(value))
            elif isinstance(control, QComboBox):
                index = control.findText(str(value))
                control.setCurrentIndex(max(0, index))

    def _save(self):
        for key, control in self.controls.items():
            if isinstance(control, QCheckBox):
                value = control.isChecked()
            elif isinstance(control, (QSpinBox, QSlider)):
                value = control.value()
            else:
                value = control.currentText()
            self.store.setValue(f"preferences/{key}", value)
        self.store.setValue("preferences/revision", int(time.time() * 1000))
        self.store.sync()

    def _reset(self):
        for key in DEFAULTS:
            self.store.remove(f"preferences/{key}")
        self._load()
        self._save()

    def _preview_sound(self):
        if not self.controls["sound/enabled"].isChecked() or sys.platform != "win32":
            return
        try:
            import winsound
            winsound.PlaySound(
                self.controls["sound/notification"].currentText(),
                winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass


def run_settings_app():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Dexget Notch Settings")
    window = NotchSettingsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_settings_app())
