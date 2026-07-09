# Sync backend/ → appsail/ksp-ai-backend/ and frontend/ → client/.
# Keeps the local dev layout as source of truth; the Catalyst directories
# are derived artefacts.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Write-Host "Preparing Catalyst layout under $root" -ForegroundColor Cyan

# ---- Backend → AppSail ----
$srcBE  = Join-Path $root "backend"
$destBE = Join-Path $root "appsail\ksp-ai-backend"
Write-Host "  backend/  → appsail/ksp-ai-backend/" -ForegroundColor Green

# Copy Python files (never overwrite Dockerfile / app-config.json).
$files = @("main.py","db.py","seed.py","llm.py","analytics.py","catalyst.py","jobs.py","requirements.txt")
foreach ($f in $files) {
    $src = Join-Path $srcBE $f
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $destBE $f)
    }
}

# .env is user-managed; copy .env.example so deployment can init one.
if (Test-Path (Join-Path $srcBE ".env.example")) {
    Copy-Item -Force (Join-Path $srcBE ".env.example") (Join-Path $destBE ".env.example")
}

# .dockerignore keeps venv / .env / DB out of the Docker build.
@"
.venv/
__pycache__/
*.pyc
*.db
.env
stratus_local/
"@ | Set-Content -Encoding utf8 (Join-Path $destBE ".dockerignore")

# ---- Frontend → client ----
$srcFE  = Join-Path $root "frontend"
$destFE = Join-Path $root "client"
Write-Host "  frontend/ → client/" -ForegroundColor Green

$feFiles = @("index.html","app.js","styles.css","config.js")
foreach ($f in $feFiles) {
    $src = Join-Path $srcFE $f
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $destFE $f)
    }
}

# Rewrite `/static/` prefixes (used by local dev's FastAPI mount) so the
# hosted client loads assets from the same directory.
$idx = Join-Path $destFE "index.html"
if (Test-Path $idx) {
    $c = Get-Content -Raw $idx
    $c = $c.Replace('href="/static/', 'href="./')
    $c = $c.Replace('src="/static/', 'src="./')
    $c | Set-Content -Encoding utf8 $idx
}

# ---- Frontend → AppSail webroot (single-URL mode) ----
# FastAPI in the AppSail container serves the UI at /static, so this copy
# keeps the /static/ prefixes as-is (no rewrite). One AppSail URL then
# serves both the API and the UI.
$destWeb = Join-Path $destBE "webroot"
New-Item -ItemType Directory -Force -Path $destWeb | Out-Null
Write-Host "  frontend/ → appsail/ksp-ai-backend/webroot/" -ForegroundColor Green
foreach ($f in $feFiles) {
    $src = Join-Path $srcFE $f
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $destWeb $f)
    }
}

Write-Host ""
Write-Host "Layout ready. Next:" -ForegroundColor Yellow
Write-Host "  1. catalyst login" -ForegroundColor Yellow
Write-Host "  2. catalyst init --force     # if you haven't linked a project yet" -ForegroundColor Yellow
Write-Host "  3. catalyst deploy --only client       # static UI, works immediately" -ForegroundColor Yellow
Write-Host "  4. Create AppSail in console, then: catalyst appsail:add; catalyst deploy --only appsail" -ForegroundColor Yellow
