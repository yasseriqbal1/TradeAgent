@echo off
setlocal EnableExtensions

REM TradeAgent - 1-click stopper (Docker)

cd /d "%~dp0"

echo ==============================================
echo TradeAgent (Docker) - Stopping...
echo Folder: %cd%
echo ==============================================
echo.

docker info >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
  echo [ERROR] Docker is not running.
  echo If TradeAgent is not running, you can ignore this.
  echo.
  pause
  exit /b 1
)

docker compose stop

if not "%ERRORLEVEL%"=="0" (
  echo.
  echo [ERROR] Stop failed. See messages above.
  pause
  exit /b %ERRORLEVEL%
)

echo.
echo [OK] TradeAgent stopped (data preserved).
pause
