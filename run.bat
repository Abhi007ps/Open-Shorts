@echo off
setlocal enabledelayedexpansion
title OpenShorts Studio - AI Viral Clipping and Highlights
color 0b

echo =====================================================================
echo       OPENSHORTS STUDIO - AI HIGHLIGHTS AND VIRAL AUTO-CLIPPER
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Locate Python 3.10+ (validating against Windows Store alias stubs)
set "PY_CMD="
call :scan_python

if not defined PY_CMD (
    where winget >nul 2>&1
    if !errorlevel! equ 0 (
        echo [*] Python 3.10+ not found. Installing Python 3.12 automatically via winget...
        winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        call :scan_python
    )
)

if not defined PY_CMD (
    echo [ERROR] Python 3.10 or higher was not found on your system!
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
goto :after_python

:scan_python
for /f "delims=" %%P in ('python -c "import sys; print(sys.executable) if sys.version_info >= (3, 10) else sys.exit(1)" 2^>nul') do (
    if exist "%%P" (
        set "PY_CMD=%%P"
        exit /b 0
    )
)
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable) if sys.version_info >= (3, 10) else sys.exit(1)" 2^>nul') do (
    if exist "%%P" (
        set "PY_CMD=%%P"
        exit /b 0
    )
)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_CMD=%%D\python.exe"
            exit /b 0
        )
    )
)
for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%D\python.exe" (
        "%%D\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_CMD=%%D\python.exe"
            exit /b 0
        )
    )
)
exit /b 1

:after_python

:: 2. Always Create / Use Isolated Virtual Environment (.venv)
set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if exist "%VENV_PY%" (
    set "ACTIVE_PY=%VENV_PY%"
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
"!ACTIVE_PY!" -c "import fastapi, uvicorn, pydantic, PIL, aiofiles, yt_dlp" >nul 2>&1
if !errorlevel! neq 0 (
    echo [*] Installing required packages: fastapi, uvicorn, pydantic, pillow, aiofiles, yt-dlp...
    "!ACTIVE_PY!" -m pip install -r "%~dp0requirements.txt" --quiet
    if !errorlevel! neq 0 (
        echo [*] Retrying package installation with console output...
        "!ACTIVE_PY!" -m pip install -r "%~dp0requirements.txt"
    )
)

:: 4. Run Pre-flight System, Zero-Touch Setup & Hardware Diagnostics
"!ACTIVE_PY!" "%~dp0backend\bootstrap.py" --setup
if !errorlevel! neq 0 (
    echo [WARN] Bootstrap diagnostic encountered an issue, but attempting launch...
)

:: Parse arguments for LAN mode
set "IS_LAN=0"
if /i "%~1"=="--lan" set "IS_LAN=1"
if /i "%~2"=="--lan" set "IS_LAN=1"

if "!IS_LAN!"=="1" (
    set "OPENSHORTS_LAN=1"
    set "HOST_BIND=0.0.0.0"
) else (
    set "OPENSHORTS_LAN=0"
    set "HOST_BIND=127.0.0.1"
)

:: 5. Display Access URLs
echo.
echo =====================================================================
echo                     SERVER ACCESS URLS
echo =====================================================================
echo   [Local PC]    http://localhost:8000
echo   [Local PC]    http://127.0.0.1:8000
if "!IS_LAN!"=="1" (
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
        for /f "tokens=1" %%b in ("%%a") do (
            echo   [LAN Mobile]  http://%%b:8000
        )
    )
    echo                 [LAN mode enabled: Access from any phone or PC on Wi-Fi]
) else (
    echo.
    echo   Tip: Run "run.bat --lan" to enable Wi-Fi / mobile LAN access across your local network
)
echo =====================================================================
echo.

:: 6. Launch Web Browser
echo [*] Launching OpenShorts Studio in your default browser...
start "" "http://localhost:8000"

:: 7. Start Uvicorn Server
if "!IS_LAN!"=="1" (
    echo [*] Starting OpenShorts server on http://0.0.0.0:8000 [LAN Enabled]...
) else (
    echo [*] Starting OpenShorts server on http://127.0.0.1:8000 [Localhost Only]...
)
echo     [Keep this window open while using the Studio. Press Ctrl+C to stop.]
echo.
"!ACTIVE_PY!" -m uvicorn backend.main:app --host !HOST_BIND! --port 8000

pause
