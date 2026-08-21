# Run reef Ollama fix from COOPER via SSH.
$ErrorActionPreference = "Stop"
$Reef = "owner@192.168.68.20"
$Here = $PSScriptRoot
$Fix = Join-Path $Here "reef-ollama-fix.ps1"
$Remote = "C:\Users\Owner\AppData\Local\Temp\reef-ollama-fix.ps1"

if (-not (Test-Path $Fix)) { throw "missing $Fix" }

Write-Host "Copying fix script to reef..." -ForegroundColor Cyan
scp $Fix "${Reef}:C:/Users/Owner/AppData/Local/Temp/reef-ollama-fix.ps1"

Write-Host "Running on reef..." -ForegroundColor Cyan
& ssh.exe -o LogLevel=ERROR -o ConnectTimeout=30 $Reef `
    "powershell -NoProfile -ExecutionPolicy Bypass -File $Remote"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Ollama OK. Re-kick sweep:" -ForegroundColor Green
    Write-Host "  cd C:\Users\gmhow\dev\trust-but-anchor"
    Write-Host "  .\scripts\reef-unstick-anchor2.ps1"
}
