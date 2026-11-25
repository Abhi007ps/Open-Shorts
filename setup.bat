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
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desk = [Environment]::GetFolderPath('Desktop'); " ^
    "$lnk = Join-Path $desk 'OpenShorts Studio.lnk'; " ^
    "if (-not (Test-Path $lnk)) { " ^
    "  $s = $ws.CreateShortcut($lnk); " ^
    "  $s.TargetPath = \"$env:SystemRoot\System32\wscript.exe\"; " ^
    "  $s.Arguments = '\"%~dp0launch_studio.vbs\"'; " ^
    "  $s.WorkingDirectory = '%~dp0'; " ^
    "  $ico = Get-ChildItem -Path '%~dp0assets' -Filter '*.ico' -ErrorAction SilentlyContinue | Select-Object -First 1; " ^
    "  if ($ico) { $s.IconLocation = $ico.FullName } else { $s.IconLocation = \"$env:SystemRoot\System32\imageres.dll,18\" }; " ^
    "  $s.Description = 'OpenShorts Studio - AI Highlights and Viral Auto-Clipper'; " ^
    "  $s.Save(); " ^
    "  Write-Host '[OK] Created Desktop shortcut: OpenShorts Studio'; " ^
    "}" >nul 2>&1

call "%~dp0run.bat" %*
