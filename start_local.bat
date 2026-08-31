@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.9 or newer and enable the python command.
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Install Node.js 20.19 or newer, or 22.12 or newer.
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js with npm enabled.
  exit /b 1
)

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "RUN_DIR=%ROOT_DIR%\.local\run"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = [System.IO.Path]::GetFullPath('%ROOT_DIR%');" ^
  "$run = Join-Path $root '.local\\run';" ^
  "New-Item -ItemType Directory -Force -Path $run | Out-Null;" ^
  "$backend = Start-Process cmd.exe -ArgumentList '/k','cd /d ""' + $root + '"" && set PYTHONPATH=src && python -m ai_icon_pipeline.api_launcher --reload' -PassThru;" ^
  "Set-Content -Path (Join-Path $run 'backend.pid') -Value $backend.Id;" ^
  "$frontend = Start-Process cmd.exe -ArgumentList '/k','cd /d ""' + (Join-Path $root 'web') + '"" && if not exist node_modules npm install && npm run dev -- --host 127.0.0.1' -PassThru;" ^
  "Set-Content -Path (Join-Path $run 'frontend.pid') -Value $frontend.Id"

echo.
echo Started backend on http://127.0.0.1:8000 and frontend on http://127.0.0.1:5173
echo You can now open http://127.0.0.1:5173/
