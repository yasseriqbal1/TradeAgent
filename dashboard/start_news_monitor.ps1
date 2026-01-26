# News Monitor - Startup Script (PowerShell)

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "NEWS MONITOR - RSS -> REDIS ALERTS" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] Activating virtual environment..." -ForegroundColor Yellow
& "..\venv\Scripts\Activate.ps1"

Write-Host "[2/2] Starting news monitor..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Config via env vars (.env is loaded by the script):" -ForegroundColor Gray
Write-Host "  NEWS_RSS_URLS=... (comma-separated)" -ForegroundColor Gray
Write-Host "  WATCHLIST_TICKERS=... (optional)" -ForegroundColor Gray
Write-Host "  NEWS_POLL_SECONDS=60" -ForegroundColor Gray
Write-Host ""

python news_monitor.py
