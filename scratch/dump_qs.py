import uiautomation as auto
import time

print("Pressing Win+A...")
auto.SendKeys('{Win}a')
time.sleep(1.5)

root = auto.GetRootControl()
print("Top level children of Desktop (all):")
children = root.GetChildren()
print(f"Total top level children count: {len(children)}")
for child in children:
    try:
        name = child.Name
        cls = child.ClassName
        c_type = child.ControlTypeName
        off = child.IsOffscreen
        print(f"Name: '{name}' | Class: '{cls}' | Type: {c_type} | Offscreen: {off}")
    except Exception as e:
        print(f"Error reading child: {e}")

time.sleep(1)
auto.SendKeys('{Win}a')
