"""Exercise Windows accessibility against a disposable test app, then close it."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def fixture(directory):
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton
    from PyQt6.QtCore import QTimer
    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("JARVIS disposable automation test")
    layout = QVBoxLayout(window)
    field = QLineEdit()
    field.setAccessibleName("Test name")
    save = QPushButton("Save test")
    save.clicked.connect(lambda: (directory / "result.txt").write_text(field.text(), encoding="utf-8"))
    layout.addWidget(field)
    layout.addWidget(save)
    window.show()
    QTimer.singleShot(300, lambda: (directory / "ready.json").write_text(
        json.dumps({"handle": int(window.winId())}), encoding="utf-8"))
    QTimer.singleShot(60000, app.quit)
    app.exec()


def main():
    from jarvis.tools.desktop import desktop_observe, desktop_type, desktop_click
    with tempfile.TemporaryDirectory(prefix="jarvis_desktop_smoke_") as directory:
        root = Path(directory)
        process = subprocess.Popen(
            [sys.executable, __file__, "--fixture", directory],
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 20
            while not (root / "ready.json").exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Fixture exited before showing its controls.")
                time.sleep(0.1)
            handle = json.loads((root / "ready.json").read_text(encoding="utf-8"))["handle"]
            result = desktop_observe(handle)
            assert result.success, result.error
            edit = next(c for c in result.output["controls"] if c["type"] == "Edit")
            text = "JARVIS Unicode \u03a9"
            result = desktop_type(edit["control_id"], text)
            assert result.success, result.error
            assert not desktop_click(edit["control_id"]).success, "Old snapshots must expire."
            observed = desktop_observe(handle)
            button = next(c for c in observed.output["controls"] if c["name"] == "Save test")
            assert desktop_click(button["control_id"]).success
            deadline = time.monotonic() + 5
            while not (root / "result.txt").exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            assert (root / "result.txt").read_text(encoding="utf-8") == text
            print("PASS: desktop observation, Unicode text entry, click and independent saved-value verification.")
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args()
    fixture(args.fixture) if args.fixture else main()
