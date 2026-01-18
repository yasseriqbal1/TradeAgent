@echo off
echo ================================================================================
echo TRADING DASHBOARD - STARTUP
echo ================================================================================
echo.
echo [1/3] Activating virtual environment...
call ..\venv\Scripts\activate.bat

echo [2/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo [3/3] Starting dashboard server...
echo.
echo ================================================================================
echo Dashboard will open at: http://localhost:5000
echo Press Ctrl+C to stop the dashboard
echo ================================================================================
echo.
python app.py
