@echo off
REM TradeAgent - Start Redis (Windows)
REM Safe to run alongside the trading bot; no-op if Redis is already listening.

set PORT=6379
if not "%REDIS_PORT%"=="" set PORT=%REDIS_PORT%

netstat -ano | findstr ":%PORT%" | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
  echo [OK] Redis already listening on port %PORT%
  exit /b 0
)

set REDIS_SERVER_EXE=%REDIS_SERVER_EXE%
if "%REDIS_SERVER_EXE%"=="" set REDIS_SERVER_EXE=C:\Users\training\Documents\Redis\redis-server.exe

if not exist "%REDIS_SERVER_EXE%" (
  echo [ERROR] redis-server.exe not found: %REDIS_SERVER_EXE%
  echo Set REDIS_SERVER_EXE to the full path, or install Redis/Memurai.
  exit /b 1
)

echo Starting Redis: %REDIS_SERVER_EXE% (port %PORT%)
"%REDIS_SERVER_EXE%" --port %PORT%
