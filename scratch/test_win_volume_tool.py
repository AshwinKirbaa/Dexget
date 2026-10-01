import sys
sys.path.insert(0, r"c:\Users\Aravindh\Downloads\Dexget-feature-windows-system-controls\Dexget-feature-windows-system-controls")
from jarvis.tools import windows

print("1. Testing volume_set(60)...")
res1 = windows.volume_set(60)
print(f"volume_set(60) result: success={res1.success}, obs='{res1.observation}', err='{res1.error}'")

print("\n2. Testing volume_set(80)...")
res2 = windows.volume_set(80)
print(f"volume_set(80) result: success={res2.success}, obs='{res2.observation}', err='{res2.error}'")

print("\n3. Testing volume_up()...")
res3 = windows.volume_up()
print(f"volume_up result: success={res3.success}, obs='{res3.observation}'")

print("\n4. Testing volume_down()...")
res4 = windows.volume_down()
print(f"volume_down result: success={res4.success}, obs='{res4.observation}'")

print("\n--- Volume tests completed cleanly ---")
