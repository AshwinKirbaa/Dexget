import ctypes
import ctypes.wintypes as wintypes
import os
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

session_id = wintypes.DWORD()
kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(session_id))

h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
buf = ctypes.create_unicode_buffer(256)
user32.GetUserObjectInformationW(h_desk, 2, buf, ctypes.sizeof(buf), None)

h_winsta = user32.GetProcessWindowStation()
buf2 = ctypes.create_unicode_buffer(256)
user32.GetUserObjectInformationW(h_winsta, 2, buf2, ctypes.sizeof(buf2), None)

print(f"Python PID: {os.getpid()}")
print(f"Session ID: {session_id.value}")
print(f"Window Station: {buf2.value}")
print(f"Desktop: {buf.value}")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False
print(f"Is Admin: {is_admin()}")
