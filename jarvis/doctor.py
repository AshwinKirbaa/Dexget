"""
JARVIS Diagnostic Tool.
Tests connectivity, environment readiness, and critical dependencies.
"""
import sys
import os

def run_diagnostics():
    print("============================================================")
    print("                JARVIS DIAGNOSTICS REPORT                   ")
    print("============================================================")
    
    # 1. SQLite readiness
    try:
        from jarvis.memory.store import _get_conn
        conn = _get_conn()
        conn.close()
        print("[OK] SQLite memory is ready and schemas are initialized.")
    except Exception as e:
        print(f"[FAIL] SQLite memory failed: {e}")

    # 2. LLM Connectivity
    try:
        import requests
        from jarvis.config.models import get_fast_model
        model = get_fast_model()
        url = "http://localhost:11434/api/tags"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            models = [m["name"] for m in res.json().get("models", [])]
            if any(model in m for m in models):
                print(f"[OK] Ollama is running and fast model '{model}' is available.")
            else:
                print(f"[WARN] Ollama running, but fast model '{model}' is NOT found. Try: ollama run {model}")
        else:
            print(f"[FAIL] Ollama API returned status {res.status_code}")
    except Exception as e:
        print(f"[FAIL] Ollama connectivity failed: {e}")

    # 3. Playwright Environment
    try:
        import importlib.util
        if importlib.util.find_spec("playwright"):
            print("[OK] Playwright environment installed.")
        else:
            print("[FAIL] Playwright not found. Try: pip install playwright && playwright install")
    except Exception as e:
        print(f"[FAIL] Playwright check failed: {e}")

    # 4. UFO UIAutomation
    try:
        import uiautomation as auto
        print("[OK] UFO UIAutomation (uiautomation) is installed and available.")
    except ImportError:
        print("[FAIL] uiautomation not found. Try: pip install uiautomation")

    # 5. Audio Devices
    try:
        import pyaudiowpatch as pyaudio
        p = pyaudio.PyAudio()
        info = p.get_default_input_device_info()
        print(f"[OK] Audio input: {info['name']}")
        info_out = p.get_default_output_device_info()
        print(f"[OK] Audio output: {info_out['name']}")
        p.terminate()
    except Exception as e:
        print(f"[WARN] Audio devices check failed (check PyAudioWpatch): {e}")

    print("============================================================")
    print("                      DIAGNOSTICS COMPLETE                  ")
    print("============================================================")

if __name__ == "__main__":
    run_diagnostics()
