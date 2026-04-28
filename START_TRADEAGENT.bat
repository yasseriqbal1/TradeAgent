@echo off
setlocal EnableExtensions

REM TradeAgent - 1-click starter (Docker)
REM Prereq: Docker Desktop must be installed and running.

cd /d "%~dp0"

echo ==============================================
echo TradeAgent (Docker) - Starting...
echo Folder: %cd%
echo ==============================================
echo.

docker info >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
  echo [ERROR] Docker is not running.
  echo.
  echo 1) Open Docker Desktop
  echo 2) Wait until it says Running
  echo 3) Double-click this file again
  echo.
  pause
  exit /b 1
)

powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0start_docker.ps1"

if not "%ERRORLEVEL%"=="0" (
  echo.
  echo [ERROR] Start failed. See messages above.
  pause
  exit /b %ERRORLEVEL%
)

echo.
echo [OK] TradeAgent start command completed.

echo Waiting for dashboard to be ready...
powershell -NoLogo -ExecutionPolicy Bypass -Command "$u='http://localhost:5000/api/status'; $ok=$false; for($i=0;$i -lt 60;$i++){ try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri $u; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){$ok=$true; break}} catch{}; Start-Sleep -Seconds 2 }; if($ok){exit 0}else{exit 1}"

if "%ERRORLEVEL%"=="0" (
  echo Opening dashboard in your browser...
  start "TradeAgent Dashboard" "http://localhost:5000"
) else (
  echo.
  echo [WARN] Dashboard is still starting (or port 5000 is blocked).
  echo        Wait 30-60 seconds, then double-click STATUS_TRADEAGENT.bat
  echo        Or open: http://localhost:5000
)

echo.
echo Current status:
docker compose ps

echo.
echo If the dashboard did not open, go to: http://localhost:5000
pause
