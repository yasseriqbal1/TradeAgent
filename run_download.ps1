# Auto-detect script location and run download
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ScriptDir "venv\Scripts\python.exe"
$DownloadScript = Join-Path $ScriptDir "download_all_stocks_stooq.py"

# Set UTF-8 encoding
$env:PYTHONIOENCODING = 'utf-8'

# Run the download script
& $PythonExe $DownloadScript
