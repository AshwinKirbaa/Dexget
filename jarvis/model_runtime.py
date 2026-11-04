"""Start and prepare the local Ollama model used by JARVIS."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelRuntime:
    ready: bool
    model: str
    process: Optional[subprocess.Popen] = None
    error: Optional[str] = None


def _base_url() -> str:
    return os.environ.get("JARVIS_OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def _request(path: str, payload=None, timeout: float = 3.0):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        _base_url() + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def find_ollama_executable() -> Optional[str]:
    configured = os.environ.get("JARVIS_OLLAMA_EXE", "").strip()
    app_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        configured,
        os.path.join(app_dir, "ollama.exe"),
        os.path.join(project_dir, "ollama.exe"),
        os.path.join(local, "Programs", "Ollama", "ollama.exe"),
        os.path.join(local, "JarvisAgent", "ollama", "ollama.exe"),
        shutil.which("ollama") or "",
    ]
    return next((path for path in candidates if path and os.path.isfile(path)), None)


def _hidden_process_args():
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs.update(startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
    return kwargs


def _server_ready() -> bool:
    try:
        _request("/api/tags", timeout=1.5)
        return True
    except Exception:
        return False


def _installed_models() -> set[str]:
    result = _request("/api/tags", timeout=5)
    return {item.get("name", "") for item in result.get("models", [])}


def ensure_model_ready(*, warm: bool = True) -> ModelRuntime:
    """Ensure Ollama is listening and the configured model is available."""
    model = os.environ.get("JARVIS_OLLAMA_MODEL", "gemma3:4b")
    process = None
    try:
        if not _server_ready():
            executable = find_ollama_executable()
            if not executable:
                return ModelRuntime(False, model, error="Ollama is not installed or could not be found.")
            process = subprocess.Popen([executable, "serve"], **_hidden_process_args())
            deadline = time.monotonic() + float(os.environ.get("JARVIS_OLLAMA_START_TIMEOUT", "30"))
            while time.monotonic() < deadline:
                if _server_ready():
                    break
                if process.poll() is not None:
                    return ModelRuntime(False, model, process, "Ollama exited before its server became ready.")
                time.sleep(0.4)
            else:
                return ModelRuntime(False, model, process, "Timed out waiting for the Ollama server.")

        if model not in _installed_models():
            if os.environ.get("JARVIS_AUTO_PULL_MODEL", "true").lower() not in ("1", "true", "yes"):
                return ModelRuntime(False, model, process, f"Model '{model}' is not installed.")
            executable = find_ollama_executable()
            if not executable:
                return ModelRuntime(False, model, process, "Ollama executable is unavailable for model download.")
            pull = subprocess.run(
                [executable, "pull", model],
                timeout=float(os.environ.get("JARVIS_OLLAMA_PULL_TIMEOUT", "1800")),
                **_hidden_process_args(),
            )
            if pull.returncode != 0 or model not in _installed_models():
                return ModelRuntime(False, model, process, f"Could not download model '{model}'.")

        if warm:
            _request(
                "/api/generate",
                {"model": model, "prompt": "", "stream": False, "keep_alive": "10m", "options": {"num_predict": 1}},
                timeout=float(os.environ.get("JARVIS_OLLAMA_WARM_TIMEOUT", "300")),
            )
        return ModelRuntime(True, model, process)
    except Exception as exc:
        return ModelRuntime(False, model, process, str(exc))

