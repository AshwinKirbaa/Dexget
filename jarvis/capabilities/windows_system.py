import subprocess
import re
import os
import uiautomation as auto
import time
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

def open_quick_settings():
    """Opens Quick Settings via Win+A."""
    auto.SendKeys('{Win}a')
    time.sleep(1.0)

# ==========================================
# Wi-Fi
# ==========================================

def wifi_get_status() -> ToolResult:
    out = run_cmd(["netsh", "wlan", "show", "interfaces"])
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
    return ToolResult(False, error="UNKNOWN_WIFI_STATE", observation="unknown")

def wifi_enable() -> ToolResult:
    # First try netsh / PS
    run_ps("Enable-NetAdapter -Name 'Wi-Fi' -Confirm:$false")
    time.sleep(2)
    st = wifi_get_status()
    if st.success and "enabled" in st.output:
        return ToolResult(True, output=True, observation="Wi-Fi enabled.")
    
    # UIAutomation fallback
    _click_quick_setting_button("Wi-Fi")
    time.sleep(3)
    
    st2 = wifi_get_status()
    if st2.success and "enabled" in st2.output:
        return ToolResult(True, output=True, observation="Wi-Fi enabled.")
    return ToolResult(False, error="UNVERIFIED", observation="Attempted to enable Wi-Fi, but state remains unverified.")

def wifi_disable() -> ToolResult:
    run_ps("Disable-NetAdapter -Name 'Wi-Fi' -Confirm:$false")
    time.sleep(2)
    st = wifi_get_status()
    if st.success and "disabled" in st.output:
        return ToolResult(True, output=True, observation="Wi-Fi disabled.")
        
    # UIAutomation fallback
    _click_quick_setting_button("Wi-Fi")
    time.sleep(3)
    
    st2 = wifi_get_status()
    if st2.success and "disabled" in st2.output:
        return ToolResult(True, output=True, observation="Wi-Fi disabled.")
    return ToolResult(False, error="UNVERIFIED", observation="Attempted to disable Wi-Fi, but state remains unverified.")

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

def _click_quick_setting_button(btn_name: str) -> bool:
    open_quick_settings()
    # Try exact match first to avoid hitting "Manage Bluetooth devices" when we want "Bluetooth"
    btn = auto.Control(searchDepth=4, RegexName=f"^{btn_name}$")
    if btn.Exists(2, 1):
        btn.Click()
        time.sleep(1)
        auto.SendKeys('{Win}a')
        return True
    
    # Fallback to substring
    btn = auto.Control(searchDepth=4, RegexName=f".*{btn_name}.*")
    if btn.Exists(2, 1):
        btn.Click()
        time.sleep(1)
        auto.SendKeys('{Win}a')
        return True
        
    auto.SendKeys('{Win}a')
    return False

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

def _bluetooth_manage_ui(device_name: str, connect: bool) -> ToolResult:
    open_quick_settings()
    manage_btn = auto.ButtonControl(searchDepth=4, RegexName=".*Manage Bluetooth.*")
    if not manage_btn.Exists(2, 1):
        auto.SendKeys('{Win}a')
        return ToolResult(False, error="UI_AUTOMATION_FAILED", observation="Could not open Quick Settings Bluetooth menu.")
        
    manage_btn.Click()
    time.sleep(1.5)
    
    target = auto.ListItemControl(searchDepth=6, RegexName=f".*{device_name}.*")
    if not target.Exists(2, 1):
        auto.SendKeys('{Win}a')
        return ToolResult(False, error="DEVICE_NOT_FOUND", observation=f"I couldn't find {device_name}.")
        
    target.Click()
    time.sleep(4 if connect else 2) # Wait for action
    auto.SendKeys('{Win}a')
    
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

def get_quick_setting_toggle_state(btn_name: str) -> str:
    open_quick_settings()
    btn = auto.ButtonControl(searchDepth=4, RegexName=f".*{btn_name}.*")
    state = "UNKNOWN"
    if btn.Exists(2, 1):
        try:
            state = "ON" if btn.CurrentToggleState() == 1 else "OFF"
        except:
            if "On" in btn.Name: state = "ON"
            elif "Off" in btn.Name: state = "OFF"
    auto.SendKeys('{Win}a')
    return state

def set_quick_setting_toggle(btn_name: str, target_state: bool) -> bool:
    open_quick_settings()
    btn = auto.ButtonControl(searchDepth=4, RegexName=f".*{btn_name}.*")
    success = False
    if btn.Exists(2, 1):
        current = None
        try:
            current = (btn.CurrentToggleState() == 1)
        except:
            if "On" in btn.Name: current = True
            elif "Off" in btn.Name: current = False
            
        if current is not None:
            if current != target_state:
                btn.Click()
                time.sleep(1)
                success = True
            else:
                success = True # Already in target state
    auto.SendKeys('{Win}a')
    return success

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
    out = run_ps("[Windows.System.Power.PowerManager,Windows.System.Power,ContentType=WindowsRuntime] | Out-Null; [Windows.System.Power.PowerManager]::EnergySaverStatus")
    state = "UNKNOWN"
    if "Off" in out: state = "OFF"
    elif "On" in out: state = "ON"
    return ToolResult(True, output=state, observation=state)

def energy_saver_enable() -> ToolResult:
    return ToolResult(False, error="UNSUPPORTED", observation="No reliable control interface available for Energy Saver toggle.")

def energy_saver_disable() -> ToolResult:
    return ToolResult(False, error="UNSUPPORTED", observation="No reliable control interface available for Energy Saver toggle.")

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
