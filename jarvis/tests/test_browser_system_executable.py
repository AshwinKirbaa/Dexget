from unittest.mock import patch

from jarvis.automation.browser_backend import (
    _installed_browser_path,
    _system_browser_launch_options,
)


def test_installed_browser_resolution_prefers_requested_browser():
    with patch("jarvis.automation.browser_backend.os.path.isfile") as isfile:
        isfile.side_effect = lambda path: bool(path and path.endswith("msedge.exe"))
        path = _installed_browser_path("edge")
    assert path and path.endswith("msedge.exe")


def test_generic_launch_always_passes_system_executable():
    with patch(
        "jarvis.automation.browser_backend._installed_browser_path",
        return_value=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ):
        options = _system_browser_launch_options("chrome")

    assert options["executable_path"].endswith("chrome.exe")
    assert options["headless"] is False
