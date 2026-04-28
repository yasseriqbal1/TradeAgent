# TradeAgent - Docker launcher
# Prereq: Docker Desktop installed and running

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

if (-not (Test-Path "$root\.env")) {
    Write-Host "[ERROR] .env not found. Copy .env.template -> .env and fill values." -ForegroundColor Red
    exit 1
}

$tokenFile = Join-Path $root 'secrets\questrade_refresh_token.txt'
if (-not (Test-Path $tokenFile)) {
    Write-Host "[WARN] Questrade token file not found at: $tokenFile" -ForegroundColor Yellow
    Write-Host "       Create it (recommended) or run: .\update_questrade_token.ps1" -ForegroundColor Yellow
}

Write-Host "Building + starting services..." -ForegroundColor Cyan

# Lightweight default: pull prebuilt images (no local build)
& docker compose pull
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to pull one or more images." -ForegroundColor Red
    Write-Host "        If you see GHCR 403 Forbidden, your GitHub Packages images are not public." -ForegroundColor Yellow
    Write-Host "        Fix options:" -ForegroundColor Yellow
    Write-Host "          1) Make GHCR packages public (recommended for customers)" -ForegroundColor Yellow
    Write-Host "          2) Or run: docker login ghcr.io (then re-run this script)" -ForegroundColor Yellow
    Write-Host "        Dev fallback: docker compose up -d --build" -ForegroundColor Yellow
    exit 1
}
& docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] docker compose up failed." -ForegroundColor Red
    Write-Host "        Run: docker compose ps" -ForegroundColor Yellow
    Write-Host "        Then: docker compose logs --tail 200 dashboard" -ForegroundColor Yellow
    exit 1
}

Write-Host "\nDashboard: http://localhost:5000" -ForegroundColor Green
Write-Host "To start RSS news monitor too: docker compose --profile news up -d" -ForegroundColor Yellow
Write-Host "To start n8n too: docker compose --profile n8n up -d" -ForegroundColor Yellow

# Wait until the dashboard is reachable (first boot can take time)
$dashboardUrl = "http://localhost:5000"
$statusUrl = "$dashboardUrl/api/status"

Write-Host "Waiting for dashboard to be ready..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $statusUrl -TimeoutSec 2
        if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "[WARN] Dashboard is still starting (or port 5000 is blocked)." -ForegroundColor Yellow
    Write-Host "       Try again in ~30 seconds: $dashboardUrl" -ForegroundColor Yellow
    Write-Host "       Status: docker compose ps" -ForegroundColor Yellow
} else {
    Write-Host "Dashboard is ready: $dashboardUrl" -ForegroundColor Green
    Start-Process $dashboardUrl | Out-Null
}
