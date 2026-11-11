param([switch]$SkipExeBuild)

$ErrorActionPreference = "Stop"

$pythonCandidates = @(
    "$env:USERPROFILE\AppData\Local\Programs\Python\Python311-arm64\python.exe",
    "$env:USERPROFILE\AppData\Local\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311-arm64\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    (Get-Command python.exe -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$pythonExe = $pythonCandidates | Select-Object -First 1
if (-not $pythonExe) { throw "A usable Python installation could not be found." }

$pythonArch = if ($pythonExe -match "arm64") { "arm64" } elseif ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
$packageArch = if ($pythonArch -eq "arm64") { "arm64" } else { "x64" }
Write-Host "Building for $packageArch using Python architecture $pythonArch"

if (-not $SkipExeBuild) {
    Write-Host "1. Building EXE with PyInstaller..."
    & $pythonExe build.py
} else {
    Write-Host "1. Using existing ARM64 EXE..."
    if (-not (Test-Path "dist\JarvisAgent.exe")) {
        throw "dist\JarvisAgent.exe does not exist. Run without -SkipExeBuild first."
    }
}

Write-Host "2. Creating MSIX layout..."
$msixDir = "dist\msix_content"
if (Test-Path $msixDir) { Remove-Item -Recurse -Force $msixDir }
New-Item -ItemType Directory -Path $msixDir | Out-Null

Copy-Item "dist\JarvisAgent.exe" -Destination $msixDir

# Copy .env so the packaged app can read it from beside the .exe
if (Test-Path ".env") {
    Copy-Item ".env" -Destination $msixDir
    Write-Host "   -> Copied .env alongside exe"
} else {
    Write-Host "   WARNING: .env not found - Fish Audio TTS will fall back to Windows TTS"
}

Write-Host "3. Generating Assets..."
& $pythonExe create_assets.py

Write-Host "4. Creating AppxManifest.xml..."
$manifest = @"
<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:uap3="http://schemas.microsoft.com/appx/manifest/uap/windows10/3"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  xmlns:desktop="http://schemas.microsoft.com/appx/manifest/desktop/windows10">

  <Identity Name="JarvisAI" Publisher="CN=JarvisDev" Version="1.0.136.0" ProcessorArchitecture="$packageArch"/>
  
  <Properties>
    <DisplayName>JARVIS</DisplayName>
    <PublisherDisplayName>JarvisDev</PublisherDisplayName>
    <Logo>Assets\Square44x44Logo.png</Logo>
    <Description>JARVIS AI desktop assistant</Description>
  </Properties>

  <Resources>
    <Resource Language="en-US"/>
  </Resources>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.22000.0" MaxVersionTested="10.0.22621.0"/>
  </Dependencies>

  <Capabilities>
    <uap3:Capability Name="userNotificationListener"/>
    <Capability Name="internetClient"/>
    <Capability Name="privateNetworkClientServer"/>
    <rescap:Capability Name="runFullTrust"/>
    <DeviceCapability Name="microphone"/>
    <DeviceCapability Name="webcam"/>
  </Capabilities>

  <Applications>
    <Application Id="JarvisApp"
                 Executable="JarvisAgent.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="JARVIS"
        Description="JARVIS AI desktop assistant"
        Square150x150Logo="Assets\Square150x150Logo.png"
        Square44x44Logo="Assets\Square44x44Logo.png"
        BackgroundColor="#000000" />
      <Extensions>
        <uap3:Extension Category="windows.appExtension">
          <uap3:AppExtension
              Name="com.microsoft.windows.copilotkeyprovider"
              Id="JarvisCopilotProvider"
              DisplayName="JARVIS"
              Description="JARVIS AI desktop assistant"
              PublicFolder="Public" />
        </uap3:Extension>
      </Extensions>
    </Application>
  </Applications>
</Package>
"@

Set-Content -Path "$msixDir\AppxManifest.xml" -Value $manifest -Encoding UTF8

Write-Host "5. Creating Certificate..."
$cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object {
    $_.Subject -eq "CN=JarvisDev" -and $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date)
} | Sort-Object NotBefore | Select-Object -First 1
if (-Not $cert) {
    $cert = New-SelfSignedCertificate -Type Custom -Subject "CN=JarvisDev" -KeyUsage DigitalSignature -FriendlyName "Jarvis Dev Cert" -CertStoreLocation "Cert:\CurrentUser\My" -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")

    # Trust only the newly created development certificate for CurrentUser.
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store "Root", "CurrentUser"
    $store.Open("ReadWrite")
    $store.Add($cert)
    $store.Close()
}
Write-Host "   -> Signing certificate: $($cert.Thumbprint)"

Write-Host "6. Packing MSIX..."
$makeappx = (Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter "makeappx.exe" | Where-Object { $_.FullName -like "*\$packageArch\*" } | Sort-Object FullName -Descending | Select-Object -First 1).FullName
& $makeappx pack -d $msixDir -p dist\JarvisCopilot.msix -o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE" }

Write-Host "7. Signing MSIX..."
$signtool = (Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter "signtool.exe" | Where-Object { $_.FullName -like "*\$packageArch\*" } | Sort-Object FullName -Descending | Select-Object -First 1).FullName
& $signtool sign /fd SHA256 /sha1 $cert.Thumbprint /s My dist\JarvisCopilot.msix
if ($LASTEXITCODE -ne 0) { throw "signtool failed with exit code $LASTEXITCODE" }

Write-Host ""
Write-Host "Build complete!"
Write-Host "Package output path: dist\JarvisCopilot.msix"
Write-Host "Certificate used: $($cert.Thumbprint) from CurrentUser\My"
Write-Host ""
Write-Host "To install, run:"
Write-Host "Add-AppxPackage -Path dist\JarvisCopilot.msix"
