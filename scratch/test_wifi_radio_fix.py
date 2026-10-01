import subprocess
import sys
sys.path.insert(0, r"c:\Users\Aravindh\Downloads\Dexget-feature-windows-system-controls\Dexget-feature-windows-system-controls")
from jarvis.capabilities import windows_system

print("--- netsh wlan show interfaces output ---")
res = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True)
print(res.stdout)

print("\n--- Quick Settings Wi-Fi state ---")
qs_wifi_state = windows_system.get_quick_setting_toggle_state("Wi-Fi")
print(f"Quick Settings Wi-Fi state: {qs_wifi_state}")
