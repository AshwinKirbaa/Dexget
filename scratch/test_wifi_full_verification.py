import sys
sys.path.insert(0, r"c:\Users\Aravindh\Downloads\Dexget-feature-windows-system-controls\Dexget-feature-windows-system-controls")
from jarvis.capabilities import windows_system

print("1. Testing wifi_get_status()...")
st1 = windows_system.wifi_get_status()
print(f"Status result: success={st1.success}, output='{st1.output}'")

print("\n2. Testing wifi_enable()...")
res_en = windows_system.wifi_enable()
print(f"wifi_enable result: success={res_en.success}, obs='{res_en.observation}'")

st2 = windows_system.wifi_get_status()
print(f"Status after enable: output='{st2.output}'")

print("\n3. Testing wifi_disable()...")
res_dis = windows_system.wifi_disable()
print(f"wifi_disable result: success={res_dis.success}, obs='{res_dis.observation}'")

st3 = windows_system.wifi_get_status()
print(f"Status after disable: output='{st3.output}'")

print("\n4. Re-enabling Wi-Fi...")
res_en2 = windows_system.wifi_enable()
print(f"wifi_enable restore result: success={res_en2.success}, obs='{res_en2.observation}'")

print("\n--- Test complete ---")
