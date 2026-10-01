import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import sys
import uiautomation as auto

# Fix stdout encoding for printing unicode
sys.stdout.reconfigure(encoding='utf-8')

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

DESKTOP_ALL_ACCESS = 0x01FF

def inspect_qs():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_default:
        user32.SetThreadDesktop(h_default)
        
    with auto.UIAutomationInitializerInThread():
        print("Pressing Win+A...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        qs_win = root.PaneControl(ClassName='ControlCenterWindow')
        if not qs_win.Exists(2, 0.5):
            print("ControlCenterWindow not found via PaneControl. Checking all children of root...")
            qs_win = root
            
        print(f"Targeting window: {qs_win.Name} ({qs_win.ClassName})")
        
        print("\n--- Quick Settings Detailed Hierarchy ---")
        for control, depth in auto.WalkControl(qs_win, maxDepth=10):
            try:
                name = control.Name
                c_type = control.ControlTypeName
                auto_id = control.AutomationId
                cls = control.ClassName
                toggle_state = ""
                if hasattr(control, 'CurrentToggleState'):
                    try:
                        toggle_state = control.CurrentToggleState()
                    except:
                        pass
                value = ""
                if hasattr(control, 'CurrentValue'):
                    try:
                        value = control.CurrentValue()
                    except:
                        pass
                
                print(f"{'  '*depth}[{c_type}] Name: '{name}' | AutoId: '{auto_id}' | Class: '{cls}' | Toggle: {toggle_state} | Value: {value}")
            except Exception as e:
                print(f"{'  '*depth}Error inspecting control: {e}")
                
        time.sleep(1)
        auto.SendKeys('{Win}a')

t = threading.Thread(target=inspect_qs)
t.start()
t.join()
