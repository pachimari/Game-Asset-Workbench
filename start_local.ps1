[CmdletBinding()]
param(
    [switch]$Hidden
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$web = Join-Path $root 'web'
$run = Join-Path $root '.local\run'
$backendPidFile = Join-Path $run 'backend.pid'
$frontendPidFile = Join-Path $run 'frontend.pid'

function Resolve-Application {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$InstallHint
    )

    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) {
        throw "$Name was not found. $InstallHint"
    }

    return $command.Source
}

function Stop-StartedProcessTree {
    param(
        [System.Diagnostics.Process]$Process
    )

    if ($null -eq $Process) {
        return
    }

    & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
}

$python = Resolve-Application -Name 'python.exe' -InstallHint 'Install Python 3.9 or newer and enable the python command.'
$null = Resolve-Application -Name 'node.exe' -InstallHint 'Install Node.js 20.19 or newer, or 22.12 or newer.'
$npm = Resolve-Application -Name 'npm.cmd' -InstallHint 'Reinstall Node.js with npm enabled.'

New-Item -ItemType Directory -Force -Path $run | Out-Null
Remove-Item -LiteralPath $backendPidFile, $frontendPidFile -Force -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath (Join-Path $web 'node_modules'))) {
    Write-Host 'Installing frontend dependencies...'
    $install = Start-Process -FilePath $npm -ArgumentList @('install') -WorkingDirectory $web -Wait -PassThru -NoNewWindow
    if ($install.ExitCode -ne 0) {
        throw "npm install failed with exit code $($install.ExitCode)."
    }
}

$backend = $null
$frontend = $null
$previousPythonPath = $env:PYTHONPATH

try {
    $windowStyle = if ($Hidden) { 'Hidden' } else { 'Normal' }

    $env:PYTHONPATH = 'src'
    $backend = Start-Process `
        -FilePath $python `
        -ArgumentList @('-m', 'ai_icon_pipeline.api_launcher', '--reload') `
        -WorkingDirectory $root `
        -WindowStyle $windowStyle `
        -PassThru

    $frontend = Start-Process `
        -FilePath $npm `
        -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1') `
        -WorkingDirectory $web `
        -WindowStyle $windowStyle `
        -PassThru

    Start-Sleep -Seconds 1
    $backend.Refresh()
    $frontend.Refresh()

    if ($backend.HasExited) {
        throw "Backend exited during startup with exit code $($backend.ExitCode)."
    }
    if ($frontend.HasExited) {
        throw "Frontend exited during startup with exit code $($frontend.ExitCode)."
    }

    Set-Content -LiteralPath $backendPidFile -Value $backend.Id -Encoding Ascii
    Set-Content -LiteralPath $frontendPidFile -Value $frontend.Id -Encoding Ascii
}
catch {
    Stop-StartedProcessTree -Process $frontend
    Stop-StartedProcessTree -Process $backend
    Remove-Item -LiteralPath $backendPidFile, $frontendPidFile -Force -ErrorAction SilentlyContinue
    throw
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}

Write-Host ''
Write-Host 'Started backend on http://127.0.0.1:8000 and frontend on http://127.0.0.1:5173'
Write-Host 'You can now open http://127.0.0.1:5173/'
