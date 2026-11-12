import os
import sys

def main():
    # Launch the PyQt GUI
    try:
        from jarvis.config.environment import load_environment
        load_environment()
        if "--settings" in sys.argv:
            from notch_settings import run_settings_app
            raise SystemExit(run_settings_app())
        from PyQt6.QtWidgets import QApplication
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

        # Ollama is intentionally not started here. Model-backed questions start
        # it on demand and unload/terminate it immediately after the response.
        print("[JARVIS COPILOT] Provider initialized (Ollama: on demand)")
        
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
