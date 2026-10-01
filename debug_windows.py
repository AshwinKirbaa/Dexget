import ctypes
from ctypes import wintypes
import psutil

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

def get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def get_window_thread_process_id(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def test_apps(app_name):
    print(f"\n--- Testing {app_name} ---")
    pids = []
    for p in psutil.process_iter(['name', 'pid']):
        try:
            if p.info['name'] and app_name.lower() in p.info['name'].lower():
                pids.append(p.info['pid'])
        except:
            pass
    
    print(f"Found PIDs for {app_name}: {pids}")
    hwnds = []
    def enum_windows_proc(hwnd, lParam):
        if get_window_thread_process_id(hwnd) in pids:
            hwnds.append(hwnd)
        return True
    user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
    
    for hwnd in hwnds:
        title = get_window_text(hwnd)
        visible = user32.IsWindowVisible(hwnd) != 0
        if title or visible:
            print(f"HWND: {hwnd}, Visible: {visible}, Title: '{title}'")

test_apps("discord")
test_apps("chrome")
test_apps("explorer")
