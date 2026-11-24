@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "GIT="
if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if not defined GIT set "GIT=git"

echo ===================================================
echo     OpenShorts Studio - One-Click GitHub Sync
echo ===================================================
echo.

echo [1/3] Staging all tracked changes...
"%GIT%" add .

echo [2/3] Committing with timestamp...
"%GIT%" commit -m "update: %DATE% %TIME%"

echo [3/3] Pushing to GitHub (origin main)...
"%GIT%" push origin main

echo.
echo ===================================================
echo     Sync Complete! View at:
echo     https://github.com/Abhi007ps/Open-Shorts
echo ===================================================
echo.
pause
