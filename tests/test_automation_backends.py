from jarvis.automation.ufo_backend import UfoWindowsBackend
from jarvis.automation.browser_backend import BrowserUseBackend
from jarvis.automation.manager import AutomationManager

def test_backends_are_instantiable():
    ufo = UfoWindowsBackend()
    assert ufo is not None
    
    browser = BrowserUseBackend()
    assert browser is not None
    
    manager = AutomationManager()
    manager.register_windows_backend(ufo)
    manager.register_browser_backend(browser)
    assert manager is not None
    
    print("ALL BACKENDS INSTANTIABLE")

if __name__ == "__main__":
    test_backends_are_instantiable()
