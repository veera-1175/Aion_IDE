# Start AION web UI (http://localhost:8090)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Virtual env missing. Run: .\scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}

$port = if ($args.Count -gt 0) { $args[0] } else { 8090 }
Write-Host "AION UI: http://127.0.0.1:$port" -ForegroundColor Cyan
$aion = Join-Path $Root ".venv\Scripts\aion.exe"
& $aion serve --port $port
