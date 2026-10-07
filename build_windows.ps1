param([switch]$WithDjiSdk)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$taskOutput = Join-Path (Split-Path $PSScriptRoot -Parent) 'G29CockpitV4'
$taskWork = Join-Path $PSScriptRoot '..\..\work'
$taskGradleArgs = @(':app:assembleDebug', ':app:assembleDebugAndroidTest', ':app:lintDebug', '--console=plain')
if ($WithDjiSdk) { $taskGradleArgs = @('-PwithDjiSdk=true') + $taskGradleArgs }
Push-Location android
try {
    .\gradlew.bat @taskGradleArgs
    if ($LASTEXITCODE -ne 0) { throw "Budowa lub lint APK nie powiodły się" }
} finally { Pop-Location }
python -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Instalacja zależności nie powiodła się" }
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Testy nie przeszły" }
python -m PyInstaller --noconfirm --onefile --windowed --name G29CockpitV4 --distpath $taskOutput --workpath (Join-Path $taskWork 'pyinstaller-v4') --specpath $taskWork --add-data "$PSScriptRoot\config.json;." cockpit.py
if ($LASTEXITCODE -ne 0) { throw "Budowa EXE nie powiodła się" }
if (-not (Test-Path -LiteralPath (Join-Path $taskOutput 'config.json'))) {
    $taskConfig = if (Test-Path -LiteralPath 'dist\config.json') { 'dist\config.json' } else { 'config.json' }
    Copy-Item -LiteralPath $taskConfig -Destination (Join-Path $taskOutput 'config.json')
}
Copy-Item -LiteralPath 'android\app\build\outputs\apk\debug\app-debug.apk' -Destination (Join-Path $taskOutput 'G29Bridge.apk') -Force
if (-not (Test-Path -LiteralPath (Join-Path $taskOutput 'video')) -and (Test-Path -LiteralPath 'dist\video')) {
    Copy-Item -LiteralPath 'dist\video' -Destination (Join-Path $taskOutput 'video') -Recurse
}
Copy-Item -LiteralPath 'docs\START-V4.md' -Destination (Join-Path $taskOutput 'START-V4.md') -Force
Write-Host "Gotowy plik: $taskOutput\G29CockpitV4.exe. DJI SDK jest tylko do odczytu, sterowanie lotem wyłączone."
