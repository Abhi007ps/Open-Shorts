@echo off
title OpenShorts Studio - Clean Slate & Factory Reset
color 0e

echo =====================================================================
echo       OPENSHORTS STUDIO - FACTORY RESET / NEW USER CLEAN SLATE
echo =====================================================================
echo.
echo  This tool will safely remove:
echo   - All previous test clips, exports, and thumbnails
echo   - All previously uploaded videos and downloaded stream slices
echo   - All temporary audio files, frames, and session state
echo.
echo  This tool will PRESERVE:
echo   - All FFmpeg and Whisper AI binaries (bin/)
echo   - All pre-downloaded AI speech models (models/)
echo   - All core code, UI, and default presets
echo.
echo =====================================================================
set /p "CONFIRM=Are you sure you want to clean OpenShorts Studio for a new user? [Y/N]: "
if /i not "%CONFIRM%"=="Y" (
    echo.
    echo [CANCELLED] No files were changed.
    pause
    exit /b 0
)

echo.
cd /d "%~dp0"

:: Check python
set "PY_CMD=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    set "PY_CMD=py"
)

"%PY_CMD%" "%~dp0backend\reset_data.py"

echo.
echo [DONE] The studio is now completely brand new!
echo You can now zip this folder or share it with another user.
echo.
pause
