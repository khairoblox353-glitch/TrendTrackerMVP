# Start the Next.js dev server against a locally running backend.
#
#   .\scripts\dev-frontend.ps1
#
# Expects the backend at http://localhost:8000 (see scripts/dev-backend.ps1).

$ErrorActionPreference = "Stop"
$FrontendRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "frontend"

if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $FrontendRoot
    try { & npm.cmd install --no-audit --no-fund }
    finally { Pop-Location }
}

# The browser never calls the API directly, so the server-side base URL is the only one
# that matters. Override it here rather than in a committed file.
$env:API_BASE_URL = $env:API_BASE_URL ?? "http://localhost:8000"

Push-Location $FrontendRoot
try {
    & npm.cmd run dev
}
finally {
    Pop-Location
}
