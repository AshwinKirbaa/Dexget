import sys
import os
import time

# Add project root to sys.path
sys.path.insert(0, r"c:\Users\Aravindh\Downloads\Dexget-feature-windows-system-controls\Dexget-feature-windows-system-controls")

from jarvis.capabilities import windows_system

print("--- Testing Quick Settings & System Control capabilities ---")

print("\n1. Testing Bluetooth Status...")
bt_st = windows_system.bluetooth_get_status()
print(f"Bluetooth status result: success={bt_st.success}, output='{bt_st.output}'")

print("\n2. Testing Airplane Mode Status...")
ap_st = windows_system.airplane_mode_get_status()
print(f"Airplane mode status result: success={ap_st.success}, output='{ap_st.output}'")

print("\n3. Testing Energy Saver Status...")
es_st = windows_system.energy_saver_get_status()
print(f"Energy saver status result: success={es_st.success}, output='{es_st.output}'")

print("\n4. Testing Night Light Quick Setting Toggle (Toggle & Revert)...")
nl_st_before = windows_system.get_quick_setting_toggle_state("Night light")
print(f"Night light status before: '{nl_st_before}'")
if nl_st_before != "UNKNOWN":
    target = (nl_st_before != "ON")
    toggle_res1 = windows_system.set_quick_setting_toggle("Night light", target)
    print(f"Set Night light to {target}: success={toggle_res1}")
    nl_st_mid = windows_system.get_quick_setting_toggle_state("Night light")
    print(f"Night light status mid: '{nl_st_mid}'")
    toggle_res2 = windows_system.set_quick_setting_toggle("Night light", not target)
    print(f"Reverted Night light to {not target}: success={toggle_res2}")
    nl_st_after = windows_system.get_quick_setting_toggle_state("Night light")
    print(f"Night light status after: '{nl_st_after}'")

print("\n--- Verification completed cleanly ---")
