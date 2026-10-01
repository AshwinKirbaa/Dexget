import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

def find_qs_button(qs_win, identifier: str):
    """Search for a quick action button by AutomationId or Name using WalkControl."""
    id_lower = identifier.lower()
    for control, depth in auto.WalkControl(qs_win, maxDepth=12):
        try:
            auto_id = control.AutomationId
            name = control.Name
            
            if auto_id and id_lower in auto_id.lower():
                return control
            if name and id_lower == name.lower() and auto_id != "SplitL2Button":
                return control
        except:
            pass
    return None

def test_walk_toggle():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_default:
        user32.SetThreadDesktop(h_default)
        
    with auto.UIAutomationInitializerInThread():
        print("Opening Quick Settings...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        qs_win = root.PaneControl(ClassName='ControlCenterWindow')
        if not qs_win.Exists(2, 0.5):
            qs_win = root
            
        print("Finding Bluetooth button via WalkControl...")
        btn = find_qs_button(qs_win, "Microsoft.QuickAction.Bluetooth")
        if btn:
            print(f"FOUND! Type: {btn.ControlTypeName}, Name: '{btn.Name}', AutoId: '{btn.AutomationId}'")
            pat_toggle = None
            try:
                pat_toggle = btn.GetTogglePattern()
            except: pass
            
            print(f"TogglePattern: {pat_toggle}")
            if pat_toggle:
                print(f"ToggleState before: {pat_toggle.ToggleState}")
                print("Toggling...")
                pat_toggle.Toggle()
                time.sleep(2)
                print(f"ToggleState after: {pat_toggle.ToggleState}")
                print("Restoring state...")
                pat_toggle.Toggle()
                time.sleep(2)
                print(f"ToggleState final: {pat_toggle.ToggleState}")
            else:
                print("No TogglePattern. Trying Invoke pattern or Space...")
                try:
                    inv = btn.GetInvokePattern()
                    if inv:
                        inv.Invoke()
                        print("Invoked!")
                except Exception as e:
                    print(f"Invoke error: {e}")
        else:
            print("Bluetooth button NOT found via WalkControl!")
            
        auto.SendKeys('{Win}a')

t = threading.Thread(target=test_walk_toggle)
t.start()
t.join()
