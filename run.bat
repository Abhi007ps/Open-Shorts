@echo off
setlocal enabledelayedexpansion
title OpenShorts Studio - AI Viral Clipping and Highlights
color 0b

echo =====================================================================
echo       OPENSHORTS STUDIO - AI HIGHLIGHTS AND VIRAL AUTO-CLIPPER
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Locate Python 3
set "PY_CMD="

python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :found_python
)

py --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto :found_python
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto :found_python
    )
)

for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto :found_python
    )
)

:found_python
if not defined PY_CMD (
    echo [ERROR] Python 3 was not found on your system!
    echo.
    echo Please install Python 3.10 or higher from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check the box:
    echo   "Add python.exe to PATH"
    echo during Python installation!
    echo.
    set /p "OPEN_PY=Would you like to open python.org now? [Y/N]: "
    if /i "!OPEN_PY!"=="Y" start https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment or use existing Python
set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if exist "%VENV_PY%" (
    set "ACTIVE_PY=%VENV_PY%"
    goto :check_deps
)

echo [*] Checking Python environment...
"!PY_CMD!" -c "import fastapi, uvicorn, pydantic, PIL" >nul 2>&1
if !errorlevel! equ 0 (
    set "ACTIVE_PY=!PY_CMD!"
    goto :check_deps
)

echo [*] Setting up isolated Python environment in .venv...
"!PY_CMD!" -m venv "%VENV_DIR%"
if exist "%VENV_PY%" (
    set "ACTIVE_PY=%VENV_PY%"
) else (
    set "ACTIVE_PY=!PY_CMD!"
)

:check_deps
:: 3. Verify / Install Dependencies
"!ACTIVE_PY!" -c "import fastapi, uvicorn, pydantic, PIL, aiofiles" >nul 2>&1
if !errorlevel! neq 0 (
    echo [*] Installing required packages: fastapi, uvicorn, pydantic, pillow, aiofiles...
    "!ACTIVE_PY!" -m pip install -r "%~dp0requirements.txt" --quiet
    if !errorlevel! neq 0 (
        echo [*] Retrying package installation with console output...
        "!ACTIVE_PY!" -m pip install -r "%~dp0requirements.txt"
    )
)

:: 4. Run Pre-flight System & Hardware Diagnostics
"!ACTIVE_PY!" "%~dp0backend\bootstrap.py"
if !errorlevel! neq 0 (
    echo [WARN] Bootstrap diagnostic encountered an issue, but attempting launch...
)

:: 5. Display Access URLs
echo.
echo =====================================================================
echo                     SERVER ACCESS URLS
echo =====================================================================
echo   [Local PC]    http://localhost:8000
echo   [Local PC]    http://127.0.0.1:8000
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        echo   [LAN Mobile]  http://%%b:8000
    )
)
echo                 [Access from any phone, laptop, or PC on this Wi-Fi]
echo =====================================================================
echo.

:: 6. Launch Web Browser
echo [*] Launching OpenShorts Studio in your default browser...
start "" "http://localhost:8000"

:: 7. Start Uvicorn Server
echo [*] Starting OpenShorts server on http://127.0.0.1:8000 ...
echo     [Keep this window open while using the Studio. Press Ctrl+C to stop.]
echo.
"!ACTIVE_PY!" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

pause
