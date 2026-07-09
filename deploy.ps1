# One-shot deploy wrapper for Catalyst.
# Assumes: catalyst login already done (this session can't OAuth for you),
# and CATALYST_PROJECT_ID / CATALYST_PROJECT_KEY in your env or backend/.env.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host ""
Write-Host "=== KSP Crime AI · Catalyst deploy ===" -ForegroundColor Cyan
Write-Host ""

# --- Preflight ---
Write-Host "[1/5] Preflight checks" -ForegroundColor Yellow
try { catalyst whoami | Out-Null }
catch {
    Write-Host "  Not logged in. Run:  catalyst login  first." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ catalyst logged in as $(catalyst whoami)"

if (-not (Test-Path "$root\catalyst.json")) {
    Write-Host "  catalyst.json missing at repo root." -ForegroundColor Red
    exit 1
}

# --- Sync local layout → Catalyst dirs ---
Write-Host ""
Write-Host "[2/5] Syncing backend/ and frontend/ into Catalyst layout" -ForegroundColor Yellow
powershell.exe -ExecutionPolicy Bypass -File "$root\scripts\prepare-deploy.ps1"

# --- Data Store schema ---
Write-Host ""
Write-Host "[3/5] Data Store schema (skip if you've done this once)" -ForegroundColor Yellow
$doDs = Read-Host "  Create Data Store tables now? [y/N]"
if ($doDs -match '^[Yy]') {
    $seed = Read-Host "  Also seed synthetic data (~1800 FIRs)? [y/N]"
    $args = @()
    if ($seed -match '^[Yy]') { $args += "--seed" }
    & "$root\backend\.venv\Scripts\python.exe" "$root\scripts\create-datastore-tables.py" @args
}
else {
    Write-Host "  Skipped."
}

# --- Init if needed ---
Write-Host ""
Write-Host "[4/5] Catalyst project link" -ForegroundColor Yellow
if (-not (Test-Path "$root\.catalystrc")) {
    Write-Host "  No .catalystrc found — running 'catalyst init'." -ForegroundColor Cyan
    catalyst init --force
}
else {
    Write-Host "  ✓ project already linked (.catalystrc found)"
}

# --- Deploy ---
Write-Host ""
Write-Host "[5/5] Deploying appsail + client" -ForegroundColor Yellow
catalyst deploy --only appsail
catalyst deploy --only client

Write-Host ""
Write-Host "✓ Done. Check your Catalyst console for AppSail + Web Client URLs." -ForegroundColor Green
