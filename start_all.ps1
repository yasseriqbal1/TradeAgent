# TradeAgent - Start Everything (PowerShell)
#
# Opens separate PowerShell windows for:
# - Redis
# - n8n
# - Bot runner
# - Dashboard
#
# Usage:
#   .\start_all.ps1
#   .\start_all.ps1 -NoN8N
#

param(
    [switch]$NoRedis,
    [switch]$NoN8N,
    [switch]$NoBot,
    [switch]$NoDashboard
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-VenvPython {
    param([string]$root)

    $venvCandidates = @(
        (Join-Path -Path $root -ChildPath '.venv'),
        (Join-Path -Path $root -ChildPath 'venv')
    )

    foreach ($v in $venvCandidates) {
        $py = Join-Path $v 'Scripts\python.exe'
        if (Test-Path $py) {
            return $py
        }
    }

    throw "No venv python found. Expected .venv\\Scripts\\python.exe or venv\\Scripts\\python.exe"
}

function Start-TerminalWindow {
    param(
        [Parameter(Mandatory=$true)][string]$Title,
        [Parameter(Mandatory=$true)][string]$WorkingDir,
        [Parameter(Mandatory=$true)][string]$Command
    )

    $wd = $WorkingDir.Replace("'", "''")
    $t = $Title.Replace("'", "''")

    $full = @(
        "`$host.UI.RawUI.WindowTitle='$t'",
        "Set-Location -LiteralPath '$wd'",
        $Command
    ) -join '; '

    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit',
        '-NoLogo',
        '-ExecutionPolicy', 'Bypass',
        '-Command', $full
    ) | Out-Null
}

$PythonExe = Resolve-VenvPython -root $Root

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   TradeAgent - Start Everything" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Using Python: $PythonExe" -ForegroundColor Gray
Write-Host ""

if (-not $NoRedis) {
    # Uses the existing helper script to keep Redis install/path logic in one place.
    Start-TerminalWindow -Title 'TradeAgent - Redis' -WorkingDir $Root -Command '.\start_redis.ps1'
}

if (-not $NoN8N) {
    # npx is usually installed with Node.js. If this fails, install Node.js LTS.
    Start-TerminalWindow -Title 'TradeAgent - n8n' -WorkingDir $Root -Command 'npx n8n'
}

if (-not $NoBot) {
    Start-TerminalWindow -Title 'TradeAgent - Bot (paper)' -WorkingDir $Root -Command "& '$PythonExe' test_live_1hour_questrade.py"
}

if (-not $NoDashboard) {
    $dashDir = Join-Path $Root 'dashboard'
    Start-TerminalWindow -Title 'TradeAgent - Dashboard' -WorkingDir $dashDir -Command "`$env:DASHBOARD_DEBUG='false'; & '$PythonExe' app.py"
}

Write-Host "Launched. Close the spawned windows to stop services." -ForegroundColor Green
