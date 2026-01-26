# TradeAgent - Start Redis (PowerShell)
# Safe to run alongside the trading bot; no-op if Redis is already listening.

$port = [int]($env:REDIS_PORT)
if (-not $port) { $port = 6379 }

try {
    $listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listening) {
        Write-Host "[OK] Redis already listening on port $port" -ForegroundColor Green
        exit 0
    }
} catch {
    # If we can't check ports, we'll try to start anyway.
}

$redisExe = $env:REDIS_SERVER_EXE
if (-not $redisExe -or -not (Test-Path $redisExe)) {
    $redisExe = "C:\Users\training\Documents\Redis\redis-server.exe"
}

if (-not (Test-Path $redisExe)) {
    Write-Host "[ERROR] redis-server.exe not found." -ForegroundColor Red
    Write-Host "Set REDIS_SERVER_EXE to the full path, or install Redis/Memurai." -ForegroundColor Yellow
    Write-Host "Example: $env:REDIS_SERVER_EXE=\"C:\\Path\\to\\redis-server.exe\"" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting Redis: $redisExe (port $port)" -ForegroundColor Yellow
& $redisExe --port $port
