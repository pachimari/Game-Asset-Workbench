@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_local.ps1"
if errorlevel 1 (
  echo.
  echo Failed to stop Game Asset Workbench cleanly.
  echo Review the error above, then press any key to close this window.
  pause >nul
  exit /b 1
)

exit /b 0
