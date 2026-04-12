@echo off
setlocal

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "RUN_DIR=%ROOT_DIR%\.local\run"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$run = [System.IO.Path]::GetFullPath('%RUN_DIR%');" ^
  "$pidFiles = @('backend.pid','frontend.pid');" ^
  "foreach ($name in $pidFiles) {" ^
  "  $path = Join-Path $run $name;" ^
  "  if (Test-Path $path) {" ^
  "    $pidValue = Get-Content $path -ErrorAction SilentlyContinue;" ^
  "    if ($pidValue) { Stop-Process -Id $pidValue -ErrorAction SilentlyContinue }" ^
  "    Remove-Item $path -Force -ErrorAction SilentlyContinue;" ^
  "  }" ^
  "}"

echo Stopped local backend and frontend processes.
