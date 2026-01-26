@echo off
echo ================================================================================
echo TRADING DASHBOARD - STARTUP
echo ================================================================================
echo.
echo [1/3] Activating virtual environment...
call ..\venv\Scripts\activate.bat

echo [2/3] Installing dependencies...
pip install -r requirements.txt

set PORT=5000
if not "%DASHBOARD_PORT%"=="" set PORT=%DASHBOARD_PORT%

REM If port is already listening, assume dashboard is already running.
netstat -ano | findstr ":%PORT%" | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
	echo [OK] Dashboard already running on http://localhost:%PORT%
	exit /b 0
)

echo [3/3] Starting dashboard server...
echo.
echo ================================================================================
echo Dashboard will open at: http://localhost:%PORT%
echo Press Ctrl+C to stop the dashboard
echo ================================================================================
echo.
python app.py
