import comtypes.client
import time
import subprocess

# Load UIAutomationClient typelib
try:
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation, IUIAutomationElement, TreeScope_Children, TreeScope_Subtree
    uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
    root = uia.GetRootElement()
    print("IUIAutomation initialized successfully.")
    print("Root name:", root.CurrentName)
except Exception as e:
    print(f"Error initializing COM UIAutomation: {e}")
    root = None
    uia = None

if uia and root:
    print("\nPressing Win+A...")
    subprocess.run(["powershell", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys('^%{ESC}')"]) # non-win
    import uiautomation as auto
    auto.SendKeys('{Win}a')
    time.sleep(1.5)

    condition = uia.CreateTrueCondition()
    children = root.FindAll(TreeScope_Children, condition)
    print(f"Root.FindAll(TreeScope_Children) count: {children.Length}")
    for i in range(children.Length):
        elem = children.GetElement(i)
        try:
            print(f"[{i}] Name: '{elem.CurrentName}' | ClassName: '{elem.CurrentClassName}' | AutoId: '{elem.CurrentAutomationId}'")
        except Exception as ex:
            print(f"[{i}] Error: {ex}")

    time.sleep(1)
    auto.SendKeys('{Win}a')
