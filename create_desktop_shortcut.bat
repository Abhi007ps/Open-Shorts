@echo off
title Create OpenShorts Studio Desktop Shortcut
echo [*] Creating Desktop Shortcut for OpenShorts Studio...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desk = [Environment]::GetFolderPath('Desktop'); " ^
    "$s = $ws.CreateShortcut(\"$desk\OpenShorts Studio.lnk\"); " ^
    "$s.TargetPath = '%~dp0run.bat'; " ^
    "$s.WorkingDirectory = '%~dp0'; " ^
    "$s.Description = 'OpenShorts Studio - AI Highlights and Viral Auto-Clipper'; " ^
    "$s.Save(); " ^
    "Write-Host '[SUCCESS] Desktop shortcut created: ' $desk'\OpenShorts Studio.lnk' -ForegroundColor Green"

echo.
echo You can now start OpenShorts Studio directly from your Desktop icon!
echo.
pause
