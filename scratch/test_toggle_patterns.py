import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

def test_toggle_methods():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_default:
        user32.SetThreadDesktop(h_default)
        
    with auto.UIAutomationInitializerInThread():
        print("Opening Quick Settings...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        qs_win = root.PaneControl(ClassName='ControlCenterWindow')
        
        btn = qs_win.ButtonControl(searchDepth=10, AutomationId="Microsoft.QuickAction.BlueLightReduction")
        if btn.Exists(1, 0.2):
            pat = btn.GetTogglePattern()
            print(f"Initial ToggleState: {pat.ToggleState if pat else None}")
            
            # Method 1: pat.Toggle()
            if pat:
                print("Trying pat.Toggle()...")
                try:
                    pat.Toggle()
                    time.sleep(1.5)
                    print(f"ToggleState after pat.Toggle(): {pat.ToggleState}")
                except Exception as e:
                    print(f"pat.Toggle() error: {e}")
                    
            # Try InvokePattern
            try:
                inv = btn.GetInvokePattern()
                if inv:
                    print("Trying inv.Invoke()...")
                    inv.Invoke()
                    time.sleep(1.5)
                    print(f"ToggleState after inv.Invoke(): {pat.ToggleState if pat else None}")
            except Exception as e:
                print(f"inv.Invoke() error: {e}")
                
            # Try parent item or keyboard focus
            try:
                print("Trying btn.SetFocus() + SendKeys('{Space}')...")
                btn.SetFocus()
                auto.SendKeys('{Space}')
                time.sleep(1.5)
                print(f"ToggleState after Space: {pat.ToggleState if pat else None}")
            except Exception as e:
                print(f"Focus+Space error: {e}")
                
        else:
            print("Button not found!")
            
        auto.SendKeys('{Win}a')

t = threading.Thread(target=test_toggle_methods)
t.start()
t.join()
