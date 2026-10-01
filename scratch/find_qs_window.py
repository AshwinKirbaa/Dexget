import ctypes
from ctypes import wintypes
import time
import uiautomation as auto
import psutil

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

def get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0: return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def get_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

print("Pressing Win+A...")
auto.SendKeys('{Win}a')
time.sleep(1.5)

print("\n--- EnumWindows (All Windows) ---")
windows = []
def enum_cb(hwnd, lparam):
    txt = get_window_text(hwnd)
    cls = get_class_name(hwnd)
    pid = get_pid(hwnd)
    vis = bool(user32.IsWindowVisible(hwnd))
    windows.append((hwnd, pid, cls, txt, vis))
    return True

user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

print(f"Total window count returned by EnumWindows: {len(windows)}")
for h, pid, cls, txt, vis in windows:
    if vis or txt or "control" in cls.lower() or "center" in cls.lower() or "shell" in cls.lower():
        try:
            pname = psutil.Process(pid).name()
        except:
            pname = "unknown"
        print(f"HWND: {h} | PID: {pid} ({pname}) | Vis: {vis} | Class: '{cls}' | Title: '{txt}'")

time.sleep(1)
auto.SendKeys('{Win}a')
