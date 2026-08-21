# Enable Remote Desktop on reef. Requires Administrator. Run ON reef.
# From COOPER: .\scripts\setup-reef-rdp.ps1
#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

Write-Host "=== enable RDP on reef ===" -ForegroundColor Cyan

Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" `
    -Name "fDenyTSConnections" -Value 0

# Allow RDP without NLA for homelab LAN (simpler first connect)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" `
    -Name "UserAuthentication" -Value 0 -ErrorAction SilentlyContinue

Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue

$rdpUsers = "Remote Desktop Users"
$account = "$env:USERDOMAIN\$env:USERNAME"
$existing = Get-LocalGroupMember -Group $rdpUsers -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq $account }
if (-not $existing) {
    Add-LocalGroupMember -Group $rdpUsers -Member $env:USERNAME -ErrorAction SilentlyContinue
    Write-Host "added $account to $rdpUsers"
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -like "192.168.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "RDP enabled." -ForegroundColor Green
Write-Host "Connect from COOPER: mstsc /v:$ip"
Write-Host "User: $account  (or .\Owner)"
Write-Host "Registry fDenyTSConnections:" (Get-ItemProperty "HKLM:\System\CurrentControlSet\Control\Terminal Server").fDenyTSConnections
