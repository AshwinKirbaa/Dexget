import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import subprocess
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

DESKTOP_ALL_ACCESS = 0x01FF

def run_on_default_desktop():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if not h_default:
        print(f"OpenDesktopW failed: {kernel32.GetLastError()}")
        return
    
    res = user32.SetThreadDesktop(h_default)
    print(f"SetThreadDesktop in new thread result: {res}")
    if not res:
        print(f"SetThreadDesktop error: {kernel32.GetLastError()}")
        return
        
    with auto.UIAutomationInitializerInThread():
        print("Pressing Win+A...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        print("Root control:", root)
        
        found_cnt = 0
        for child, depth in auto.WalkControl(root, maxDepth=4):
            if child.Name or child.AutomationId or child.ClassName:
                print(f"  {'  '*depth}[{child.ControlTypeName}] Name: '{child.Name}' | Class: '{child.ClassName}' | AutoId: '{child.AutomationId}'")
                found_cnt += 1
                if found_cnt > 40:
                    print("... stopped after 40 controls ...")
                    break
                    
        time.sleep(1)
        auto.SendKeys('{Win}a')

t = threading.Thread(target=run_on_default_desktop)
t.start()
t.join()
