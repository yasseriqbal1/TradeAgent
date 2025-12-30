@echo off
REM TradeAgent - Start Services Script

echo ======================================
echo   TradeAgent Service Launcher
echo ======================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv venv
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Start FastAPI in background
echo Starting FastAPI service on http://127.0.0.1:8000...
start "TradeAgent FastAPI" cmd /k "python -m uvicorn quant_agent.service:app --host 127.0.0.1 --port 8000"

REM Wait for FastAPI to start
timeout /t 5 /nobreak >nul

REM Test FastAPI health
echo.
echo Testing FastAPI health endpoint...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] FastAPI is running
) else (
    echo [WARN] FastAPI may not be ready yet
)

echo.
echo ======================================
echo   Services Started
echo ======================================
echo.
echo FastAPI:  http://127.0.0.1:8000
echo n8n:      Run 'npx n8n' in another terminal
echo.
echo To stop: Close the FastAPI window or press Ctrl+C
echo.
pause
