# Poll reef anchor2 sweep log. Run from COOPER (repo root or scripts/).
$ErrorActionPreference = "Stop"
$Reef = "owner@192.168.68.20"
$Out = Join-Path $PSScriptRoot "..\results\reef-status.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null

$remote = "powershell -NoProfile -Command ""Get-Content C:\Users\Owner\dev\trust-but-anchor\results\anchor2-sweep.log -Tail 30"""
ssh.exe -o ConnectTimeout=20 -o LogLevel=ERROR $Reef $remote 2>$null | Tee-Object -FilePath $Out
Write-Host ""
Write-Host "Saved: $Out" -ForegroundColor DarkGray
