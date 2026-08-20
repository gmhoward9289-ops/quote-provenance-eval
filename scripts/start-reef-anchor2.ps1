# Start anchor2 sweep on reef (Windows OpenSSH). Run from COOPER.
$ErrorActionPreference = "Stop"
$Reef = "owner@192.168.68.20"
$Here = $PSScriptRoot
$Launch = Join-Path $Here "reef-anchor2-launch.ps1"
$Worker = Join-Path $Here "anchor2-sweep.ps1"

if (-not (Test-Path $Launch)) { throw "missing $Launch" }

Write-Host "Copying scripts to reef..." -ForegroundColor Cyan
scp $Launch "${Reef}:C:/Users/Owner/AppData/Local/Temp/reef-anchor2-launch.ps1"
scp $Worker "${Reef}:C:/Users/Owner/AppData/Local/Temp/anchor2-sweep.ps1"

Write-Host "Starting sweep on reef..." -ForegroundColor Cyan
ssh -o ConnectTimeout=20 $Reef "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Owner\AppData\Local\Temp\reef-anchor2-launch.ps1"
