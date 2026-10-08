param([switch]$WithDjiSdk)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$taskOutput = Join-Path (Split-Path $PSScriptRoot -Parent) 'G29CockpitV5'
$taskPrevious = Join-Path (Split-Path $PSScriptRoot -Parent) 'G29CockpitV4'
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
python -m PyInstaller --noconfirm --onefile --windowed --name G29CockpitV5 --distpath $taskOutput --workpath (Join-Path $taskWork 'pyinstaller-v5') --specpath $taskWork --add-data "$PSScriptRoot\config.json;." cockpit.py
if ($LASTEXITCODE -ne 0) { throw "Budowa EXE nie powiodła się" }
if (-not (Test-Path -LiteralPath (Join-Path $taskOutput 'config.json'))) {
    $taskConfig = if (Test-Path -LiteralPath (Join-Path $taskPrevious 'config.json')) { Join-Path $taskPrevious 'config.json' } elseif (Test-Path -LiteralPath 'dist\config.json') { 'dist\config.json' } else { 'config.json' }
    Copy-Item -LiteralPath $taskConfig -Destination (Join-Path $taskOutput 'config.json')
}
Copy-Item -LiteralPath 'android\app\build\outputs\apk\debug\app-debug.apk' -Destination (Join-Path $taskOutput 'G29Bridge.apk') -Force
if (-not (Test-Path -LiteralPath (Join-Path $taskOutput 'video'))) {
    $taskVideo = if (Test-Path -LiteralPath (Join-Path $taskPrevious 'video')) { Join-Path $taskPrevious 'video' } else { 'dist\video' }
    if (Test-Path -LiteralPath $taskVideo) { Copy-Item -LiteralPath $taskVideo -Destination (Join-Path $taskOutput 'video') -Recurse }
}
Copy-Item -LiteralPath 'docs\START-V5.md' -Destination (Join-Path $taskOutput 'START-V5.md') -Force
Copy-Item -LiteralPath 'AUDYT-V5.md' -Destination (Join-Path $taskOutput 'AUDYT-V5.md') -Force
Copy-Item -LiteralPath 'docs\USB-FIX-0.5.md' -Destination (Join-Path $taskOutput 'USB-FIX-0.5.md') -Force
foreach ($taskLicense in @('THIRD-PARTY.md', 'DJI-LICENSE.txt')) {
    $taskLicenseSource = if (Test-Path -LiteralPath $taskLicense) { $taskLicense } else { Join-Path $taskPrevious $taskLicense }
    if (Test-Path -LiteralPath $taskLicenseSource) { Copy-Item -LiteralPath $taskLicenseSource -Destination (Join-Path $taskOutput $taskLicense) -Force }
}
Write-Host "Gotowy plik: $taskOutput\G29CockpitV5.exe. DJI SDK jest tylko do odczytu, sterowanie lotem wyłączone. Wymagana zgoda na sesję na telefonie 0.6."
