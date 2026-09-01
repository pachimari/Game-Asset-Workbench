@echo off
setlocal

set "HIDDEN_ARG="
if "%GAME_ASSET_WORKBENCH_HIDDEN%"=="1" set "HIDDEN_ARG=-Hidden"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_local.ps1" %HIDDEN_ARG%
if errorlevel 1 (
  echo.
  echo Failed to start Game Asset Workbench.
  echo Review the error above, then press any key to close this window.
  pause >nul
  exit /b 1
)

exit /b 0
