"""
Windows desktop/system tools.

All tools use direct Windows mechanisms:
  - ctypes.windll for lock, native APIs
  - PowerShell WMI for brightness
  - pycaw (already in project deps) for audio
  - subprocess for power management

Every tool is self-contained and never requires legacy_jarvis.py.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import webbrowser
import time
import datetime
import socket

from jarvis.tools.base import RiskLevel, Tool, ToolResult

IS_WINDOWS = platform.system() == "Windows"

try:
    import psutil
except ImportError:
    psutil = None

APP_ALIASES = {
    "chrome": "chrome.exe",       "google chrome": "chrome.exe",
    "edge":   "msedge.exe",       "firefox": "firefox.exe",
    "vs code": "code.exe",        "code": "code.exe",
    "notepad": "notepad.exe",     "calculator": "calculator.exe",
    "calc":    "calc.exe",        "paint": "mspaint.exe",
    "cmd":     "cmd.exe",         "powershell": "powershell.exe",
    "explorer": "explorer.exe",   "taskmgr": "taskmgr.exe",
}


# ---------------------------------------------------------------------------
# Application management
# ---------------------------------------------------------------------------

def open_application(app_name: str) -> ToolResult:
    try:
        from jarvis.tools.application_resolver import resolve_application, find_installed_application, check_running_process
        from jarvis.tools.browser import open_url
    except ImportError:
        pass
        
    def _log(msg):
        print(f"  {msg}")
        
    target = resolve_application(app_name)
    app_info = find_installed_application(target, logger=_log)
    
    if not app_info["installed"]:
        _log(f"[APPLICATION] {target.title()} desktop application not found")
        fallback = app_info.get("web_fallback")
        if fallback:
            _log(f"[APPLICATION] Using web fallback")
            _log(f"[BROWSER] Opening {target.title()} Web")
            res = open_url(fallback)
            res.observation = f"{target.title()} desktop isn't installed, so I opened {target.title()} Web."
            return res
        else:
            return ToolResult(False, error="not_installed", observation=f"{target.title()} is not installed on this system.")

    executable = app_info["command"]
    try:
        if IS_WINDOWS:
            import jarvis.tools.window_manager as wm
            from jarvis.tools.application_resolver import get_running_pids
            
            pids = get_running_pids(target)
            if app_info["method"] == "running_process" or pids:
                _log(f"[APPLICATION] Found {target.title()} process")
                _log(f"[APPLICATION] Existing instance detected")
                _log(f"[APPLICATION] Searching for {target.title()} window")
                
                activated = False
                for pid in pids:
                    hwnd = wm.WindowManager.get_main_window_for_pid(pid)
                    if hwnd:
                        _log(f"[APPLICATION] Restoring {target.title()} window")
                        _log(f"[APPLICATION] Bringing {target.title()} to foreground")
                        wm.WindowManager.activate_window(hwnd)
                        _log(f"[APPLICATION] Verifying window...")
                        if wm.WindowManager.verify_window_active(hwnd):
                            _log(f"[OK] {target.title()} window activated")
                            activated = True
                            break
                            
                if activated:
                    return ToolResult(True, output=app_name, observation=f"{target.title()} is open.")
                else:
                    _log(f"[APPLICATION] {target.title()} is running, but I couldn't bring its window to the foreground directly. Launching executable to trigger it.")
                    # Fall through to the launch code below by breaking the if block conceptually.
                    pass
            else:
                _log(f"[APPLICATION] {target.title()} is not running")
            
            _log(f"[APPLICATION] Launching {target.title()}")
            
            if executable.endswith('.lnk'):
                subprocess.Popen(executable, shell=True)
            elif "\\" in executable or "/" in executable:
                subprocess.Popen([executable])
            else:
                subprocess.Popen(["powershell", "-Command", f"Start-Process '{executable}'"], shell=True)
                
            _log(f"[APPLICATION] Waiting for application window")
            
            # Wait up to 5 seconds for the window to appear
            for _ in range(10):
                time.sleep(0.5)
                pids = get_running_pids(target)
                if pids:
                    for pid in pids:
                        hwnd = wm.WindowManager.get_main_window_for_pid(pid)
                        if hwnd:
                            _log(f"[APPLICATION] {target.title()} window found")
                            _log(f"[APPLICATION] Activating {target.title()}")
                            wm.WindowManager.activate_window(hwnd)
                            if wm.WindowManager.verify_window_active(hwnd):
                                _log(f"[OK] {target.title()} is open.")
                                return ToolResult(True, output=app_name, observation=f"{target.title()} is open.")
                            else:
                                # Sometimes activation needs a second try
                                time.sleep(0.5)
                                wm.WindowManager.activate_window(hwnd)
                                if wm.WindowManager.verify_window_active(hwnd):
                                    _log(f"[OK] {target.title()} is open.")
                                    return ToolResult(True, output=app_name, observation=f"{target.title()} is open.")
                            
            if check_running_process(target):
                _log(f"[OK] {target.title()} is running.")
                return ToolResult(True, output=app_name, observation=f"{target.title()} is open and running.")
            else:
                return ToolResult(False, error="verify_failed", observation=f"I tried to launch {target.title()}, but couldn't verify it is running.")
        else:
            if shutil.which(executable.replace(".exe", "")) is None:
                return ToolResult(False, error="not_installed", observation=f"Cannot find {executable}")
            subprocess.Popen([executable.replace(".exe", "")])
            time.sleep(1.0)
            return ToolResult(True, output=app_name, observation=f"{target.title()} is open.")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"I found {target.title()}, but I couldn't launch the desktop application.")


def close_application(app_name: str) -> ToolResult:
    try:
        if IS_WINDOWS:
            proc = app_name if app_name.lower().endswith(".exe") else app_name + ".exe"
            result = subprocess.run(["taskkill", "/IM", proc, "/F"], capture_output=True, text=True, timeout=5)
            success = result.returncode == 0
            return ToolResult(success, observation=f"taskkill {proc}: exit={result.returncode}")
        else:
            subprocess.run(["pkill", "-f", app_name], capture_output=True, timeout=5)
            return ToolResult(True, observation=f"Sent pkill for {app_name}")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not close {app_name}: {exc}")


def open_folder(path: str) -> ToolResult:
    if not os.path.exists(path):
        return ToolResult(False, error="not_found", observation=f"Path not found: {path}")
    try:
        if IS_WINDOWS:
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            webbrowser.open(path)
        return ToolResult(True, output=path, observation=f"Opened {path}")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not open {path}: {exc}")


def open_website(url: str) -> ToolResult:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return ToolResult(True, output=url, observation=f"Opened {url} in the default browser")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not open {url}: {exc}")


def get_system_information() -> ToolResult:
    info = {"platform": platform.system(), "release": platform.release(), "version": platform.version(), "machine": platform.machine(), "processor": platform.processor()}
    if psutil is not None:
        info["cpu_percent"] = psutil.cpu_percent(interval=0.3)
        info["cpu_cores"] = psutil.cpu_count(logical=False)
        info["cpu_threads"] = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        info["ram_percent"] = mem.percent
        info["ram_total_gb"] = round(mem.total / (1024 ** 3), 2)
        info["ram_used_gb"] = round(mem.used / (1024 ** 3), 2)
        info["ram_available_gb"] = round(mem.available / (1024 ** 3), 2)
    return ToolResult(True, output=info, observation=f"System info: {info}")

def get_time() -> ToolResult:
    now = datetime.datetime.now()
    return ToolResult(True, output={"time": now.strftime("%I:%M %p")}, observation=f"The current time is {now.strftime('%I:%M %p')}.")

def get_date() -> ToolResult:
    now = datetime.datetime.now()
    return ToolResult(True, output={"date": now.strftime("%A, %B %d, %Y")}, observation=f"Today's date is {now.strftime('%A, %B %d, %Y')}.")

def get_storage_info() -> ToolResult:
    if psutil is None:
        return ToolResult(False, error="psutil_missing", observation="psutil is not installed")
    drives = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            drives.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": usage.percent
            })
        except PermissionError:
            continue
    return ToolResult(True, output=drives, observation=f"Found {len(drives)} drives.")

def get_gpu_info() -> ToolResult:
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="GPU info only supported on Windows")
    try:
        cmd = "Get-WmiObject Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            out = []
            for d in data:
                ram = d.get("AdapterRAM")
                ram_gb = round(ram / (1024**3), 2) if ram else None
                out.append({"name": d.get("Name"), "ram_gb": ram_gb})
            return ToolResult(True, output=out, observation=f"GPU info retrieved successfully.")
        return ToolResult(False, error="wmi_error", observation="GPU information could not be retrieved.")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation="GPU information could not be retrieved.")

def get_battery_info() -> ToolResult:
    if psutil is None:
        return ToolResult(False, error="psutil_missing", observation="psutil is not installed")
    batt = psutil.sensors_battery()
    if not batt:
        return ToolResult(False, error="no_battery", observation="No battery found on this device.")
    return ToolResult(True, output={"percent": batt.percent, "power_plugged": batt.power_plugged, "secsleft": batt.secsleft}, observation=f"Battery at {batt.percent}%")

def get_network_info() -> ToolResult:
    host = socket.gethostname()
    local_ip = socket.gethostbyname(host)
    return ToolResult(True, output={"hostname": host, "local_ip": local_ip}, observation=f"Local IP is {local_ip}")


def get_display_info() -> ToolResult:
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="Display info only supported on Windows")
    try:
        import ctypes
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        monitors = user32.GetSystemMetrics(80) # SM_CMONITORS
        return ToolResult(True, output={"primary_resolution": f"{w}x{h}", "monitor_count": monitors}, observation=f"Resolution: {w}x{h}, Monitors: {monitors}")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation="Could not retrieve display information.")

# ---------------------------------------------------------------------------
# Lock PC
# ---------------------------------------------------------------------------

def lock_pc() -> ToolResult:
    """Lock the Windows workstation immediately."""
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="Lock is only supported on Windows")
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return ToolResult(True, observation="PC locked")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not lock PC: {exc}")


# ---------------------------------------------------------------------------
# Brightness
# ---------------------------------------------------------------------------

def set_brightness(percent: int) -> ToolResult:
    """
    Set screen brightness via WMI (works on most laptops).
    External/desktop monitors typically don't support WMI brightness.
    """
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="Brightness control is only supported on Windows")
    percent = max(0, min(100, int(percent)))
    try:
        cmd = (
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
            f".WmiSetBrightness(1,{percent})"
        )
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return ToolResult(True, observation=f"Brightness set to {percent}%")
        err = result.stderr.strip() or result.stdout.strip()
        return ToolResult(
            False, error=err,
            observation=(
                f"Could not set brightness to {percent}% via WMI. "
                f"Note: external/desktop monitors don't support WMI brightness. "
                f"Error: {err}"
            ),
        )
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Brightness error: {exc}")


def get_brightness() -> ToolResult:
    """Read current screen brightness via WMI."""
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="Brightness reading is only supported on Windows")
    try:
        cmd = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            val = int(result.stdout.strip())
            return ToolResult(True, output=val, observation=f"Current brightness: {val}%")
        return ToolResult(False, error="wmi_unavailable",
                          observation="Could not read brightness (WMI may be unavailable on this monitor)")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Brightness read error: {exc}")

def brightness_up() -> ToolResult:
    res = get_brightness()
    if not res.success: return res
    val = min(100, int(res.output) + 10)
    return set_brightness(val)

def brightness_down() -> ToolResult:
    res = get_brightness()
    if not res.success: return res
    val = max(0, int(res.output) - 10)
    return set_brightness(val)


# ---------------------------------------------------------------------------
# Audio (volume / mute)
# ---------------------------------------------------------------------------

def _get_pycaw_volume():
    """Return (IAudioEndpointVolume proxy, None) or (None, error_str)."""
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return volume, None
    except ImportError:
        return None, "pycaw not installed — run: pip install pycaw"
    except Exception as exc:
        return None, str(exc)


def volume_set(percent: int) -> ToolResult:
    """Set system master volume (0–100)."""
    percent = max(0, min(100, int(percent)))
    vol, err = _get_pycaw_volume()
    if vol is None:
        return ToolResult(False, error=err, observation=f"Could not set volume: {err}")
    try:
        vol.SetMasterVolumeLevelScalar(percent / 100.0, None)
        return ToolResult(True, observation=f"Volume set to {percent}%")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not set volume: {exc}")

def volume_up() -> ToolResult:
    vol, err = _get_pycaw_volume()
    if vol is None: return ToolResult(False, error=err, observation=err)
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new_vol = min(1.0, current + 0.10)
        vol.SetMasterVolumeLevelScalar(new_vol, None)
        return ToolResult(True, observation=f"Volume increased to {int(new_vol*100)}%")
    except Exception as exc: return ToolResult(False, error=str(exc), observation=str(exc))

def volume_down() -> ToolResult:
    vol, err = _get_pycaw_volume()
    if vol is None: return ToolResult(False, error=err, observation=err)
    try:
        current = vol.GetMasterVolumeLevelScalar()
        new_vol = max(0.0, current - 0.10)
        vol.SetMasterVolumeLevelScalar(new_vol, None)
        return ToolResult(True, observation=f"Volume decreased to {int(new_vol*100)}%")
    except Exception as exc: return ToolResult(False, error=str(exc), observation=str(exc))


def mute_audio() -> ToolResult:
    """Mute the system audio."""
    vol, err = _get_pycaw_volume()
    if vol is None:
        return ToolResult(False, error=err, observation=f"Could not mute: {err}")
    try:
        vol.SetMute(1, None)
        return ToolResult(True, observation="Audio muted")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not mute: {exc}")


def unmute_audio() -> ToolResult:
    """Unmute the system audio."""
    vol, err = _get_pycaw_volume()
    if vol is None:
        return ToolResult(False, error=err, observation=f"Could not unmute: {err}")
    try:
        vol.SetMute(0, None)
        return ToolResult(True, observation="Audio unmuted")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not unmute: {exc}")


# ---------------------------------------------------------------------------
# Power management
# ---------------------------------------------------------------------------

def sleep_pc() -> ToolResult:
    """Put the PC to sleep (S3 suspend state)."""
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="Sleep is only supported on Windows")
    try:
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return ToolResult(True, observation="PC going to sleep")
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not sleep: {exc}")


def shutdown_pc() -> ToolResult:
    """Schedule a system shutdown in 30 seconds (run 'shutdown /a' to cancel)."""
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="Shutdown is only supported on Windows")
    try:
        subprocess.run(["shutdown", "/s", "/t", "30"], check=True, capture_output=True, timeout=10)
        return ToolResult(
            True,
            observation="Shutdown scheduled in 30 seconds. Run 'shutdown /a' in a terminal to cancel.",
        )
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not schedule shutdown: {exc}")


def restart_pc() -> ToolResult:
    """Schedule a system restart in 30 seconds (run 'shutdown /a' to cancel)."""
    if not IS_WINDOWS:
        return ToolResult(False, error="not_windows", observation="Restart is only supported on Windows")
    try:
        subprocess.run(["shutdown", "/r", "/t", "30"], check=True, capture_output=True, timeout=10)
        return ToolResult(
            True,
            observation="Restart scheduled in 30 seconds. Run 'shutdown /a' in a terminal to cancel.",
        )
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"Could not schedule restart: {exc}")


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(registry) -> None:
    # --- Application management ---
    registry.register(Tool("win_open_application", "Open a desktop application by name.", {"app_name": {"type": "str", "required": True}}, RiskLevel.LOW, open_application, "windows"))
    registry.register(Tool("win_close_application", "Close/kill a running application by name.", {"app_name": {"type": "str", "required": True}}, RiskLevel.MEDIUM, close_application, "windows"))
    registry.register(Tool("win_open_folder", "Open a folder in File Explorer.", {"path": {"type": "str", "required": True}}, RiskLevel.LOW, open_folder, "windows"))
    registry.register(Tool("win_open_website", "Open a URL in default browser.", {"url": {"type": "str", "required": True}}, RiskLevel.LOW, open_website, "windows"))

    # --- System Information Tools ---
    registry.register(Tool("sys_get_specs", "Get laptop specifications.", {}, RiskLevel.LOW, get_system_information, "system"))
    registry.register(Tool("sys_get_cpu", "Get CPU information.", {}, RiskLevel.LOW, get_system_information, "system"))
    registry.register(Tool("sys_get_ram", "Get RAM information.", {}, RiskLevel.LOW, get_system_information, "system"))
    registry.register(Tool("sys_get_os", "Get OS information.", {}, RiskLevel.LOW, get_system_information, "system"))
    registry.register(Tool("sys_get_time", "Get system time.", {}, RiskLevel.LOW, get_time, "system"))
    registry.register(Tool("sys_get_date", "Get system date.", {}, RiskLevel.LOW, get_date, "system"))
    registry.register(Tool("sys_get_storage", "Get storage capacity info.", {}, RiskLevel.LOW, get_storage_info, "system"))
    registry.register(Tool("sys_get_gpu", "Get GPU information.", {}, RiskLevel.LOW, get_gpu_info, "system"))
    registry.register(Tool("sys_get_battery", "Get battery information.", {}, RiskLevel.LOW, get_battery_info, "system"))
    registry.register(Tool("sys_get_network", "Get network information.", {}, RiskLevel.LOW, get_network_info, "system"))
    registry.register(Tool("sys_get_display", "Get display/screen info.", {}, RiskLevel.LOW, get_display_info, "system"))
    registry.register(Tool("win_system_info", "Get current CPU/RAM/platform info.", {}, RiskLevel.LOW, get_system_information, "windows"))

    # --- Lock ---
    registry.register(Tool(
        name="win_lock_pc",
        description="Lock the Windows workstation immediately (same as Win+L).",
        parameters={},
        risk_level=RiskLevel.LOW, func=lock_pc, category="windows"))

    # --- Brightness ---
    registry.register(Tool(
        name="win_set_brightness",
        description="Set screen brightness (0-100). Works on laptops via WMI; external monitors may not be supported.",
        parameters={"percent": {"type": "int", "required": True, "description": "Brightness level 0-100"}},
        risk_level=RiskLevel.LOW, func=set_brightness, category="windows"))

    registry.register(Tool(
        name="win_get_brightness",
        description="Get the current screen brightness percentage.",
        parameters={},
        risk_level=RiskLevel.LOW, func=get_brightness, category="windows"))

    registry.register(Tool(
        name="win_brightness_up",
        description="Increase screen brightness by 10%.",
        parameters={},
        risk_level=RiskLevel.LOW, func=brightness_up, category="windows"))

    registry.register(Tool(
        name="win_brightness_down",
        description="Decrease screen brightness by 10%.",
        parameters={},
        risk_level=RiskLevel.LOW, func=brightness_down, category="windows"))

    # --- Audio ---
    registry.register(Tool(
        name="win_volume_set",
        description="Set the system master volume (0-100). Requires pycaw.",
        parameters={"percent": {"type": "int", "required": True, "description": "Volume level 0-100"}},
        risk_level=RiskLevel.LOW, func=volume_set, category="windows"))

    registry.register(Tool(
        name="win_mute",
        description="Mute the system audio output. Requires pycaw.",
        parameters={},
        risk_level=RiskLevel.LOW, func=mute_audio, category="windows"))

    registry.register(Tool(
        name="win_unmute",
        description="Unmute the system audio output. Requires pycaw.",
        parameters={},
        risk_level=RiskLevel.LOW, func=unmute_audio, category="windows"))

    registry.register(Tool(
        name="win_volume_up",
        description="Increase system volume by 10%.",
        parameters={},
        risk_level=RiskLevel.LOW, func=volume_up, category="windows"))
        
    registry.register(Tool(
        name="win_volume_down",
        description="Decrease system volume by 10%.",
        parameters={},
        risk_level=RiskLevel.LOW, func=volume_down, category="windows"))

    # --- Power ---
    registry.register(Tool(
        name="win_sleep",
        description="Put the PC into sleep/suspend mode.",
        parameters={},
        risk_level=RiskLevel.MEDIUM, func=sleep_pc, category="windows"))

    registry.register(Tool(
        name="win_shutdown",
        description="Schedule a system shutdown in 30 seconds. Run 'shutdown /a' to cancel.",
        parameters={},
        risk_level=RiskLevel.DESTRUCTIVE, func=shutdown_pc, category="windows"))

    registry.register(Tool(
        name="win_restart",
        description="Schedule a system restart in 30 seconds. Run 'shutdown /a' to cancel.",
        parameters={},
        risk_level=RiskLevel.HIGH, func=restart_pc, category="windows"))
