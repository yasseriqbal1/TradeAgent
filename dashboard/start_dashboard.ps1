# Trading Dashboard - Startup Script (PowerShell)

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "TRADING DASHBOARD - STARTUP" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Yellow
& "..\venv\Scripts\Activate.ps1"

Write-Host "[2/3] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host "[3/3] Starting dashboard server..." -ForegroundColor Yellow

$port = [int]($env:DASHBOARD_PORT)
if (-not $port) { $port = 5000 }

try {
	$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
	if ($listening) {
		Write-Host "[OK] Dashboard already running on http://localhost:$port" -ForegroundColor Green
		exit 0
	}
} catch {
	# If we can't check ports, just try to start.
}
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host "Dashboard will open at: http://localhost:$port" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the dashboard" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""

$env:DASHBOARD_PORT = "$port"
python app.py
