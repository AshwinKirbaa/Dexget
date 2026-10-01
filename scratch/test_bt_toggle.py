import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

def test_bt_toggle():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_default:
        user32.SetThreadDesktop(h_default)
        
    with auto.UIAutomationInitializerInThread():
        print("Opening Quick Settings...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        qs_win = root.PaneControl(ClassName='ControlCenterWindow')
        
        # Search by AutomationId
        btn = qs_win.Control(searchDepth=12, AutomationId="Microsoft.QuickAction.Bluetooth")
        if not btn.Exists(2, 0.2):
            print("Trying search from root...")
            btn = root.Control(searchDepth=12, AutomationId="Microsoft.QuickAction.Bluetooth")
            
        if btn.Exists(1, 0.2):
            print(f"Found Bluetooth button: Name='{btn.Name}', Class='{btn.ClassName}', ControlType={btn.ControlTypeName}")
            
            # Check Patterns
            pat_toggle = None
            try:
                pat_toggle = btn.GetTogglePattern()
            except: pass
            
            pat_inv = None
            try:
                pat_inv = btn.GetInvokePattern()
            except: pass
            
            print(f"TogglePattern: {pat_toggle}, InvokePattern: {pat_inv}")
            if pat_toggle:
                print(f"ToggleState before: {pat_toggle.ToggleState}")
                print("Calling pat_toggle.Toggle()...")
                pat_toggle.Toggle()
                time.sleep(2)
                print(f"ToggleState after pat_toggle.Toggle(): {pat_toggle.ToggleState}")
                
                print("Calling pat_toggle.Toggle() again to restore...")
                pat_toggle.Toggle()
                time.sleep(2)
                print(f"ToggleState after restore: {pat_toggle.ToggleState}")
            elif pat_inv:
                print("Calling pat_inv.Invoke()...")
                pat_inv.Invoke()
                time.sleep(2)
            else:
                print("Neither Toggle Pattern nor Invoke Pattern available. Trying SetFocus + Space...")
                btn.SetFocus()
                auto.SendKeys('{Space}')
                time.sleep(2)
        else:
            print("Bluetooth button not found!")
            
        auto.SendKeys('{Win}a')

t = threading.Thread(target=test_bt_toggle)
t.start()
t.join()
