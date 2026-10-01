import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import sys

sys.path.insert(0, r"c:\Users\Aravindh\Downloads\Dexget-feature-windows-system-controls\Dexget-feature-windows-system-controls")
import uiautomation as auto

user32 = ctypes.windll.user32
DESKTOP_ALL_ACCESS = 0x01FF

def ensure_desktop():
    try:
        h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
        if h_default:
            user32.SetThreadDesktop(h_default)
    except Exception:
        pass

def test_qs_wait():
    ensure_desktop()
    with auto.UIAutomationInitializerInThread():
        print("Opening Win+A...")
        auto.SendKeys('{Win}a')
        t0 = time.time()
        root = auto.GetRootControl()
        qs = root.PaneControl(ClassName='ControlCenterWindow')
        found = qs.Exists(3.0, 0.2)
        dt = time.time() - t0
        print(f"qs.Exists(3.0, 0.2) -> Found={found} in {dt:.3f}s")
        
        if found:
            for item in ["Wi-Fi", "Bluetooth", "Airplane mode", "Energy saver", "Night light"]:
                # Search inside qs
                btn = None
                for control, depth in auto.WalkControl(qs, maxDepth=10):
                    c_id = control.AutomationId or ""
                    c_name = control.Name or ""
                    c_type = control.ControlTypeName
                    if item.lower() in c_name.lower() or item.lower() in c_id.lower():
                        if c_type in ["ButtonControl", "CheckBoxControl", "ToggleControl"]:
                            btn = control
                            break
                print(f"Item {item:15}: Found={btn is not None} (AutoId='{btn.AutomationId if btn else ''}')")
                
        auto.SendKeys('{Win}a')

t = threading.Thread(target=test_qs_wait)
t.start()
t.join()
