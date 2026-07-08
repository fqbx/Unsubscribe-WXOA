# Refresh PATH for current PowerShell session and run the app
$adbPath = "C:\Users\MW\Downloads\platform-tools-latest-windows\platform-tools"
if ($env:Path -notlike "*$adbPath*") {
    $env:Path = "$adbPath;$env:Path"
}

Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    & .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
} else {
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "`nADB version:"
adb version
Write-Host "`nConnected devices:"
adb devices
Write-Host "`nStarting app..."
python main.py
