# TradeAgent - Update Questrade refresh token for Docker
# Writes token to ./secrets/questrade_refresh_token.txt and restarts the bot container.

param(
    [string]$Token
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$secretsDir = Join-Path $root 'secrets'
$tokenPath = Join-Path $secretsDir 'questrade_refresh_token.txt'

if (-not $Token -or $Token.Trim().Length -lt 10) {
    $Token = Read-Host -Prompt 'Paste the NEW Questrade refresh token'
}

if (-not $Token -or $Token.Trim().Length -lt 10) {
    Write-Host "[ERROR] Token looks empty/too short." -ForegroundColor Red
    exit 1
}

$Token = $Token.Trim()

# Allow pasting the full URL and extract the refresh_token=... value
if ($Token -match "refresh_token=") {
    try {
        $Token = [System.Uri]::UnescapeDataString(($Token -split "refresh_token=")[-1])
        # Strip any trailing parameters
        if ($Token -match "&") { $Token = ($Token -split "&")[0] }
        $Token = $Token.Trim()
    } catch {
        # If parsing fails, keep the original and let validation handle it
    }
}

New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null

# Write without BOM (BOM breaks Questrade refresh token requests)
[System.IO.File]::WriteAllText($tokenPath, $Token + "`n", (New-Object System.Text.UTF8Encoding($false)))

Write-Host "[OK] Saved token to $tokenPath" -ForegroundColor Green

# Restart bot so it immediately picks up the new token
Write-Host "Restarting bot container..." -ForegroundColor Cyan
& docker compose restart bot

Write-Host "[OK] Done. Check logs with: docker compose logs -f bot" -ForegroundColor Green
