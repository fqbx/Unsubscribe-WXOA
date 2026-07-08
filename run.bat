@echo off
setlocal
set "ADB_DIR=C:\Users\MW\Downloads\platform-tools-latest-windows\platform-tools"
set "PATH=%ADB_DIR%;%PATH%"

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo ADB version:
adb version
echo.
echo Connected devices:
adb devices
echo.
echo Starting app...
python main.py
