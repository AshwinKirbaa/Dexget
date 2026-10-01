import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL_ACCESS = 0x01FF

def check_toggles():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_default:
        user32.SetThreadDesktop(h_default)
        
    with auto.UIAutomationInitializerInThread():
        print("Opening Quick Settings...")
        auto.SendKeys('{Win}a')
        time.sleep(1.5)
        
        root = auto.GetRootControl()
        qs_win = root.PaneControl(ClassName='ControlCenterWindow')
        
        button_map = {
            "Wi-Fi": "Microsoft.QuickAction.WiFi",
            "Bluetooth": "Microsoft.QuickAction.Bluetooth",
            "Airplane mode": "Microsoft.QuickAction.AirplaneMode",
            "Energy saver": "Microsoft.QuickAction.EnergySaverAcOnly",
            "Night light": "Microsoft.QuickAction.BlueLightReduction"
        }
        
        for name, auto_id in button_map.items():
            btn = qs_win.ButtonControl(searchDepth=10, AutomationId=auto_id)
            if btn.Exists(1, 0.2):
                toggle_val = None
                try:
                    toggle_val = btn.CurrentToggleState()
                except Exception as e:
                    toggle_val = f"Error: {e}"
                
                toggle_pat = None
                try:
                    pat = btn.GetTogglePattern()
                    if pat:
                        toggle_pat = pat.ToggleState
                except Exception as e:
                    toggle_pat = f"Error: {e}"
                
                print(f"[{name}] AutoId='{auto_id}' | Exists=True | CurrentToggleState={toggle_val} | TogglePattern.ToggleState={toggle_pat}")
            else:
                print(f"[{name}] AutoId='{auto_id}' | Exists=False")
                
        time.sleep(1)
        auto.SendKeys('{Win}a')

t = threading.Thread(target=check_toggles)
t.start()
t.join()
