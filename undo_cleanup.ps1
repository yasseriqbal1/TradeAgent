# ============================================================================
# TradeAgent Project Cleanup - UNDO Script
# Restores all files moved by cleanup_project.ps1
# ============================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "`n============================================================================" -ForegroundColor Cyan
Write-Host "TRADEAGENT CLEANUP - UNDO" -ForegroundColor Cyan
Write-Host "============================================================================`n" -ForegroundColor Cyan

$logFile = Join-Path $ProjectRoot "cleanup_log.txt"

if (-not (Test-Path $logFile)) {
    Write-Host "❌ cleanup_log.txt not found!" -ForegroundColor Red
    Write-Host "   Cannot undo - no cleanup was performed or log was deleted." -ForegroundColor Yellow
    exit
}

Write-Host "This will restore all files moved by cleanup_project.ps1" -ForegroundColor Yellow
$confirm = Read-Host "`nProceed with undo? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "`n❌ Undo cancelled" -ForegroundColor Red
    exit
}

Write-Host "`n📋 Reading cleanup log...`n" -ForegroundColor Green

$logContent = Get-Content $logFile
$movedFiles = $logContent | Where-Object { $_ -like "MOVED:*" }

Write-Host "Found $($movedFiles.Count) file(s) to restore`n" -ForegroundColor Yellow

$restoredCount = 0
foreach ($line in $movedFiles) {
    # Parse: "MOVED: .\source.py → .\Testing/folder/source.py"
    $parts = $line -replace "MOVED: ", "" -split " → "
    $originalPath = $parts[0].Trim() -replace "^\.\\", ""
    $movedPath = $parts[1].Trim() -replace "^\.\\", ""
    
    $src = Join-Path $ProjectRoot $movedPath
    $dst = Join-Path $ProjectRoot $originalPath
    
    if (Test-Path $src) {
        Move-Item -Path $src -Destination $dst -Force
        Write-Host "  ✓ Restored: $originalPath" -ForegroundColor Green
        $restoredCount++
    } else {
        Write-Host "  ⊘ Not found: $movedPath" -ForegroundColor DarkGray
    }
}

Write-Host "`n✅ Restored $restoredCount file(s) to original locations" -ForegroundColor Green

# Optionally remove Testing folder
$removeTestingFolder = Read-Host "`nRemove Testing/ folder? (yes/no)"
if ($removeTestingFolder -eq "yes") {
    $testingPath = Join-Path $ProjectRoot "Testing"
    if (Test-Path $testingPath) {
        Remove-Item -Path $testingPath -Recurse -Force
        Write-Host "✓ Deleted Testing/ folder" -ForegroundColor Green
    }
}

Write-Host "`n============================================================================" -ForegroundColor Cyan
Write-Host "UNDO COMPLETE - Project restored to original state" -ForegroundColor Green
Write-Host "============================================================================`n" -ForegroundColor Cyan
