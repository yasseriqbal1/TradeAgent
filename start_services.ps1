# TradeAgent - Start Services (PowerShell)

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   TradeAgent Service Launcher" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run: python -m venv venv" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Start FastAPI in background
Write-Host "Starting FastAPI service on http://127.0.0.1:8000..." -ForegroundColor Yellow
$fastapi = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & .\venv\Scripts\Activate.ps1
    python -m uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000
}

# Wait for FastAPI to start
Write-Host "Waiting for FastAPI to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Test FastAPI health
Write-Host ""
Write-Host "Testing FastAPI health endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "[OK] FastAPI is running" -ForegroundColor Green
    Write-Host ""
    $health = $response.Content | ConvertFrom-Json
    Write-Host "Status: $($health.status)" -ForegroundColor Green
    Write-Host "Environment: $($health.environment)" -ForegroundColor Green
    Write-Host "Universe: $($health.config.universe_size) stocks" -ForegroundColor Green
} catch {
    Write-Host "[WARN] FastAPI health check failed: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   Services Started" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "FastAPI:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Docs:     http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "To start n8n, open another terminal and run:" -ForegroundColor Yellow
Write-Host "  npx n8n" -ForegroundColor White
Write-Host ""
Write-Host "FastAPI Job ID: $($fastapi.Id)" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop FastAPI:" -ForegroundColor Yellow
Write-Host "  Stop-Job -Id $($fastapi.Id); Remove-Job -Id $($fastapi.Id)" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to exit this script (FastAPI will keep running)" -ForegroundColor Yellow
Write-Host ""

# Keep script running
try {
    while ($true) {
        Start-Sleep -Seconds 10
        $jobState = (Get-Job -Id $fastapi.Id).State
        if ($jobState -ne "Running") {
            Write-Host "[ERROR] FastAPI stopped unexpectedly!" -ForegroundColor Red
            Receive-Job -Id $fastapi.Id
            break
        }
    }
} finally {
    Write-Host ""
    Write-Host "Cleaning up..." -ForegroundColor Yellow
}
