# Start the backend with autoreload against a local PostgreSQL.
#
#   .\scripts\dev-backend.ps1
#
# Requires the `db` service to be running (`docker compose up -d db`) and a `.env`
# with DATABASE_URL pointing at localhost.

$ErrorActionPreference = "Stop"
$BackendRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"

$python = Join-Path $BackendRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating the backend virtualenv..."
    python -m venv (Join-Path $BackendRoot ".venv")
    & $python -m pip install --quiet --upgrade pip
    & $python -m pip install --quiet -r (Join-Path $BackendRoot "requirements-dev.txt")
}

# `backend/app` must be importable, so run from the backend directory.
Push-Location $BackendRoot
try {
    & $python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
}
finally {
    Pop-Location
}
