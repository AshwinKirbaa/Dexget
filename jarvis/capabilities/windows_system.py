import subprocess
import re
import os
import ctypes
import ctypes.wintypes as wintypes
try:
    import uiautomation as auto
except ImportError:
    auto = None
import time
import threading
from typing import Dict, Any, List, Optional
from jarvis.tools.base import Tool, ToolResult

# ==========================================
# Helpers
# ==========================================

def run_ps(cmd: str) -> str:
    """Run a PowerShell command and return its output."""
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=10)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def run_cmd(args: List[str]) -> str:
    """Run a standard cmd command."""
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

DESKTOP_ALL_ACCESS = 0x01FF

def run_in_desktop_thread(fn, *args, **kwargs):
    """Run fn in a dedicated thread attached to 'Default' desktop station."""
    res_box = [None, None]
    def worker():
        try:
            try:
                user32 = ctypes.windll.user32
                h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
                if h_default:
                    user32.SetThreadDesktop(h_default)
            except Exception:
                pass
            res_box[0] = fn(*args, **kwargs)
        except Exception as e:
            res_box[1] = e

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    if res_box[1]:
        raise res_box[1]
    return res_box[0]

def ensure_desktop():
    """Ensure thread desktop is set to interactive 'Default' station."""
    try:
        user32 = ctypes.windll.user32
        h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
        if h_default:
            user32.SetThreadDesktop(h_default)
    except Exception:
        pass

def open_quick_settings():
    """Opens Quick Settings via Win+A."""
    ensure_desktop()
    if auto:
        auto.SendKeys('{Win}a')
    else:
        import pyautogui
        pyautogui.hotkey('win', 'a')
    time.sleep(1.0)

def close_quick_settings():
    """Closes Quick Settings via Win+A."""
    ensure_desktop()
    if auto:
        auto.SendKeys('{Win}a')
    else:
        import pyautogui
        pyautogui.hotkey('win', 'a')

QUICK_ACTION_MAP = {
    "wifi": "Microsoft.QuickAction.WiFi",
    "wi-fi": "Microsoft.QuickAction.WiFi",
    "bluetooth": "Microsoft.QuickAction.Bluetooth",
    "airplane mode": "Microsoft.QuickAction.AirplaneMode",
    "airplane": "Microsoft.QuickAction.AirplaneMode",
    "energy saver": "Microsoft.QuickAction.EnergySaverAcOnly",
    "battery saver": "Microsoft.QuickAction.EnergySaverAcOnly",
    "night light": "Microsoft.QuickAction.BlueLightReduction",
    "accessibility": "Microsoft.QuickAction.Accessibility",
    "mobile hotspot": "Microsoft.QuickAction.MobileHotspot",
    "nearby sharing": "Microsoft.QuickAction.NearShare",
    "cast": "Microsoft.QuickAction.Cast",
    "project": "Microsoft.QuickAction.ProjectL2",
    "sound output": "VolumeL2Button",
}

def get_qs_window():
    if not auto:
        return None
    root = auto.GetRootControl()
    qs = root.PaneControl(ClassName='ControlCenterWindow')
    if qs.Exists(2.0, 0.2):
        return qs
    for child in root.GetChildren():
        if 'controlcenter' in child.ClassName.lower() or child.Name == 'Quick settings':
            return child
    return root

def find_quick_setting_control(btn_name: str, auto_id_override: str = None, is_manage_btn: bool = False):
    if not auto:
        return None
    target_id = auto_id_override or QUICK_ACTION_MAP.get(btn_name.lower())
    target_name_lower = btn_name.lower()
    
    qs_container = get_qs_window()
    if not qs_container:
        return None
        
    for control, depth in auto.WalkControl(qs_container, maxDepth=10):
        try:
            c_id = control.AutomationId or ""
            c_name = control.Name or ""
            c_type = control.ControlTypeName
            
            if is_manage_btn:
                if c_id == "SplitL2Button" and target_name_lower in c_name.lower():
                    return control
                if "manage" in c_name.lower() and target_name_lower in c_name.lower():
                    return control
            else:
                if target_id and target_id.lower() == c_id.lower():
                    return control
                if c_name and target_name_lower == c_name.lower() and c_id != "SplitL2Button":
                    if c_type in ["ButtonControl", "CheckBoxControl", "ToggleControl"]:
                        return control
        except Exception:
            pass
    return None


# ==========================================
# Wi-Fi
# ==========================================

def wifi_get_status() -> ToolResult:
    out = run_cmd(["netsh", "wlan", "show", "interfaces"])
    if "Software Off" in out:
        return ToolResult(True, output="disabled (software radio off)", observation="disabled (software radio off)")
    if "State" in out:
        m = re.search(r"State\s*:\s*(.*)", out)
        if m:
            state = m.group(1).strip()
            if state == "connected":
                ssid_m = re.search(r"SSID\s*:\s*(.*)", out)
                ssid = ssid_m.group(1).strip() if ssid_m else "Unknown SSID"
                obs = f"enabled (connected to {ssid})"
                return ToolResult(True, output=obs, observation=obs)
            obs = f"enabled ({state})"
            return ToolResult(True, output=obs, observation=obs)
    if "The Wireless AutoConfig Service" in out or "There is no wireless interface" in out:
        return ToolResult(True, output="disabled", observation="disabled")
    
    qs_st = get_quick_setting_toggle_state("Wi-Fi")
    if qs_st == "ON":
        return ToolResult(True, output="enabled (disconnected)", observation="enabled (disconnected)")
    elif qs_st == "OFF":
        return ToolResult(True, output="disabled", observation="disabled")
        
    return ToolResult(False, error="UNKNOWN_WIFI_STATE", observation="unknown")

def wifi_enable() -> ToolResult:
    # 1. Enable network adapter if disabled
    run_ps("Enable-NetAdapter -Name 'Wi-Fi' -Confirm:$false")
    time.sleep(1)
    
    # 2. Explicitly set Quick Settings Wi-Fi radio toggle to ON
    set_quick_setting_toggle("Wi-Fi", True)
    time.sleep(2)
    
    st = wifi_get_status()
    if st.success and "disabled" not in st.output and "software radio off" not in st.output:
        return ToolResult(True, output=True, observation="Wi-Fi enabled.")
        
    return ToolResult(False, error="UNVERIFIED", observation="Attempted to enable Wi-Fi, but state remains unverified.")

def wifi_disable() -> ToolResult:
    # 1. Turn off software radio via Quick Settings
    set_quick_setting_toggle("Wi-Fi", False)
    time.sleep(2)
    
    st = wifi_get_status()
    if st.success and ("disabled" in st.output or "software radio off" in st.output):
        return ToolResult(True, output=True, observation="Wi-Fi disabled.")
        
    run_ps("Disable-NetAdapter -Name 'Wi-Fi' -Confirm:$false")
    time.sleep(2)
    return ToolResult(True, output=True, observation="Wi-Fi disabled.")

def wifi_list_networks() -> ToolResult:
    out = run_cmd(["netsh", "wlan", "show", "networks"])
    networks = []
    for line in out.split('\n'):
        if line.strip().startswith("SSID"):
            parts = line.split(":")
            if len(parts) > 1:
                ssid = parts[1].strip()
                if ssid: networks.append(ssid)
    obs = "Networks:\n" + "\n".join(networks)
    return ToolResult(True, output=networks, observation=obs)

def wifi_connect(ssid: str) -> ToolResult:
    run_cmd(["netsh", "wlan", "connect", f"name={ssid}"])
    time.sleep(4)
    st = wifi_get_status()
    if st.success and ssid in st.output:
        return ToolResult(True, output=True, observation=f"Connected to {ssid}.")
    return ToolResult(False, error="CONNECTION_FAILED", observation=f"Failed to verify connection to {ssid}.")

# ==========================================
# Bluetooth
# ==========================================

def bluetooth_get_status() -> ToolResult:
    # Reliable Windows Radio State check using Microsoft Bluetooth Enumerator presence.
    # When Bluetooth Radio is turned OFF in Quick Settings, the Enumerator software device is removed (Present: False).
    cmd = "Get-PnpDevice -Class Bluetooth | Where-Object { $_.FriendlyName -eq 'Microsoft Bluetooth Enumerator' -or $_.FriendlyName -eq 'Microsoft Bluetooth LE Enumerator' } | Select-Object -ExpandProperty Present"
    out = run_ps(cmd).strip().lower()
    
    if "true" in out:
        state = "ON"
    elif "false" in out:
        state = "OFF"
    else:
        srv = run_ps("Get-Service bthserv | Select-Object -ExpandProperty Status").strip()
        if srv == "Running": state = "ON"
        else: state = "OFF"
    return ToolResult(True, output=state, observation=state)

def _click_quick_setting_button_worker(btn_name: str) -> bool:
    if not auto:
        return False
    with auto.UIAutomationInitializerInThread():
        open_quick_settings()
        btn = find_quick_setting_control(btn_name)
        success = False
        if btn:
            try:
                pat = btn.GetTogglePattern()
                if pat:
                    pat.Toggle()
                    time.sleep(1)
                    success = True
                else:
                    inv = btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                        time.sleep(1)
                        success = True
            except Exception:
                pass
        close_quick_settings()
        return success

def _click_quick_setting_button(btn_name: str) -> bool:
    return run_in_desktop_thread(_click_quick_setting_button_worker, btn_name)

def bluetooth_enable() -> ToolResult:
    if bluetooth_get_status().output == "ON":
        return ToolResult(True, output=True, observation="Bluetooth is already ON.")
        
    _click_quick_setting_button("Bluetooth")
    time.sleep(3)
    
    if bluetooth_get_status().output == "ON":
        return ToolResult(True, output=True, observation="Bluetooth enabled.")
    return ToolResult(False, error="BLUETOOTH_RADIO_STATE_UNVERIFIED", observation="Attempted to enable Bluetooth, but radio state remains OFF/UNKNOWN.")

def bluetooth_disable() -> ToolResult:
    if bluetooth_get_status().output == "OFF":
        return ToolResult(True, output=True, observation="Bluetooth is already OFF.")
        
    _click_quick_setting_button("Bluetooth")
    time.sleep(3)
    
    if bluetooth_get_status().output == "OFF":
        return ToolResult(True, output=True, observation="Bluetooth disabled.")
    return ToolResult(False, error="BLUETOOTH_RADIO_STATE_UNVERIFIED", observation="Attempted to disable Bluetooth, but radio state remains ON/UNKNOWN.")

def bluetooth_toggle() -> ToolResult:
    st = bluetooth_get_status()
    if st.output == "ON": return bluetooth_disable()
    else: return bluetooth_enable()

def bluetooth_discover_devices() -> ToolResult:
    # 1. Get audio devices and their states from PyCaw
    import warnings
    from pycaw.pycaw import AudioUtilities
    import re
    audio_states = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            devices = AudioUtilities.GetAllDevices()
            for d in devices:
                if d.FriendlyName:
                    st = str(d.state)
                    state_str = "Paired"
                    if "Active" in st: state_str = "Connected"
                    elif "Unplugged" in st: state_str = "Disconnected"
                    elif "NotPresent" in st: state_str = "Not Present"
                    
                    m = re.match(r".*\((.*?)\)", d.FriendlyName)
                    if m:
                        name = m.group(1)
                        if "Qualcomm" not in name and "Hands-Free" not in name and "Adapter" not in name:
                            audio_states[name] = state_str
        except: pass

    # 2. Get all paired Bluetooth devices from PnP
    out = run_ps("Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName | ConvertTo-Json -Compress")
    import json
    devices = []
    try:
        data = json.loads(out)
        if isinstance(data, dict): data = [data]
        ignored = ["service", "transport", "enumerator", "profile", "adapter", "protocol", "generic", "fastconnect"]
        for d in data:
            fname = d.get("FriendlyName", "")
            if not fname: continue
            if any(ign in fname.lower() for ign in ignored): continue
            devices.append(fname)
    except: pass
    
    devices = list(set(devices))
    obs = "Bluetooth devices:\n"
    res_list = []
    for d in devices:
        st = audio_states.get(d, "Paired")
        res_list.append({"name": d, "status": st})
        obs += f"- {d}\n  Status: {st}\n"
        
    return ToolResult(True, output=res_list, observation=obs)

def _bluetooth_manage_ui_worker(device_name: str, connect: bool) -> ToolResult:
    if not auto:
        return ToolResult(False, error="UI_AUTOMATION_UNAVAILABLE", observation="UI Automation unavailable.")
    with auto.UIAutomationInitializerInThread():
        open_quick_settings()
        manage_btn = find_quick_setting_control("Bluetooth", is_manage_btn=True)
        if not manage_btn:
            close_quick_settings()
            return ToolResult(False, error="UI_AUTOMATION_FAILED", observation="Could not open Quick Settings Bluetooth menu.")
            
        try:
            inv = manage_btn.GetInvokePattern()
            if inv: inv.Invoke()
            else: manage_btn.Click()
        except:
            manage_btn.Click()
        time.sleep(1.5)
        
        qs_win = get_qs_window()
        target = None
        if qs_win:
            for control, depth in auto.WalkControl(qs_win, maxDepth=8):
                if control.ControlTypeName == "ListItemControl" and device_name.lower() in (control.Name or "").lower():
                    target = control
                    break
                
        if not target:
            close_quick_settings()
            return ToolResult(False, error="DEVICE_NOT_FOUND", observation=f"I couldn't find {device_name}.")
            
        try:
            inv = target.GetInvokePattern()
            if inv: inv.Invoke()
            else: target.Click()
        except:
            target.Click()
        time.sleep(4 if connect else 2)
        close_quick_settings()
    
    # Verify
    disc = bluetooth_discover_devices()
    for d in disc.output:
        if device_name.lower() in d['name'].lower():
            if connect:
                if d['status'] == 'Connected':
                    return ToolResult(True, output=True, observation=f"Bluetooth is on and {d['name']} is connected.")
                else:
                    return ToolResult(False, error="CONNECTION_FAILED", observation=f"I found {d['name']}, but Windows couldn't connect to it.")
            else:
                if d['status'] == 'Connected':
                    return ToolResult(False, error="DISCONNECT_FAILED", observation=f"Failed to disconnect {d['name']}.")
                else:
                    return ToolResult(True, output=True, observation=f"{d['name']} disconnected.")
                    
    return ToolResult(True, output=True, observation=f"{device_name} {'connected' if connect else 'disconnected'}.")

def _bluetooth_manage_ui(device_name: str, connect: bool) -> ToolResult:
    return run_in_desktop_thread(_bluetooth_manage_ui_worker, device_name, connect)

def bluetooth_connect(device_name: str) -> ToolResult:
    st = bluetooth_get_status()
    if st.output != "ON":
        bluetooth_enable()
        time.sleep(2)
    return _bluetooth_manage_ui(device_name, connect=True)

def bluetooth_disconnect(device_name: str) -> ToolResult:
    return _bluetooth_manage_ui(device_name, connect=False)

def bluetooth_get_connected_devices() -> ToolResult:
    res = bluetooth_discover_devices()
    if not res.success: return res
    connected = [d for d in res.output if d['status'] == 'Connected']
    if not connected:
        return ToolResult(True, output=[], observation="No Bluetooth devices are currently connected.")
    
    obs = "Connected Bluetooth devices:\n"
    for c in connected: obs += f"- {c['name']}\n"
    return ToolResult(True, output=connected, observation=obs)

# ==========================================
# Airplane Mode
# ==========================================

def _get_quick_setting_toggle_state_worker(btn_name: str) -> str:
    if not auto:
        return "UNKNOWN"
    with auto.UIAutomationInitializerInThread():
        open_quick_settings()
        btn = find_quick_setting_control(btn_name)
        state = "UNKNOWN"
        if btn:
            try:
                pat = btn.GetTogglePattern()
                if pat:
                    state = "ON" if pat.ToggleState == 1 else "OFF"
            except Exception:
                pass
            if state == "UNKNOWN":
                if "On" in btn.Name: state = "ON"
                elif "Off" in btn.Name: state = "OFF"
        close_quick_settings()
        return state

def get_quick_setting_toggle_state(btn_name: str) -> str:
    return run_in_desktop_thread(_get_quick_setting_toggle_state_worker, btn_name)

def _set_quick_setting_toggle_worker(btn_name: str, target_state: bool) -> bool:
    if not auto:
        return False
    with auto.UIAutomationInitializerInThread():
        open_quick_settings()
        btn = find_quick_setting_control(btn_name)
        success = False
        if btn:
            try:
                pat = btn.GetTogglePattern()
                if pat:
                    current_on = (pat.ToggleState == 1)
                    if current_on != target_state:
                        pat.Toggle()
                        time.sleep(1)
                    success = True
                else:
                    inv = btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                        time.sleep(1)
                        success = True
            except Exception:
                pass
        close_quick_settings()
        return success

def set_quick_setting_toggle(btn_name: str, target_state: bool) -> bool:
    return run_in_desktop_thread(_set_quick_setting_toggle_worker, btn_name, target_state)

def airplane_mode_get_status() -> ToolResult:
    state = get_quick_setting_toggle_state("Airplane mode")
    if state == "UNKNOWN":
        return ToolResult(False, error="UNSUPPORTED", observation="Could not determine Airplane mode state.")
    return ToolResult(True, output=state, observation=state)

def airplane_mode_enable() -> ToolResult:
    success = set_quick_setting_toggle("Airplane mode", True)
    if not success:
        return ToolResult(False, error="UNSUPPORTED", observation="Could not enable Airplane mode via Quick Settings.")
    return ToolResult(True, output=True, observation="Airplane mode enabled.")

def airplane_mode_disable() -> ToolResult:
    success = set_quick_setting_toggle("Airplane mode", False)
    if not success:
        return ToolResult(False, error="UNSUPPORTED", observation="Could not disable Airplane mode via Quick Settings.")
    return ToolResult(True, output=True, observation="Airplane mode disabled.")

# ==========================================
# Brightness
# ==========================================

def brightness_get() -> int:
    out = run_ps("(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness")
    try:
        return int(out)
    except:
        return -1

def brightness_set(percent: int) -> bool:
    p = max(0, min(100, percent))
    run_ps(f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{p})")
    time.sleep(0.5)
    return brightness_get() == p

def brightness_increase(step: int) -> bool:
    curr = brightness_get()
    if curr >= 0:
        return brightness_set(curr + step)
    return False

def brightness_decrease(step: int) -> bool:
    curr = brightness_get()
    if curr >= 0:
        return brightness_set(curr - step)
    return False

# ==========================================
# Volume (Requires ctypes/pycaw or NirCmd, but we can try powershell)
# ==========================================

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import math

def _get_volume_interface():
    devices = AudioUtilities.GetSpeakers()
    if not devices:
        return None
    return devices.EndpointVolume

def volume_get() -> ToolResult:
    try:
        vol = _get_volume_interface()
        if not vol:
            return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation="Could not find audio endpoint.")
        val = int(round(vol.GetMasterVolumeLevelScalar() * 100))
        return ToolResult(True, output=val, observation=str(val))
    except Exception as e:
        return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation=str(e))

def volume_set(percent: int) -> ToolResult:
    try:
        p = max(0, min(100, percent))
        vol = _get_volume_interface()
        if not vol:
            return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation="Could not find audio endpoint.")
        vol.SetMasterVolumeLevelScalar(p / 100.0, None)
        return ToolResult(True, output=p, observation=str(p))
    except Exception as e:
        return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation=str(e))

def volume_increase(step: int) -> ToolResult:
    res = volume_get()
    if not res.success: return res
    return volume_set(int(res.output) + step)

def volume_decrease(step: int) -> ToolResult:
    res = volume_get()
    if not res.success: return res
    return volume_set(int(res.output) - step)

def volume_mute() -> ToolResult:
    try:
        vol = _get_volume_interface()
        if not vol: return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation="Could not find audio endpoint.")
        vol.SetMute(1, None)
        return ToolResult(True, output=True, observation="Muted")
    except Exception as e:
        return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation=str(e))

def volume_unmute() -> ToolResult:
    try:
        vol = _get_volume_interface()
        if not vol: return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation="Could not find audio endpoint.")
        vol.SetMute(0, None)
        return ToolResult(True, output=True, observation="Unmuted")
    except Exception as e:
        return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation=str(e))

# ==========================================
# Audio Output
# ==========================================

def audio_output_list() -> ToolResult:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            devices = AudioUtilities.GetAllDevices()
            outputs = []
            for d in devices:
                if str(AudioUtilities.GetEndpointDataFlow(d.id)) == "eRender" and d.FriendlyName:
                    state_str = "DISCONNECTED"
                    ds = str(d.state)
                    if "Active" in ds: state_str = "ACTIVE"
                    elif "Disabled" in ds: state_str = "DISABLED"
                    elif "NotPresent" in ds: state_str = "NOT_PRESENT"
                    elif "Unplugged" in ds: state_str = "UNPLUGGED"
                    
                    is_default = False
                    try:
                        def_dev = AudioUtilities.GetSpeakers()
                        if def_dev and def_dev.id == d.id:
                            is_default = True
                    except: pass
                    
                    outputs.append({
                        "name": d.FriendlyName,
                        "id": d.id,
                        "state": state_str,
                        "is_default": is_default
                    })
            
            obs = "\n".join([f"- {o['name']} [{o['state']}]" + (" [DEFAULT]" if o["is_default"] else "") for o in outputs])
            return ToolResult(True, output=outputs, observation=obs)
        except Exception as e:
            return ToolResult(False, error="AUDIO_ENDPOINT_ERROR", observation=str(e))

def audio_output_get() -> ToolResult:
    try:
        devices = AudioUtilities.GetSpeakers()
        if not devices:
            return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation="No default audio device.")
        return ToolResult(True, output=devices.FriendlyName, observation=devices.FriendlyName)
    except Exception as e:
        return ToolResult(False, error="AUDIO_ENDPOINT_UNAVAILABLE", observation=str(e))

def audio_output_set(device_name: str) -> ToolResult:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            devices = AudioUtilities.GetAllDevices()
            target = None
            for d in devices:
                if str(AudioUtilities.GetEndpointDataFlow(d.id)) == "eRender" and d.FriendlyName:
                    if device_name.lower() in d.FriendlyName.lower():
                        target = d
                        break
            if not target:
                return ToolResult(False, error="DEVICE_NOT_FOUND", observation=f"Audio output '{device_name}' was not found.")
            
            if "Active" not in str(target.state):
                return ToolResult(False, error="DEVICE_NOT_ACTIVE", observation=f"{target.FriendlyName} is known to Windows but is currently disconnected or inactive.")
                
            AudioUtilities.SetDefaultDevice(target.id)
            return ToolResult(True, output=target.FriendlyName, observation=f"Audio output switched to {target.FriendlyName}")
        except Exception as e:
            return ToolResult(False, error="AUDIO_ENDPOINT_ERROR", observation=str(e))

# ==========================================
# Energy Saver
# ==========================================

def energy_saver_get_status() -> ToolResult:
    state = get_quick_setting_toggle_state("Energy saver")
    if state == "UNKNOWN":
        out = run_ps("[Windows.System.Power.PowerManager,Windows.System.Power,ContentType=WindowsRuntime] | Out-Null; [Windows.System.Power.PowerManager]::EnergySaverStatus")
        if "Off" in out: state = "OFF"
        elif "On" in out: state = "ON"
    if state == "UNKNOWN":
        return ToolResult(False, error="UNSUPPORTED", observation="Could not determine Energy saver state.")
    return ToolResult(True, output=state, observation=state)

def energy_saver_enable() -> ToolResult:
    success = set_quick_setting_toggle("Energy saver", True)
    if not success:
        return ToolResult(False, error="UNSUPPORTED", observation="Could not enable Energy saver via Quick Settings.")
    return ToolResult(True, output=True, observation="Energy saver enabled.")

def energy_saver_disable() -> ToolResult:
    success = set_quick_setting_toggle("Energy saver", False)
    if not success:
        return ToolResult(False, error="UNSUPPORTED", observation="Could not disable Energy saver via Quick Settings.")
    return ToolResult(True, output=True, observation="Energy saver disabled.")

# ==========================================
# Accessibility
# ==========================================

def accessibility_open() -> bool:
    run_cmd(["cmd", "/c", "start", "ms-settings:easeofaccess"])
    return True

def quick_settings_open() -> bool:
    open_quick_settings()
    return True

# ==========================================
# Tool Registration
# ==========================================

from jarvis.tools.base import RiskLevel, Tool, ToolResult

def _wrap(f):
    def wrapped(**kwargs):
        res = f(**kwargs)
        if isinstance(res, ToolResult):
            return res
        return ToolResult(True, observation=str(res))
    return wrapped

def register(registry) -> None:
    # Wi-Fi
    registry.register(Tool("sys_wifi_status", "Get Wi-Fi status.", {}, RiskLevel.LOW, _wrap(wifi_get_status), "windows"))
    registry.register(Tool("sys_wifi_enable", "Turn on Wi-Fi.", {}, RiskLevel.LOW, _wrap(wifi_enable), "windows"))
    registry.register(Tool("sys_wifi_disable", "Turn off Wi-Fi.", {}, RiskLevel.LOW, _wrap(wifi_disable), "windows"))
    registry.register(Tool("sys_wifi_list", "List Wi-Fi networks.", {}, RiskLevel.LOW, _wrap(wifi_list_networks), "windows"))
    registry.register(Tool("sys_wifi_connect", "Connect to a Wi-Fi network.", {"ssid": {"type": "str", "required": True}}, RiskLevel.LOW, _wrap(wifi_connect), "windows"))

    # Bluetooth
    registry.register(Tool("sys_bluetooth_status", "Get Bluetooth status.", {}, RiskLevel.LOW, _wrap(bluetooth_get_status), "windows"))
    registry.register(Tool("sys_bluetooth_enable", "Turn on Bluetooth.", {}, RiskLevel.LOW, _wrap(bluetooth_enable), "windows"))
    registry.register(Tool("sys_bluetooth_disable", "Turn off Bluetooth.", {}, RiskLevel.LOW, _wrap(bluetooth_disable), "windows"))
    registry.register(Tool("sys_bluetooth_toggle", "Toggle Bluetooth state.", {}, RiskLevel.LOW, _wrap(bluetooth_toggle), "windows"))
    registry.register(Tool("sys_bluetooth_discover", "Discover Bluetooth devices.", {}, RiskLevel.LOW, _wrap(bluetooth_discover_devices), "windows"))
    registry.register(Tool("sys_bluetooth_connect", "Connect to a Bluetooth device.", {"device_name": {"type": "str", "required": True}}, RiskLevel.LOW, _wrap(bluetooth_connect), "windows"))
    registry.register(Tool("sys_bluetooth_disconnect", "Disconnect from a Bluetooth device.", {"device_name": {"type": "str", "required": True}}, RiskLevel.LOW, _wrap(bluetooth_disconnect), "windows"))
    registry.register(Tool("sys_bluetooth_get_connected", "Get connected Bluetooth devices.", {}, RiskLevel.LOW, _wrap(bluetooth_get_connected_devices), "windows"))

    # Airplane mode
    registry.register(Tool("sys_airplane_mode_status", "Get Airplane mode status.", {}, RiskLevel.LOW, _wrap(airplane_mode_get_status), "windows"))
    registry.register(Tool("sys_airplane_mode_enable", "Turn on Airplane mode.", {}, RiskLevel.LOW, _wrap(airplane_mode_enable), "windows"))
    registry.register(Tool("sys_airplane_mode_disable", "Turn off Airplane mode.", {}, RiskLevel.LOW, _wrap(airplane_mode_disable), "windows"))

    # Brightness
    registry.register(Tool("sys_brightness_get", "Get screen brightness.", {}, RiskLevel.LOW, _wrap(brightness_get), "windows"))
    registry.register(Tool("sys_brightness_set", "Set screen brightness.", {"percent": {"type": "int", "required": True}}, RiskLevel.LOW, _wrap(brightness_set), "windows"))
    registry.register(Tool("sys_brightness_increase", "Increase screen brightness.", {"step": {"type": "int", "required": False}}, RiskLevel.LOW, _wrap(brightness_increase), "windows"))
    registry.register(Tool("sys_brightness_decrease", "Decrease screen brightness.", {"step": {"type": "int", "required": False}}, RiskLevel.LOW, _wrap(brightness_decrease), "windows"))

    # Volume
    registry.register(Tool("sys_volume_get", "Get system volume.", {}, RiskLevel.LOW, _wrap(volume_get), "windows"))
    registry.register(Tool("sys_volume_set", "Set system volume.", {"percent": {"type": "int", "required": True}}, RiskLevel.LOW, _wrap(volume_set), "windows"))
    registry.register(Tool("sys_volume_increase", "Increase system volume.", {"step": {"type": "int", "required": False}}, RiskLevel.LOW, _wrap(volume_increase), "windows"))
    registry.register(Tool("sys_volume_decrease", "Decrease system volume.", {"step": {"type": "int", "required": False}}, RiskLevel.LOW, _wrap(volume_decrease), "windows"))
    registry.register(Tool("sys_volume_mute", "Mute system volume.", {}, RiskLevel.LOW, _wrap(volume_mute), "windows"))
    registry.register(Tool("sys_volume_unmute", "Unmute system volume.", {}, RiskLevel.LOW, _wrap(volume_unmute), "windows"))

    # Audio Output
    registry.register(Tool("sys_audio_output_list", "List audio output devices.", {}, RiskLevel.LOW, _wrap(audio_output_list), "windows"))
    registry.register(Tool("sys_audio_output_get", "Get current audio output device.", {}, RiskLevel.LOW, _wrap(audio_output_get), "windows"))
    registry.register(Tool("sys_audio_output_set", "Set audio output device.", {"device_name": {"type": "str", "required": True}}, RiskLevel.LOW, _wrap(audio_output_set), "windows"))

    # Energy Saver
    registry.register(Tool("sys_energy_saver_status", "Get energy saver status.", {}, RiskLevel.LOW, _wrap(energy_saver_get_status), "windows"))
    registry.register(Tool("sys_energy_saver_enable", "Enable energy saver.", {}, RiskLevel.LOW, _wrap(energy_saver_enable), "windows"))
    registry.register(Tool("sys_energy_saver_disable", "Disable energy saver.", {}, RiskLevel.LOW, _wrap(energy_saver_disable), "windows"))

    # Accessibility & Quick Settings
    registry.register(Tool("sys_accessibility_open", "Open Windows accessibility settings.", {}, RiskLevel.LOW, _wrap(accessibility_open), "windows"))
    registry.register(Tool("sys_quick_settings_open", "Open Windows Quick Settings (Win+A).", {}, RiskLevel.LOW, _wrap(quick_settings_open), "windows"))
