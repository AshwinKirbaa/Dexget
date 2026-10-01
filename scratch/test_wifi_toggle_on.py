import sys
sys.path.insert(0, r"c:\Users\Aravindh\Downloads\Dexget-feature-windows-system-controls\Dexget-feature-windows-system-controls")
from jarvis.capabilities import windows_system

print("Turning ON Wi-Fi via set_quick_setting_toggle('Wi-Fi', True)...")
res = windows_system.set_quick_setting_toggle("Wi-Fi", True)
print(f"set_quick_setting_toggle result: {res}")

print("\n--- Quick Settings Wi-Fi state after toggle ---")
st = windows_system.get_quick_setting_toggle_state("Wi-Fi")
print(f"Wi-Fi toggle state: {st}")
