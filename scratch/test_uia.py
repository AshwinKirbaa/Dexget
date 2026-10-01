import uiautomation as auto
import time

print("Testing uiautomation...")
print("Root:", auto.GetRootControl())
fg = auto.GetForegroundWindow()
print("Foreground window:", fg.Name, fg.ClassName)

print("\nPressing Win+A...")
auto.SendKeys('{Win}a')
time.sleep(1.5)

fg2 = auto.GetForegroundWindow()
print("Foreground window after Win+A:", fg2.Name, fg2.ClassName, fg2.AutomationId)

# Let's search all controls starting from GetForegroundWindow or Desktop
print("\nWalking foreground window:")
for c, d in auto.WalkControl(fg2, maxDepth=4):
    print(f"{'  '*d}[{c.ControlTypeName}] Name: '{c.Name}' | Class: '{c.ClassName}' | AutoId: '{c.AutomationId}'")

time.sleep(1)
auto.SendKeys('{Win}a')
