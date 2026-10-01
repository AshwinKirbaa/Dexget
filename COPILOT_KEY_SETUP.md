# Copilot Key Setup for JARVIS

This document explains how to package the existing JARVIS widget so that it registers as a Copilot Hardware Key Provider in Windows.

## 1. Prerequisites
- Windows 11 with the Copilot hardware key (or Win + C).
- Windows 10 SDK (for `makeappx.exe` and `signtool.exe`, usually located at `C:\Program Files (x86)\Windows Kits\10\bin\...`).
- Python and required dependencies (already configured for JARVIS).

## 2. Build and Package
A PowerShell script is provided to automate the entire process:
1. Building the standalone `.exe` using PyInstaller.
2. Creating the MSIX layout and AppxManifest.
3. Creating default icon assets.
4. Packaging into a `.msix` file.
5. Creating a self-signed developer certificate.
6. Signing the package.

Open an administrator PowerShell prompt in the JARVIS project root and run:
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_copilot_package.ps1
```

## 3. Installation
The script will output `dist\JarvisCopilot.msix`. To install the package natively into Windows, run:
```powershell
Add-AppxPackage -Path dist\JarvisCopilot.msix
```

> **Note**: The build script attempts to install the self-signed certificate into your `CurrentUser` Trusted Root store automatically. If Windows blocks the installation saying the certificate is untrusted, you may need to manually double-click `dist\JarvisDev.pfx` and install it into "Trusted Root Certification Authorities".

## 4. Selecting JARVIS as the Copilot Key
1. Open Windows **Settings**.
2. Go to **Bluetooth & devices** -> **Keyboard**.
3. Under **Customize Copilot key on keyboard**, you will see a dropdown list.
4. Select **JARVIS** from the list.

## 5. Testing the Key
1. Press the physical Copilot key on your keyboard.
2. **JARVIS** will launch as the main desktop widget.
3. If JARVIS is already open, pressing the key again will bring the widget to the foreground and focus it instead of launching a second instance.

## 6. Uninstall / Reinstall
To completely uninstall the JARVIS package from Windows:
```powershell
Get-AppxPackage JarvisAI | Remove-AppxPackage
```

If you make code changes to JARVIS, uninstall it using the command above, run `.\build_copilot_package.ps1` again, and then install it with `Add-AppxPackage`.

## Troubleshooting
- **JARVIS does not appear in the Settings dropdown**: Ensure that `Add-AppxPackage` succeeded without errors and that you are on a recent Windows build that supports the Copilot key configuration.
- **Activation opens a blank window or fails**: Verify that your `start_app.py` executable runs correctly without packaging. The MSIX uses `runFullTrust` to execute exactly as it would as a standard desktop application.
- **Multiple Instances**: The packaging uses `QLocalServer`/`QLocalSocket` to enforce single-instance activation. If multiple instances appear, verify that the local socket `JarvisWidgetInstance` is not blocked or closed unexpectedly.
