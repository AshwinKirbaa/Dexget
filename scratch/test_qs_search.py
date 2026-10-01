import uiautomation as auto
import time

print("Opening Quick Settings (Win+A)...")
auto.SendKeys('{Win}a')
time.sleep(1.5)

# Try searching for Quick Settings window specifically or any buttons
print("Searching for buttons in UIAutomation...")
# Let's search under root control with searchDepth 10
root = auto.GetRootControl()
print("Root:", root)

# Find all buttons under Root
buttons = root.GetChildren()
print("Root children count:", len(buttons))

# Search for any control named Bluetooth, Wi-Fi, Airplane mode, etc.
for name in ["Bluetooth", "Wi-Fi", "Airplane mode", "Quick settings", "Control Center"]:
    c = auto.Control(searchDepth=8, Name=name)
    print(f"Control with Name='{name}': Exists={c.Exists(1, 0.2)}")
    if c.Exists(0, 0):
        print(f"  Found: {c.Name}, Class: {c.ClassName}, ControlType: {c.ControlTypeName}")

# Search by RegexName
for name in ["Bluetooth", "Wi-Fi", "Airplane"]:
    c = auto.Control(searchDepth=8, RegexName=f".*{name}.*")
    print(f"Control with RegexName='.*{name}.*': Exists={c.Exists(1, 0.2)}")
    if c.Exists(0, 0):
        print(f"  Found: {c.Name}, Class: {c.ClassName}, ControlType: {c.ControlTypeName}")

time.sleep(1)
auto.SendKeys('{Win}a')
