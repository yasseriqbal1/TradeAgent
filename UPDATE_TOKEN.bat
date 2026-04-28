@echo off
setlocal EnableExtensions

REM TradeAgent - 1-click token updater (Docker)

cd /d "%~dp0"

echo ==============================================
echo TradeAgent (Docker) - Update Questrade Token
echo ==============================================
echo.

docker info >nul 2>nul
if not "%ERRORLEVEL%"=="0" (
  echo [WARN] Docker is not running.
  echo You can still save the token, but the bot restart will fail.
  echo.
)

powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0update_questrade_token.ps1"

if not "%ERRORLEVEL%"=="0" (
  echo.
  echo [ERROR] Token update failed. See messages above.
  pause
  exit /b %ERRORLEVEL%
)

echo.
echo [OK] Token updated.
pause
