import os
import subprocess
import time
import urllib.request
import urllib.error
import atexit
import sys

def is_ollama_running():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:11434/", timeout=1)
        return response.getcode() == 200
    except:
        return False

def main():
    ollama_process = None
    
    if not is_ollama_running():
        # Check current directory for ollama.exe
        ollama_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ollama.exe')
        
        # Fallback to launcher.py's AppData location if not in current directory
        if not os.path.exists(ollama_exe):
            appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            ollama_exe = os.path.join(appdata, 'JarvisAgent', 'ollama', 'ollama.exe')
            
        if os.path.exists(ollama_exe):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            ollama_process = subprocess.Popen(
                [ollama_exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Wait for Ollama to be ready
            for _ in range(30):
                time.sleep(0.5)
                if is_ollama_running():
                    break

    def cleanup():
        if ollama_process:
            ollama_process.terminate()
            try:
                ollama_process.wait(timeout=3)
            except:
                ollama_process.kill()

    atexit.register(cleanup)
    
    # Launch the PyQt GUI
    try:
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
            
        print("[JARVIS COPILOT] Provider initialized")
        
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
                    print("[JARVIS COPILOT] Focusing widget")
                    if ex.isMinimized():
                        ex.showNormal()
                    ex.show()
                    ex.raise_()
                    ex.activateWindow()
                    
        server.newConnection.connect(new_connection)
        
        ex.show()
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        import os
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        log_dir = os.path.join(appdata, 'JarvisAgent')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'crash_log.txt')
        with open(log_path, "w") as f:
            f.write(f"Error starting Jarvis Widget:\n{e}\n\n")
            traceback.print_exc(file=f)

if __name__ == "__main__":
    main()
