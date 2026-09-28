import os
import glob
import subprocess
import winreg
from typing import Dict, Any, Optional, Tuple, List
import psutil

try:
    import win32com.client
except ImportError:
    win32com = None

# Aliases
ALIASES = {
    "discord": "discord",
    "chrome": "google chrome",
    "google chrome": "google chrome",
    "brave": "brave",
    "vscode": "visual studio code",
    "vs code": "visual studio code",
    "code": "visual studio code",
    "notepad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "whatsapp": "whatsapp",
    "spotify": "spotify",
    "telegram": "telegram",
    "explorer": "file explorer",
    "file explorer": "file explorer",
    "terminal": "windows terminal",
    "powershell": "powershell",
    "cmd": "command prompt",
}

WEB_FALLBACKS = {
    "discord": "https://discord.com/app",
    "whatsapp": "https://web.whatsapp.com",
    "spotify": "https://open.spotify.com",
    "telegram": "https://web.telegram.org",
}

def resolve_application(name: str) -> str:
    """Normalize names based on aliases."""
    name = name.lower().strip()
    return ALIASES.get(name, name)

def get_web_fallback(normalized_name: str) -> Optional[str]:
    return WEB_FALLBACKS.get(normalized_name)

def check_running_process(app_name: str) -> Optional[str]:
    """Check if a process matching the app name is already running."""
    # Common process names mapped from app names
    proc_map = {
        "discord": ["discord.exe"],
        "google chrome": ["chrome.exe"],
        "brave": ["brave.exe"],
        "visual studio code": ["code.exe"],
        "notepad": ["notepad.exe"],
        "calculator": ["calculatorapp.exe", "calc.exe"],
        "whatsapp": ["whatsapp.exe"],
        "spotify": ["spotify.exe"],
        "telegram": ["telegram.exe"],
        "file explorer": ["explorer.exe"],
        "windows terminal": ["windowsterminal.exe"],
        "powershell": ["powershell.exe", "pwsh.exe"],
        "command prompt": ["cmd.exe"],
        "ms-settings:": ["systemsettings.exe"]
    }
    
    target_procs = proc_map.get(app_name, [f"{app_name.replace(' ', '')}.exe"])
    
    for proc in psutil.process_iter(['name', 'exe']):
        try:
            name = proc.info['name']
            if name and name.lower() in target_procs:
                return proc.info['exe']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def get_running_pids(app_name: str) -> list[int]:
    """Return all PIDs matching the app name."""
    proc_map = {
        "discord": ["discord.exe"],
        "google chrome": ["chrome.exe"],
        "brave": ["brave.exe"],
        "visual studio code": ["code.exe"],
        "notepad": ["notepad.exe"],
        "calculator": ["calculatorapp.exe", "calc.exe"],
        "whatsapp": ["whatsapp.exe"],
        "spotify": ["spotify.exe"],
        "telegram": ["telegram.exe"],
        "file explorer": ["explorer.exe"],
        "windows terminal": ["windowsterminal.exe"],
        "powershell": ["powershell.exe", "pwsh.exe"],
        "command prompt": ["cmd.exe"],
        "ms-settings:": ["systemsettings.exe"]
    }
    target_procs = proc_map.get(app_name, [f"{app_name.replace(' ', '')}.exe"])
    pids = []
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            name = proc.info['name']
            if name and name.lower() in target_procs:
                pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return pids

def search_start_menu(app_name: str) -> Optional[str]:
    """Search Start Menu shortcuts (.lnk)."""
    if not win32com:
        return None
        
    start_menu_paths = [
        os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(os.environ.get('PROGRAMDATA', ''), r'Microsoft\Windows\Start Menu\Programs')
    ]
    
    shell = win32com.client.Dispatch("WScript.Shell")
    app_name_lower = app_name.lower().replace(' ', '')
    
    for path in start_menu_paths:
        if not os.path.exists(path):
            continue
        for root, _, files in os.walk(path):
            for file in files:
                if file.lower().endswith('.lnk'):
                    # Match filename closely
                    clean_name = file.lower().replace('.lnk', '').replace(' ', '')
                    if app_name_lower in clean_name or clean_name in app_name_lower:
                        try:
                            shortcut = shell.CreateShortCut(os.path.join(root, file))
                            target = shortcut.Targetpath
                            if target and os.path.exists(target):
                                return target
                        except Exception:
                            pass
    return None

def search_registry(app_name: str) -> Optional[str]:
    """Search Uninstall registry keys."""
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    
    app_name_lower = app_name.lower().replace(' ', '')
    
    for hkey, subkey_path in keys:
        try:
            with winreg.OpenKey(hkey, subkey_path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub_key_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub_key_name) as sub_key:
                            try:
                                display_name = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                                if app_name_lower in display_name.lower().replace(' ', ''):
                                    # Try InstallLocation + standard exe
                                    try:
                                        install_loc = winreg.QueryValueEx(sub_key, "InstallLocation")[0]
                                        if install_loc and os.path.exists(install_loc):
                                            # Look for an exe matching the name in the directory
                                            for file in os.listdir(install_loc):
                                                if file.lower().endswith('.exe') and app_name_lower in file.lower():
                                                    return os.path.join(install_loc, file)
                                            # If not found, return the generic directory, but we ideally want the exe
                                    except OSError:
                                        pass
                                    
                                    # Try DisplayIcon
                                    try:
                                        icon_loc = winreg.QueryValueEx(sub_key, "DisplayIcon")[0]
                                        icon_path = icon_loc.split(',')[0].strip('"')
                                        if icon_path.lower().endswith('.exe') and os.path.exists(icon_path):
                                            return icon_path
                                    except OSError:
                                        pass
                            except OSError:
                                pass
                    except OSError:
                        pass
        except OSError:
            pass
    return None

def search_appx(app_name: str) -> Optional[str]:
    """Search Windows AppX packages."""
    # AppX apps don't have a direct .exe path you can just run normally (they use AppUserModelId),
    # but we can try to resolve it so we can run it via `explorer.exe shell:AppsFolder\...`
    try:
        # Just use powershell to search AppxPackages
        cmd = f"Get-AppxPackage | Where-Object {{$_.Name -match '{app_name.replace(' ', '')}'}} | Select-Object -ExpandProperty PackageFamilyName"
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            family_names = result.stdout.strip().splitlines()
            if family_names:
                # Typically the App ID is "App", but it can vary. We can return a special protocol or command.
                # Actually, running packaged apps is easier via `start shell:AppsFolder\PackageFamilyName!AppId`.
                # We don't know the exact AppId, but we can return the package name.
                # However, many common apps (like Calculator) have execution aliases (calc.exe).
                pass
    except Exception:
        pass
    return None

def search_known_locations(app_name: str) -> Optional[str]:
    """Search common program directories."""
    app_name_lower = app_name.lower().replace(' ', '')
    
    # We shouldn't recurse everything. Let's just look 2 levels deep in common folders.
    base_dirs = [
        os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
        os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs'),
        os.environ.get('APPDATA', '')
    ]
    
    for base in base_dirs:
        if not base or not os.path.exists(base):
            continue
        try:
            for item in os.listdir(base):
                item_path = os.path.join(base, item)
                if os.path.isdir(item_path):
                    if app_name_lower in item.lower().replace(' ', ''):
                        # Found a matching folder, look for exe inside
                        try:
                            for file in os.listdir(item_path):
                                if file.lower().endswith('.exe') and (app_name_lower in file.lower() or 'app' in file.lower()):
                                    return os.path.join(item_path, file)
                        except OSError:
                            pass
        except OSError:
            pass
            
    # Try finding it in PATH
    try:
        # Check standard path commands
        cmd_name = app_name_lower.replace(' ', '') + ".exe"
        res = subprocess.run(["where", cmd_name], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.splitlines()[0].strip()
    except Exception:
        pass
        
    return None

def find_installed_application(app_name: str, logger=None) -> Dict[str, Any]:
    """
    Priority:
    1. Check currently running
    2. Start Menu Shortcuts
    3. Registry
    4. Known Locations
    """
    normalized = resolve_application(app_name)
    
    if logger:
        logger(f"[APPLICATION] Resolving \"{app_name}\" to \"{normalized}\"")
        logger(f"[APPLICATION] Searching installed applications...")
    
    # 1. Running Process
    running_exe = check_running_process(normalized)
    if running_exe:
        if logger:
            logger(f"[APPLICATION] Found {normalized.title()} already running")
        return {"installed": True, "command": running_exe, "method": "running_process", "web_fallback": get_web_fallback(normalized)}
        
    # 2. Start Menu
    start_menu_exe = search_start_menu(normalized)
    if start_menu_exe:
        if logger:
            logger(f"[APPLICATION] Found {normalized.title()} via Start Menu shortcut")
        return {"installed": True, "command": start_menu_exe, "method": "start_menu", "web_fallback": get_web_fallback(normalized)}
        
    # 3. Registry
    registry_exe = search_registry(normalized)
    if registry_exe:
        if logger:
            logger(f"[APPLICATION] Found {normalized.title()} via Registry")
        return {"installed": True, "command": registry_exe, "method": "registry", "web_fallback": get_web_fallback(normalized)}
        
    # 4. Known Locations
    known_exe = search_known_locations(normalized)
    if known_exe:
        if logger:
            logger(f"[APPLICATION] Found {normalized.title()} in known locations")
        return {"installed": True, "command": known_exe, "method": "known_location", "web_fallback": get_web_fallback(normalized)}
        
    # Special cases for built-in windows apps
    if normalized == "calculator":
        return {"installed": True, "command": "calc.exe", "method": "builtin", "web_fallback": None}
    if normalized == "notepad":
        return {"installed": True, "command": "notepad.exe", "method": "builtin", "web_fallback": None}
    if normalized in ["file explorer", "explorer"]:
        return {"installed": True, "command": "explorer.exe", "method": "builtin", "web_fallback": None}
    if normalized == "command prompt":
        return {"installed": True, "command": "cmd.exe", "method": "builtin", "web_fallback": None}
    if normalized == "powershell":
        return {"installed": True, "command": "powershell.exe", "method": "builtin", "web_fallback": None}
    if normalized == "ms-settings:":
        return {"installed": True, "command": "ms-settings:", "method": "builtin", "web_fallback": None}
        
    return {"installed": False, "command": None, "method": None, "web_fallback": get_web_fallback(normalized)}
