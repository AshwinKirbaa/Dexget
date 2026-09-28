import sys
import os
import subprocess
import time
import urllib.request
import urllib.error
import atexit
import zipfile
import threading

def is_ollama_running():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:11434/", timeout=1)
        return response.getcode() == 200
    except urllib.error.URLError:
        return False

def report_hook(count, block_size, total_size):
    global last_percent
    if total_size > 0:
        percent = int(count * block_size * 100 / total_size)
        if percent > 100:
            percent = 100
        if percent != last_percent:
            sys.stdout.write(f"\rDownloading Ollama: {percent}% ")
            sys.stdout.flush()
            last_percent = percent
    else:
        sys.stdout.write(f"\rDownloading Ollama: {count * block_size} bytes read")
        sys.stdout.flush()

last_percent = -1

def download_and_extract_ollama(target_dir):
    os.makedirs(target_dir, exist_ok=True)
    url = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"
    zip_path = os.path.join(target_dir, "ollama.zip")
    
    print("\nOllama is required but not installed.")
    print("Downloading Ollama (this is a large file, ~1.2GB) ...")
    
    try:
        urllib.request.urlretrieve(url, zip_path, reporthook=report_hook)
        print("\nDownload complete. Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        os.remove(zip_path)
        print("Extraction complete.")
    except Exception as e:
        print(f"\nError downloading Ollama: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        sys.exit(1)

def main():
    print("Initializing Jarvis Environment...")
    ollama_process = None
    
    if not is_ollama_running():
        # Look for ollama in AppData
        appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        jarvis_dir = os.path.join(appdata, 'JarvisAgent')
        ollama_dir = os.path.join(jarvis_dir, 'ollama')
        ollama_exe = os.path.join(ollama_dir, 'ollama.exe')
        
        # We might need to check if it's named 'ollama app.exe' depending on the zip contents
        if not os.path.exists(ollama_exe):
            download_and_extract_ollama(ollama_dir)
            
        if os.path.exists(ollama_exe):
            print("Starting built-in Ollama server...")
            # Hide the console window for ollama.exe on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # Start ollama
            ollama_process = subprocess.Popen(
                [ollama_exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Wait for it to start
            max_retries = 30
            for _ in range(max_retries):
                time.sleep(1)
                if is_ollama_running():
                    print("Ollama started successfully.")
                    break
            else:
                print("Warning: Could not connect to built-in Ollama server. Continuing anyway...")
        else:
            print(f"Warning: Ollama executable not found at {ollama_exe}")

    def cleanup():
        if ollama_process:
            print("\nShutting down Ollama server...")
            ollama_process.terminate()
            try:
                ollama_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                ollama_process.kill()

    atexit.register(cleanup)
    
    # Import main jarvis module and run
    try:
        import start_app
        start_app.main()
    except Exception as e:
        print(f"Error running Jarvis: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
