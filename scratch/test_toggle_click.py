import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

def test_toggle():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_default:
        user32.SetThreadDesktop(h_default)
        
    with auto.UIAutomationInitializerInThread():
        print("Opening Quick Settings...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        qs_win = root.PaneControl(ClassName='ControlCenterWindow')
        
        # Test Night Light toggle (safe to toggle and revert)
        btn = qs_win.ButtonControl(searchDepth=10, AutomationId="Microsoft.QuickAction.BlueLightReduction")
        if btn.Exists(1, 0.2):
            pat = btn.GetTogglePattern()
            state1 = pat.ToggleState if pat else None
            print(f"Night Light state before click: {state1}")
            
            # Click to toggle
            btn.Click()
            time.sleep(1.5)
            
            state2 = pat.ToggleState if pat else None
            print(f"Night Light state after click: {state2}")
            
            # Click again to revert
            btn.Click()
            time.sleep(1.5)
            
            state3 = pat.ToggleState if pat else None
            print(f"Night Light state after revert click: {state3}")
        else:
            print("Night Light button not found!")
            
        auto.SendKeys('{Win}a')

t = threading.Thread(target=test_toggle)
t.start()
t.join()
