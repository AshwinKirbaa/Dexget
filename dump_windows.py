import ctypes
from ctypes import wintypes
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

def get_window_thread_process_id(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def dump_app(app_name):
    print(f"\n--- {app_name} ---")
    pids = []
    for p in psutil.process_iter(['name', 'pid']):
        try:
            if p.info['name'] and app_name.lower() in p.info['name'].lower():
                pids.append(p.info['pid'])
        except: pass
    
    hwnds = []
    def cb(hwnd, lParam):
        if get_window_thread_process_id(hwnd) in pids:
            hwnds.append(hwnd)
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    
    for h in hwnds:
        title = get_window_text(h)
        cls = get_class_name(h)
        vis = user32.IsWindowVisible(h) != 0
        if title or cls == "Chrome_WidgetWin_1" or "CabinetWClass" in cls:
            print(f"HWND: {h}, PID: {get_window_thread_process_id(h)}, Vis: {vis}, Title: '{title}', Class: '{cls}'")

dump_app("discord")
dump_app("chrome")
dump_app("explorer")
