import uiautomation as auto
import time

def inspect_quick_settings():
    # Press Win+A
    auto.SendKeys('{Win}a')
    time.sleep(1) # wait for panel to open
    
    # Try to find the Quick Settings window
    # ClassName is usually 'Windows.UI.Core.CoreWindow' or 'ControlCenterWindow' or something like that
    desktop = auto.GetRootControl()
    quick_settings = desktop.WindowControl(ClassName='ControlCenterWindow')
    if not quick_settings.Exists(0):
        quick_settings = desktop.WindowControl(Name='Quick settings')
        if not quick_settings.Exists(0):
            print("Could not find Quick Settings window")
            return
            
    print("Found Quick Settings:", quick_settings)
    for control, depth in auto.WalkControl(quick_settings):
        # We only care about buttons or toggles
        if control.ControlType in [auto.ControlType.ButtonControl, auto.ControlType.CheckBoxControl, auto.ControlType.ListItemControl, auto.ControlType.SliderControl]:
            try:
                name = control.Name
                c_type = control.ControlTypeName
                auto_id = control.AutomationId
                is_enabled = control.IsEnabled
                toggle_state = ""
                if hasattr(control, 'CurrentToggleState'):
                    try:
                        toggle_state = control.CurrentToggleState()
                    except:
                        pass
                print(f"[{c_type}] Name: {name}, AutomationId: {auto_id}, IsEnabled: {is_enabled}, ToggleState: {toggle_state}")
            except Exception as e:
                pass
                
    auto.SendKeys('{Win}a') # close

if __name__ == '__main__':
    inspect_quick_settings()
