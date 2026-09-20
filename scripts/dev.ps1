# Root scripts for local development on Windows (PowerShell).

param(
    [ValidateSet("up", "down", "logs", "seed", "status", "ingest", "recalculate", "test", "build")]
    [string]$Task = "up"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Compose {
    param([string[]]$Arguments)
    & docker compose --project-directory $RepoRoot @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed: $($Arguments -join ' ')" }
}

switch ($Task) {
    "up"          { Invoke-Compose @("up", "--build", "-d"); Write-Host "`nFrontend http://localhost:3000  API http://localhost:8000/docs" }
    "down"        { Invoke-Compose @("down") }
    "logs"        { Invoke-Compose @("logs", "-f", "--tail", "100") }
    "seed"        { Invoke-Compose @("exec", "backend", "python", "-m", "app.cli", "seed") }
    "status"      { Invoke-Compose @("exec", "backend", "python", "-m", "app.cli", "status") }
    "ingest"      { Invoke-Compose @("exec", "backend", "python", "-m", "app.cli", "ingest") }
    "recalculate" { Invoke-Compose @("exec", "backend", "python", "-m", "app.cli", "recalculate") }
    "test"        { Invoke-Compose @("exec", "backend", "python", "-m", "pytest", "-q") }
    "build"       { Invoke-Compose @("build") }
}
