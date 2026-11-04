import os
import subprocess
import time
import atexit
import sys

def main():
    # Launch the PyQt GUI
    try:
        from jarvis.config.environment import load_environment
        load_environment()
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtNetwork import QLocalSocket, QLocalServer
        
        app = QApplication(sys.argv)
        
        # Check for existing instance
        socket = QLocalSocket()
        socket.connectToServer("JarvisWidgetInstance")
        if socket.waitForConnected(500):
            print("[JARVIS COPILOT] Existing instance found")
            print("[JARVIS COPILOT] Redirecting activation")
            socket.write(b"ACTIVATE")
            socket.flush()
            socket.waitForBytesWritten(1000)
            sys.exit(0)

        from jarvis.model_runtime import ensure_model_ready
        runtime = ensure_model_ready(warm=True)
        ollama_process = runtime.process

        def cleanup():
            if ollama_process and ollama_process.poll() is None:
                ollama_process.terminate()
                try:
                    ollama_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    ollama_process.kill()
        atexit.register(cleanup)

        if not runtime.ready:
            appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            log_dir = os.path.join(appdata, 'JarvisAgent')
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, 'startup_log.txt')
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(f"Model startup failed ({runtime.model}): {runtime.error}\n")
            QMessageBox.warning(
                None, "JARVIS model unavailable",
                f"The widget will open, but model tasks are unavailable.\n\n{runtime.error}\n\nLog: {log_path}",
            )
            
        print(f"[JARVIS COPILOT] Provider initialized ({runtime.model}: {'ready' if runtime.ready else 'unavailable'})")
        
        server = QLocalServer()
        server.removeServer("JarvisWidgetInstance")
        server.listen("JarvisWidgetInstance")
        
        import widget
        ex = widget.JarvisWidget()
        
        def new_connection():
            client = server.nextPendingConnection()
            if client.waitForReadyRead(1000):
                msg = client.readAll().data().decode('utf-8')
                if msg == "ACTIVATE":
                    print("[JARVIS COPILOT] Activation received")
                    print("[JARVIS COPILOT] Expanding dynamic island")
                    if ex.isMinimized():
                        ex.showNormal()
                    ex.activate_island()
                    
        server.newConnection.connect(new_connection)
        
        ex.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        log_dir = os.path.join(appdata, 'JarvisAgent')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'crash_log.txt')
        with open(log_path, "w") as f:
            f.write(f"Error starting Jarvis Widget:\n{e}\n\n")
            traceback.print_exc(file=f)
        print(f"Error starting Jarvis Widget: {e}", file=sys.stderr)
        print(f"Crash details were written to {log_path}", file=sys.stderr)
        raise

if __name__ == "__main__":
    main()
