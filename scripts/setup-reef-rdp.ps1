# Deploy reef RDP enable script and try to run it. Run from COOPER.
$ErrorActionPreference = "Stop"
$ReefHost = "owner@192.168.68.20"
$Here = $PSScriptRoot
$Enable = Join-Path $Here "reef-enable-rdp.ps1"
$RemoteTemp = "C:/Users/Owner/AppData/Local/Temp/reef-enable-rdp.ps1"
$RemoteLab = "C:/Users/Owner/lab/reef-enable-rdp.ps1"

if (-not (Test-Path $Enable)) { throw "missing $Enable" }

Write-Host "Copying enable script to reef..." -ForegroundColor Cyan
scp $Enable "${ReefHost}:$RemoteTemp"
$copy = @'
New-Item -ItemType Directory -Force -Path C:\Users\Owner\lab | Out-Null
Copy-Item -Path C:\Users\Owner\AppData\Local\Temp\reef-enable-rdp.ps1 -Destination C:\Users\Owner\lab\reef-enable-rdp.ps1 -Force
'@
$b64copy = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($copy))
ssh.exe -o LogLevel=ERROR $ReefHost "powershell -NoProfile -EncodedCommand $b64copy"

Write-Host "Checking RDP status (no elevation)..." -ForegroundColor Cyan
$probe = @'
Write-Output "hostname=$(hostname)"
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" }).IPAddress -join ","
Write-Output "ip=$ip"
Write-Output "fDenyTSConnections=$((Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server').fDenyTSConnections)"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Output "isAdmin=$admin"
'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe))
ssh.exe -o LogLevel=ERROR $ReefHost "powershell -NoProfile -EncodedCommand $b64"

Write-Host ""
Write-Host "Attempting elevated enable (UAC on reef console if not already admin)..." -ForegroundColor Yellow
$run = @'
$p = Start-Process powershell -Verb RunAs -Wait -PassThru -ArgumentList @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:\Users\Owner\lab\reef-enable-rdp.ps1"
)
exit $p.ExitCode
'@
$b64run = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($run))
ssh.exe -o LogLevel=ERROR $ReefHost "powershell -NoProfile -EncodedCommand $b64run"
$elevExit = $LASTEXITCODE

Write-Host ""
if ($elevExit -ne 0) {
    Write-Host "Elevated run did not complete (exit $elevExit)." -ForegroundColor Yellow
    Write-Host "On reef console (or HTTP drop http://192.168.68.53:8765/ POST script path):" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File C:\Users\Owner\lab\reef-enable-rdp.ps1"
} else {
    Write-Host "RDP should be enabled." -ForegroundColor Green
}

Write-Host ""
Write-Host "Connect:" -ForegroundColor Cyan
Write-Host "  mstsc C:\Users\gmhow\dev\trust-but-anchor\scripts\reef.rdp"
Write-Host "  (IP in reef.rdp: 192.168.68.20; SSH banner may show .53 if DHCP moved)"
Write-Host "  User: Owner  or  swamp\owner"
