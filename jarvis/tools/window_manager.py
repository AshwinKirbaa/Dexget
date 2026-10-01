import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SW_RESTORE = 9

def is_window_visible(hwnd):
    return user32.IsWindowVisible(hwnd) != 0

def get_window_thread_process_id(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def is_iconic(hwnd):
    return user32.IsIconic(hwnd) != 0

def get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def get_foreground_window():
    return user32.GetForegroundWindow()

class WindowManager:
    @staticmethod
    def get_windows_for_pid(pid):
        hwnds = []
        def enum_windows_proc(hwnd, lParam):
            if get_window_thread_process_id(hwnd) == pid:
                hwnds.append(hwnd)
            return True
        user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
        return hwnds

    @staticmethod
    def get_main_window_for_pid(pid, app_name=None):
        hwnds = WindowManager.get_windows_for_pid(pid)
        
        # Pass 1: Visible windows with a title (ignoring desktop/taskbar)
        for hwnd in hwnds:
            if is_window_visible(hwnd) and get_window_text(hwnd).strip():
                cls = get_class_name(hwnd)
                if cls in ("Progman", "Shell_TrayWnd", "WorkerW"):
                    continue
                return hwnd
                
        # Pass 2: Hidden/tray windows or specific classes
        for hwnd in hwnds:
            cls = get_class_name(hwnd)
            title = get_window_text(hwnd).lower()
            
            if app_name and ("explorer" in app_name.lower()):
                if cls == "CabinetWClass":
                    return hwnd
            elif app_name and ("discord" in app_name.lower()):
                if "discord" in title:
                    return hwnd
            elif app_name and ("chrome" in app_name.lower() or "brave" in app_name.lower()):
                if cls == "Chrome_WidgetWin_1" and title:
                    return hwnd
                    
        return None

    @staticmethod
    def activate_window(hwnd):
        if is_iconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, 5) # SW_SHOW
        
        # Bring to foreground using AttachThreadInput trick if necessary
        foreground_hwnd = get_foreground_window()
        if foreground_hwnd == hwnd:
            return True
            
        # Bypass Windows foreground lock timeout by simulating an ALT key press
        VK_MENU = 0x12
        KEYEVENTF_EXTENDEDKEY = 0x0001
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            
        fg_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None)
        my_thread = kernel32.GetCurrentThreadId()
        
        if fg_thread != my_thread and fg_thread != 0:
            user32.AttachThreadInput(my_thread, fg_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            user32.AttachThreadInput(my_thread, fg_thread, False)
        else:
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            
        time.sleep(0.3) # Give windows time to process
        return WindowManager.verify_window_active(hwnd)

    @staticmethod
    def verify_window_active(hwnd):
        fg = get_foreground_window()
        if fg == hwnd:
            return True
        # Also check if the foreground window belongs to the same PID
        # This handles cases where an app opens a sub-dialog or child window
        target_pid = get_window_thread_process_id(hwnd)
        fg_pid = get_window_thread_process_id(fg)
        return target_pid == fg_pid
