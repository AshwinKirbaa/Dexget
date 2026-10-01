import uiautomation as auto
import time

def inspect_windows():
    auto.SendKeys('{Win}a')
    time.sleep(1)
    for win in auto.GetRootControl().GetChildren():
        try:
            print(f"Name: {win.Name}, Class: {win.ClassName}")
            if "Control" in win.ClassName or "Quick" in win.Name or "Action" in win.ClassName:
                print(">>> MIGHT BE QUICK SETTINGS")
                for control, depth in auto.WalkControl(win, maxDepth=4):
                    print("  " * depth + f"{control.ControlTypeName}: {control.Name} ({control.AutomationId})")
        except:
            pass
    auto.SendKeys('{Win}a')

if __name__ == '__main__':
    inspect_windows()
