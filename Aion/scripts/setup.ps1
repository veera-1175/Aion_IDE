# AION setup (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== AION Setup ===" -ForegroundColor Cyan

$noesis = Join-Path (Split-Path -Parent $Root) "Noesis_v1"
if (-not (Test-Path $noesis)) {
    Write-Error "Noesis_v1 not found at $noesis"
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q
& .\.venv\Scripts\python.exe -m pip install -e $noesis -q
& .\.venv\Scripts\python.exe -m pip install -e ".[llm]" -q

New-Item -ItemType Directory -Force -Path "data", "workspace" | Out-Null
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "  Activate:  .\.venv\Scripts\Activate.ps1"
Write-Host "  Web UI:    aion serve   (or: .\scripts\serve.ps1)"
Write-Host "  Demo:      aion demo"
Write-Host "  Tests:     pytest tests\ -v"
