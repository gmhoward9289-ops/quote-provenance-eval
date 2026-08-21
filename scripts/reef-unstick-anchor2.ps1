# Clear stuck sweep lock and restart sweep. Does NOT restart ollama serve
# (leave RDP serve window alone). Optional: -FixOllama to call reef-fix-ollama.
param([switch]$FixOllama)
$ErrorActionPreference = "Stop"
$Reef = "owner@192.168.68.20"
$RepoRoot = Split-Path $PSScriptRoot -Parent

if ($FixOllama) {
    Write-Host "Fixing Ollama model store on reef..." -ForegroundColor Cyan
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "reef-fix-ollama.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN reef-fix-ollama exit=$LASTEXITCODE" -ForegroundColor Yellow
    }
}

$remote = @'
$repo = "C:\Users\Owner\dev\trust-but-anchor"
$lock = Join-Path $repo "results\anchor2-sweep.lock"
Write-Host "=== unstick reef anchor2 ==="
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq "powershell.exe" -and $_.CommandLine -like "*anchor2-sweep*"
} | ForEach-Object {
  Write-Host "stop PID=$($_.ProcessId) $($_.Name)"
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
if (Test-Path $lock) { Remove-Item $lock -Force; Write-Host "removed lock" }
try {
  $names = @((Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 8).models.name)
  Write-Host "api/tags models=$($names.Count)"
  foreach ($need in @("granite3.3:8b","mistral:7b","qwen2.5-coder:7b")) {
    if ($names -contains $need) { Write-Host "  have $need" }
    else { Write-Host "  MISS $need" }
  }
} catch { Write-Host "api/tags unreachable: $($_.Exception.Message)" }
Write-Host "done unstick"
'@
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remote))
Write-Host "Stopping stuck sweep on reef..." -ForegroundColor Yellow
& ssh.exe -o LogLevel=ERROR $Reef "powershell -NoProfile -EncodedCommand $b64"

Write-Host "Restarting sweep..." -ForegroundColor Cyan
Set-Location $RepoRoot
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-reef-anchor2.ps1
Start-Sleep -Seconds 5
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-reef-anchor2.ps1