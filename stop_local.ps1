[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$run = Join-Path $root '.local\run'
$targets = @(
    @{ Name = 'backend.pid'; Marker = 'ai_icon_pipeline.api_launcher' },
    @{ Name = 'frontend.pid'; Marker = 'npm' }
)

$stopped = 0
foreach ($target in $targets) {
    $path = Join-Path $run $target.Name
    if (-not (Test-Path -LiteralPath $path)) {
        continue
    }

    $rawPid = [string](Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue)
    $rawPid = $rawPid.Trim()
    $processId = 0
    if (-not [int]::TryParse($rawPid, [ref]$processId)) {
        Write-Warning "Ignoring invalid PID file: $path"
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        continue
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        continue
    }

    if ($process.CommandLine -notlike "*$($target.Marker)*") {
        Write-Warning "PID $processId no longer belongs to Game Asset Workbench; it was not stopped."
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        continue
    }

    & taskkill.exe /PID $processId /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop process tree $processId."
    }

    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    $stopped++
}

if ($stopped -eq 0) {
    Write-Host 'Game Asset Workbench is not running.'
} else {
    Write-Host 'Stopped local backend and frontend processes.'
}
