import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

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

def ensure_desktop():
    try:
        h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
        if h_default:
            user32.SetThreadDesktop(h_default)
    except Exception:
        pass

def open_quick_settings():
    ensure_desktop()
    auto.SendKeys('{Win}a')
    time.sleep(1.2)

def close_quick_settings():
    ensure_desktop()
    auto.SendKeys('{Win}a')

def find_quick_setting_control(btn_name: str, auto_id_override: str = None, is_manage_btn: bool = False):
    """Walk root UI tree to find a Quick Settings control reliably."""
    target_id = auto_id_override or QUICK_ACTION_MAP.get(btn_name.lower())
    target_name_lower = btn_name.lower()
    
    root = auto.GetRootControl()
    
    for control, depth in auto.WalkControl(root, maxDepth=12):
        try:
            c_id = control.AutomationId or ""
            c_name = control.Name or ""
            
            if is_manage_btn:
                if c_id == "SplitL2Button" and target_name_lower in c_name.lower():
                    return control
                if "manage" in c_name.lower() and target_name_lower in c_name.lower():
                    return control
            else:
                if target_id and target_id.lower() == c_id.lower():
                    return control
                if c_name and target_name_lower == c_name.lower() and c_id != "SplitL2Button":
                    return control
        except Exception:
            pass
    return None

def get_quick_setting_toggle_state(btn_name: str) -> str:
    ensure_desktop()
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

def set_quick_setting_toggle(btn_name: str, target_state: bool) -> bool:
    ensure_desktop()
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
            except Exception as e:
                print(f"Error toggling {btn_name}: {e}")
        close_quick_settings()
        return success

def test_module():
    print("--- Test get_quick_setting_toggle_state ---")
    for item in ["Wi-Fi", "Bluetooth", "Airplane mode", "Energy saver", "Night light"]:
        st = get_quick_setting_toggle_state(item)
        print(f"{item} status: {st}")
        
    print("\n--- Test set_quick_setting_toggle (Night light toggle & revert) ---")
    st_before = get_quick_setting_toggle_state("Night light")
    print(f"Night light before: {st_before}")
    target = (st_before != "ON")
    res1 = set_quick_setting_toggle("Night light", target)
    print(f"Set Night light to {target}: success={res1}")
    st_middle = get_quick_setting_toggle_state("Night light")
    print(f"Night light middle: {st_middle}")
    res2 = set_quick_setting_toggle("Night light", not target)
    print(f"Reverted Night light: success={res2}")
    st_after = get_quick_setting_toggle_state("Night light")
    print(f"Night light after: {st_after}")

t = threading.Thread(target=test_module)
t.start()
t.join()
