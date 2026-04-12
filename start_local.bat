@echo off
setlocal

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

