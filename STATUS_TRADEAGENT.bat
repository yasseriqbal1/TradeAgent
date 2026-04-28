@echo off
setlocal EnableExtensions

REM TradeAgent - 1-click status checker (Docker)

cd /d "%~dp0"

echo ==============================================
echo TradeAgent (Docker) - Status
echo Folder: %cd%
echo ==============================================
echo.

docker info >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
  echo [ERROR] Docker is not running.
  echo Open Docker Desktop and wait until Running.
  echo.
  pause
  exit /b 1
)

echo Containers:
docker compose ps

echo.
for /f %%i in ('docker compose ps -q 2^>nul') do set HAS_CONTAINERS=1

if not defined HAS_CONTAINERS (
  echo [INFO] No containers are running right now.
  echo        Start it by double-clicking START_TRADEAGENT.bat
  echo.
  pause
  exit /b 0
)

echo Dashboard:
echo   Checking: http://localhost:5000
powershell -NoLogo -ExecutionPolicy Bypass -Command "try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri 'http://localhost:5000/api/status'; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){exit 0}else{exit 1}} catch {exit 1}"

if "%ERRORLEVEL%"=="0" (
  start "TradeAgent Dashboard" "http://localhost:5000"
) else (
  echo [WARN] Dashboard is not reachable yet.
  echo        If you just started TradeAgent, wait 30-60 seconds and try again.
  echo        If it keeps failing: docker compose logs --tail 200 dashboard
)

echo.
pause
