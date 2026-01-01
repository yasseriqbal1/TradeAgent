# Auto-detect script location and run live trading
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ScriptDir "venv\Scripts\python.exe"
$TradingScript = Join-Path $ScriptDir "test_live_1hour_questrade.py"

# Set UTF-8 encoding
$env:PYTHONIOENCODING = 'utf-8'

# Change to project directory
Set-Location $ScriptDir

# Run the trading script
& $PythonExe $TradingScript
