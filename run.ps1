# One-command launcher for the KSP Crime AI demo.
# From project root: .\run.ps1
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot\backend
try {
    if (-not (Test-Path .venv)) {
        Write-Host "Creating virtualenv..." -ForegroundColor Cyan
        python -m venv .venv
    }
    & .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt

    if (-not (Test-Path .env)) {
        Write-Host "No backend\.env found — copying from .env.example (fallback mode)." -ForegroundColor Yellow
        Copy-Item .env.example .env
    }

    Write-Host ""
    Write-Host "Starting KSP Crime AI at http://localhost:8000" -ForegroundColor Green
    Write-Host ""
    & .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
}
finally {
    Pop-Location
}
