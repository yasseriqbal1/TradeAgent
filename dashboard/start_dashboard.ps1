# Trading Dashboard - Startup Script (PowerShell)

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "TRADING DASHBOARD - STARTUP" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Yellow
& "..\venv\Scripts\Activate.ps1"

Write-Host "[2/3] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

Write-Host "[3/3] Starting dashboard server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "Dashboard will open at: http://localhost:5000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the dashboard" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""

python app.py
