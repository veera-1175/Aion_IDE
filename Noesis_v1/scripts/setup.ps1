# Noesis Setup Script (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== Noesis Setup ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\pip install -r requirements.txt -e ".[api,dev]" -q

New-Item -ItemType Directory -Force -Path "data" | Out-Null
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "  Activate:  .\.venv\Scripts\Activate.ps1"
Write-Host "  Dashboard: python scripts\run_server.py"
Write-Host "  Demo:      python examples\innovation_demo.py"
Write-Host "  Tests:     pytest tests\ -v"
