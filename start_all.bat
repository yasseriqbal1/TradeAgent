@echo off
REM TradeAgent - Start Everything (CMD)

set ROOT=%~dp0

REM Prefer .venv, fallback to venv
set PY=%ROOT%.venv\Scripts\python.exe
if not exist "%PY%" set PY=%ROOT%venv\Scripts\python.exe

if not exist "%PY%" (
  echo ERROR: No venv python found. Expected .venv\Scripts\python.exe or venv\Scripts\python.exe
  pause
  exit /b 1
)

echo Starting Redis...
start "TradeAgent - Redis" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%ROOT%'; .\start_redis.ps1"

echo Starting n8n...
start "TradeAgent - n8n" cmd /k "cd /d %ROOT% & npx n8n"

echo Starting bot...
start "TradeAgent - Bot" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%ROOT%'; & '%PY%' test_live_1hour_questrade.py"

echo Starting dashboard...
start "TradeAgent - Dashboard" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath '%ROOT%dashboard'; $env:DASHBOARD_DEBUG='false'; & '%PY%' app.py"

echo.
echo Launched. Close the spawned windows to stop services.
