import ctypes
import ctypes.wintypes as wintypes
import threading
import time

user32 = ctypes.windll.user32
DESKTOP_ALL_ACCESS = 0x01FF

def run_in_desktop_thread(fn, *args, **kwargs):
    """Run fn in a dedicated thread attached to 'Default' desktop station."""
    res_box = [None, None] # [result, exception]
    def worker():
        try:
            h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
            if h_default:
                user32.SetThreadDesktop(h_default)
            res_box[0] = fn(*args, **kwargs)
        except Exception as e:
            res_box[1] = e

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    if res_box[1]:
        raise res_box[1]
    return res_box[0]

import uiautomation as auto

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

def _get_qs_state_worker(btn_name: str):
    with auto.UIAutomationInitializerInThread():
        auto.SendKeys('{Win}a')
        time.sleep(1.2)
        
        root = auto.GetRootControl()
        qs = root.PaneControl(ClassName='ControlCenterWindow')
        if not qs.Exists(2.0, 0.2):
            auto.SendKeys('{Win}a')
            return "UNKNOWN"
            
        target_id = QUICK_ACTION_MAP.get(btn_name.lower())
        btn = None
        for control, depth in auto.WalkControl(qs, maxDepth=10):
            c_id = control.AutomationId or ""
            c_name = control.Name or ""
            c_type = control.ControlTypeName
            if target_id and target_id.lower() == c_id.lower():
                btn = control
                break
            if c_name and btn_name.lower() == c_name.lower() and c_id != "SplitL2Button":
                if c_type in ["ButtonControl", "CheckBoxControl", "ToggleControl"]:
                    btn = control
                    break
                    
        state = "UNKNOWN"
        if btn:
            try:
                pat = btn.GetTogglePattern()
                if pat:
                    state = "ON" if pat.ToggleState == 1 else "OFF"
            except: pass
            if state == "UNKNOWN":
                if "On" in btn.Name: state = "ON"
                elif "Off" in btn.Name: state = "OFF"
                
        auto.SendKeys('{Win}a')
        return state

def get_quick_setting_toggle_state(btn_name: str) -> str:
    return run_in_desktop_thread(_get_qs_state_worker, btn_name)

print("Testing get_quick_setting_toggle_state with run_in_desktop_thread:")
for item in ["Wi-Fi", "Bluetooth", "Airplane mode", "Energy saver", "Night light"]:
    st = get_quick_setting_toggle_state(item)
    print(f"{item:15}: {st}")
