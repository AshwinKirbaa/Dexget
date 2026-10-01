import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

def run():
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
            print("ControlCenterWindow not found. Searching root...")
            qs_win = root
            
        print(f"Targeting: {qs_win.ClassName}")
        
        for c, depth in auto.WalkControl(qs_win, maxDepth=12):
            # Print buttons, checkboxes, toggles, sliders, lists
            if c.ControlType in [auto.ControlType.ButtonControl, auto.ControlType.CheckBoxControl, auto.ControlType.ListItemControl, auto.ControlType.SliderControl, auto.ControlType.TextControl, auto.ControlType.GroupControl]:
                try:
                    name = ascii(c.Name)
                    auto_id = c.AutomationId
                    c_type = c.ControlTypeName
                    toggle = ""
                    try:
                        if hasattr(c, 'CurrentToggleState'):
                            toggle = c.CurrentToggleState()
                    except: pass
                    val = ""
                    try:
                        if hasattr(c, 'CurrentValue'):
                            val = c.CurrentValue()
                    except: pass
                    print(f"{'  '*depth}[{c_type}] Name: {name} | AutoId: '{auto_id}' | Toggle: {toggle} | Value: {val}")
                except Exception as e:
                    pass
                    
        time.sleep(1)
        auto.SendKeys('{Win}a')

t = threading.Thread(target=run)
t.start()
t.join()
