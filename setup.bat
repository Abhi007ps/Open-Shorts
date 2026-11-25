@echo off
setlocal
title OpenShorts Studio - First-Time 1-Click Setup
color 0b

echo =====================================================================
echo        OPENSHORTS STUDIO - FIRST-TIME 1-CLICK SETUP ^& LAUNCHER
echo =====================================================================
echo.
echo   This will automatically verify and install any missing components:
echo     - Python 3.10+ & isolated .venv packages
echo     - FFmpeg ^& FFprobe media engine
echo     - Whisper.cpp AI speech engine ^& hardware-matched model
echo     - Tier-gated Real-ESRGAN facecam upscaler (if discrete GPU)
echo     - Local Ollama AI + Qwen3 story brain (set OPENSHORTS_SKIP_OLLAMA=1 to skip)
echo.

:: Create Desktop shortcut on first run if missing
set "SHORTCUT=%USERPROFILE%\Desktop\OpenShorts Studio.lnk"
if not exist "%SHORTCUT%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%~dp0run.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'OpenShorts Studio Pro'; $s.Save()" >nul 2>&1
    if exist "%SHORTCUT%" (
        echo [OK] Created Desktop shortcut: OpenShorts Studio
        echo.
    )
)

call "%~dp0run.bat" %*
