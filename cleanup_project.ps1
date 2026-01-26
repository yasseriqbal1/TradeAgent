# TradeAgent Project Cleanup Script
# Organizes test/utility files without changing architecture

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "TRADEAGENT PROJECT CLEANUP" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Project Root: $ProjectRoot" -ForegroundColor Yellow
Write-Host ""
Write-Host "This script will:" -ForegroundColor White
Write-Host "  1. Create Testing/ folder structure" -ForegroundColor Gray
Write-Host "  2. Move test/utility files to Testing/" -ForegroundColor Gray
Write-Host "  3. Keep ALL essential bot files in place" -ForegroundColor Gray
Write-Host "  4. NOT touch: venv/, quant_agent/, dashboard/, config/" -ForegroundColor Gray
Write-Host "  5. Create cleanup_log.txt with all moves" -ForegroundColor Gray
Write-Host ""

$confirm = Read-Host "Proceed with cleanup? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host ""
    Write-Host "Cleanup cancelled" -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "Starting cleanup..." -ForegroundColor Green
Write-Host ""

# Create log file
$logFile = Join-Path $ProjectRoot "cleanup_log.txt"
"TradeAgent Cleanup Log - $(Get-Date)" | Out-File $logFile
"=" * 80 | Out-File $logFile -Append
"" | Out-File $logFile -Append

# Function to log and move file
function Move-FileWithLog {
    param($source, $destination)
    
    if (Test-Path $source) {
        $destDir = Split-Path $destination -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        
        Move-Item -Path $source -Destination $destination -Force
        $relativeSrc = $source.Replace($ProjectRoot, ".")
        $relativeDst = $destination.Replace($ProjectRoot, ".")
        
        Write-Host "  Moved: $relativeSrc -> $relativeDst" -ForegroundColor Green
        "MOVED: $relativeSrc -> $relativeDst" | Out-File $logFile -Append
        return $true
    }
    return $false
}

# Create Testing Folder Structure
Write-Host "STEP 1: Creating Testing folder structure..." -ForegroundColor Cyan

$testingDirs = @(
    "Testing/EOD_Reports",
    "Testing/Bot_Tests", 
    "Testing/Database_Utils",
    "Testing/Backtest_Scripts",
    "Testing/Data_Download_Scripts",
    "Testing/Setup_Scripts"
)

foreach ($dir in $testingDirs) {
    $fullPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    }
}
Write-Host ""

# Move EOD Report Scripts
Write-Host "STEP 2: Moving EOD report scripts..." -ForegroundColor Cyan
$movedCount = 0
foreach ($file in @("eod_report_jan16.py", "get_today_trades.py")) {
    $src = Join-Path $ProjectRoot $file
    $dst = Join-Path $ProjectRoot "Testing/EOD_Reports/$file"
    if (Move-FileWithLog $src $dst) { $movedCount++ }
}
Write-Host "  Moved $movedCount file(s)" -ForegroundColor Yellow
Write-Host ""

# Move Bot Test Scripts
Write-Host "STEP 3: Moving bot test scripts..." -ForegroundColor Cyan
$movedCount = 0
$botTests = @("test_redis.py", "test_full_flow.py", "test_currency_conversion.py", 
              "test_earnings_blackout.py", "test_order_placement.py", 
              "test_position_size_limit.py", "test_trade_logging.py", "test_trading_window.py")
foreach ($file in $botTests) {
    $src = Join-Path $ProjectRoot $file
    $dst = Join-Path $ProjectRoot "Testing/Bot_Tests/$file"
    if (Move-FileWithLog $src $dst) { $movedCount++ }
}
Write-Host "  Moved $movedCount file(s)" -ForegroundColor Yellow
Write-Host ""

# Move Database Utility Scripts
Write-Host "STEP 4: Moving database utility scripts..." -ForegroundColor Cyan
$movedCount = 0
$dbUtils = @("check_positions.py", "check_positions_schema.py", "check_slb_position.py",
             "check_tables.py", "check_table_schema.py", "cleanup_test_data.py",
             "clear_positions.py", "fix_mu_position.py", "fix_quantity_column.py")
foreach ($file in $dbUtils) {
    $src = Join-Path $ProjectRoot $file
    $dst = Join-Path $ProjectRoot "Testing/Database_Utils/$file"
    if (Move-FileWithLog $src $dst) { $movedCount++ }
}
Write-Host "  Moved $movedCount file(s)" -ForegroundColor Yellow
Write-Host ""

# Move Backtest Scripts
Write-Host "STEP 5: Moving backtest scripts..." -ForegroundColor Cyan
$movedCount = 0
$backtestScripts = @("analyze_trades.py", "run_backtest.py", "run_backtest_direct.py", "run_simple_backtest.py")
foreach ($file in $backtestScripts) {
    $src = Join-Path $ProjectRoot $file
    $dst = Join-Path $ProjectRoot "Testing/Backtest_Scripts/$file"
    if (Move-FileWithLog $src $dst) { $movedCount++ }
}
Write-Host "  Moved $movedCount file(s)" -ForegroundColor Yellow
Write-Host ""

# Move Data Download Scripts
Write-Host "STEP 6: Moving data download scripts..." -ForegroundColor Cyan
$movedCount = 0
$dataScripts = @("download_historical_data.py", "download_all_stocks_stooq.py", 
                 "historical_data_stooq.py", "load_historical_data.py",
                 "import_nasdaq_data.py", "clean_nasdaq_data.py", "fix_and_load_data.py")
foreach ($file in $dataScripts) {
    $src = Join-Path $ProjectRoot $file
    $dst = Join-Path $ProjectRoot "Testing/Data_Download_Scripts/$file"
    if (Move-FileWithLog $src $dst) { $movedCount++ }
}
Write-Host "  Moved $movedCount file(s)" -ForegroundColor Yellow
Write-Host ""

# Move Setup Scripts
Write-Host "STEP 7: Moving setup scripts..." -ForegroundColor Cyan
$movedCount = 0
$setupScripts = @("create_live_tables.py", "create_trades_history_table.sql",
                  "verify_database_setup.py", "configure_alerts.py", "example_config_usage.py")
foreach ($file in $setupScripts) {
    $src = Join-Path $ProjectRoot $file
    $dst = Join-Path $ProjectRoot "Testing/Setup_Scripts/$file"
    if (Move-FileWithLog $src $dst) { $movedCount++ }
}
Write-Host "  Moved $movedCount file(s)" -ForegroundColor Yellow
Write-Host ""

# Delete Old Data Files
Write-Host "STEP 8: Cleaning old data files..." -ForegroundColor Cyan
$deletedCount = 0
$oldDataFiles = @("backtest_equity_curve.csv", "backtest_results_direct.json",
                  "backtest_trades.csv", "combined_historical_data.csv")
foreach ($file in $oldDataFiles) {
    $fullPath = Join-Path $ProjectRoot $file
    if (Test-Path $fullPath) {
        Remove-Item -Path $fullPath -Force
        Write-Host "  Deleted: $file" -ForegroundColor Green
        "DELETED: $file" | Out-File $logFile -Append
        $deletedCount++
    }
}
Write-Host "  Deleted $deletedCount file(s)" -ForegroundColor Yellow
Write-Host ""

# Create README
Write-Host "STEP 9: Creating Testing/README.md..." -ForegroundColor Cyan
$readmeContent = @"
# Testing & Utility Scripts

This folder contains all test, utility, and one-time setup scripts.
These are NOT required for daily trading operations.

## Essential Bot Files (Still in Root)

- test_live_1hour_questrade.py - Main trading bot
- quant_agent/ - Core bot modules
- dashboard/ - Web dashboard
- config/ - Configuration files

Cleanup Date: $(Get-Date -Format "yyyy-MM-dd HH:mm")
"@
$readmePath = Join-Path $ProjectRoot "Testing/README.md"
$readmeContent | Out-File $readmePath -Encoding UTF8
Write-Host "  Created README.md" -ForegroundColor Green
Write-Host ""

# Final Report
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "CLEANUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Full log saved to: cleanup_log.txt" -ForegroundColor Yellow
Write-Host ""
Write-Host "Essential files verified:" -ForegroundColor Green
foreach ($file in @("test_live_1hour_questrade.py", ".env", "requirements.txt")) {
    if (Test-Path (Join-Path $ProjectRoot $file)) {
        Write-Host "  OK: $file" -ForegroundColor Green
    } else {
        Write-Host "  MISSING: $file" -ForegroundColor Red
    }
}
Write-Host ""
Write-Host "Essential folders verified:" -ForegroundColor Green
foreach ($folder in @("quant_agent", "dashboard", "config", "venv")) {
    if (Test-Path (Join-Path $ProjectRoot $folder)) {
        Write-Host "  OK: $folder/" -ForegroundColor Green
    } else {
        Write-Host "  MISSING: $folder/" -ForegroundColor Red
    }
}
Write-Host ""
Write-Host "Root folder is now clean and organized!" -ForegroundColor White
Write-Host "Bot architecture unchanged - ready for Monday!" -ForegroundColor White
Write-Host ""
