import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

def ensure_desktop():
    try:
        h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
        if h_default:
            user32.SetThreadDesktop(h_default)
    except Exception:
        pass

def debug_find():
    ensure_desktop()
    with auto.UIAutomationInitializerInThread():
        print("Opening Quick Settings...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        print(f"Root: {root.Name} ({root.ClassName})")
        
        found = []
        for control, depth in auto.WalkControl(root, maxDepth=12):
            try:
                c_id = control.AutomationId or ""
                c_name = control.Name or ""
                if "QuickAction" in c_id or "Bluetooth" in c_name or "Wi-Fi" in c_name:
                    found.append((c_id, c_name, control.ControlTypeName))
            except Exception as e:
                pass
                
        print(f"Found {len(found)} matching controls:")
        for fid, fname, ftype in found:
            print(f"  Type: {ftype} | AutoId: '{fid}' | Name: '{fname}'")
            
        auto.SendKeys('{Win}a')

t = threading.Thread(target=debug_find)
t.start()
t.join()
