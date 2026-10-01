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

def get_qs_window():
    root = auto.GetRootControl()
    qs = root.PaneControl(ClassName='ControlCenterWindow')
    if qs.Exists(0.5, 0.1):
        return qs
    for child in root.GetChildren():
        if 'controlcenter' in child.ClassName.lower() or child.Name == 'Quick settings':
            return child
    return root

def find_quick_setting_control(btn_name: str, auto_id_override: str = None, is_manage_btn: bool = False):
    target_id = auto_id_override or QUICK_ACTION_MAP.get(btn_name.lower())
    target_name_lower = btn_name.lower()
    
    qs_container = get_qs_window()
    
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
                # Must match AutoId or be a button/toggle control with matching name
                if target_id and target_id.lower() == c_id.lower():
                    return control
                if c_name and target_name_lower == c_name.lower() and c_id != "SplitL2Button":
                    if c_type in ["ButtonControl", "CheckBoxControl", "ToggleControl"]:
                        return control
        except Exception:
            pass
    return None

def test_pattern_details():
    ensure_desktop()
    with auto.UIAutomationInitializerInThread():
        auto.SendKeys('{Win}a')
        time.sleep(1.0)
        
        for item in ["Wi-Fi", "Bluetooth", "Airplane mode", "Energy saver", "Night light"]:
            btn = find_quick_setting_control(item)
            if btn:
                print(f"\n--- Item: {item} ---")
                print(f"Name: {btn.Name}, AutoId: {btn.AutomationId}, ControlType: {btn.ControlTypeName}")
                try:
                    pat = btn.GetTogglePattern()
                    print(f"TogglePattern: {pat}")
                    if pat:
                        print(f"ToggleState: {pat.ToggleState}")
                except Exception as e:
                    print(f"GetTogglePattern error: {e}")
            else:
                print(f"\n--- Item: {item} NOT FOUND ---")
                
        auto.SendKeys('{Win}a')

t = threading.Thread(target=test_pattern_details)
t.start()
t.join()
