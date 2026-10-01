import ctypes
import ctypes.wintypes as wintypes
import time
import subprocess
import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

DESKTOP_ALL_ACCESS = 0x01FF

def switch_to_default_desktop():
    h_default = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
    if h_default:
        res = user32.SetThreadDesktop(h_default)
        print(f"SetThreadDesktop('Default') result: {res}")
        return h_default
    else:
        err = kernel32.GetLastError()
        print(f"OpenDesktopW('Default') failed with error: {err}")
        return None

print("Switching desktop to Default...")
h_desk = switch_to_default_desktop()

print("\nPressing Win+A...")
auto.SendKeys('{Win}a')
time.sleep(1.5)

root = auto.GetRootControl()
print("Root control:", root)

# Let's walk controls under root
print("\nWalking root controls:")
found_cnt = 0
for child, depth in auto.WalkControl(root, maxDepth=3):
    if child.Name or child.AutomationId or child.ClassName:
        print(f"  {'  '*depth}[{child.ControlTypeName}] Name: '{child.Name}' | Class: '{child.ClassName}' | AutoId: '{child.AutomationId}'")
        found_cnt += 1
        if found_cnt > 40:
            print("... stopped after 40 controls ...")
            break

time.sleep(1)
auto.SendKeys('{Win}a')
