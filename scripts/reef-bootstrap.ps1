# One-shot: persistent Ollama on reef, pull sweep models, start anchor2 sweep. From COOPER.
$ErrorActionPreference = "Stop"
$Reef = "owner@192.168.68.20"
$Here = $PSScriptRoot
$Repo = Split-Path $Here -Parent

Write-Host "=== reef bootstrap: ollama task + models + sweep ===" -ForegroundColor Cyan

Write-Host "`n[1/5] Copy scripts to reef..." -ForegroundColor Yellow
$toCopy = @(
    "reef-ollama-install-task.ps1",
    "reef-bootstrap-pull-job.ps1",
    "reef-ollama-fix.ps1",
    "reef-anchor2-launch.ps1",
    "anchor2-sweep.ps1",
    "reef-python.ps1"
)
foreach ($f in $toCopy) {
    scp (Join-Path $Here $f) "${Reef}:C:/Users/Owner/AppData/Local/Temp/$f" | Out-Null
}
$copy = @'
New-Item -Force -ItemType Directory C:\Users\Owner\dev\trust-but-anchor\results | Out-Null
Copy-Item C:\Users\Owner\AppData\Local\Temp\reef-bootstrap-pull-job.ps1 C:\Users\Owner\dev\trust-but-anchor\results\reef-bootstrap-pull-job.ps1 -Force
'@
$b64copy = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($copy))
& ssh.exe -o LogLevel=ERROR $Reef "powershell -NoProfile -EncodedCommand $b64copy" | Out-Null

Write-Host "`n[2/5] Install Ollama scheduled task..." -ForegroundColor Yellow
$elev = @'
$p = Start-Process powershell -Verb RunAs -Wait -PassThru -ArgumentList @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
  "C:\Users\Owner\AppData\Local\Temp\reef-ollama-install-task.ps1"
)
exit $p.ExitCode
'@
$b64elev = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($elev))
& ssh.exe -o LogLevel=ERROR -o ConnectTimeout=30 $Reef "powershell -NoProfile -EncodedCommand $b64elev"

Write-Host "`n[3/5] Start model pull job on reef..." -ForegroundColor Yellow
$startJob = @'
$path = "C:\Users\Owner\dev\trust-but-anchor\results\reef-bootstrap-pull-job.ps1"
$p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $path
)
Write-Host "pull job PID=$($p.Id)"
'@
$b64job = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($startJob))
& ssh.exe -o LogLevel=ERROR $Reef "powershell -NoProfile -EncodedCommand $b64job"

Write-Host "Polling models (up to 90 min)..." -ForegroundColor Yellow
$ready = $false
for ($n = 0; $n -lt 90; $n++) {
    Start-Sleep -Seconds 60
    $poll = @'
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
try {
  $names = @((Invoke-RestMethod "$env:OLLAMA_HOST/api/tags").models.name)
  $need = @("granite3.3:8b","mistral:7b","qwen2.5-coder:7b")
  $miss = @($need | Where-Object { $names -notcontains $_ })
  Write-Host ("models={0}/3 miss={1}" -f ($need.Count - $miss.Count), ($miss -join ","))
  if ($miss.Count -eq 0) { exit 0 }
} catch {
  Write-Host "api down"
  Start-ScheduledTask -TaskName "Ollama serve reef" -ErrorAction SilentlyContinue
  exit 2
}
if (Test-Path C:\Users\Owner\dev\trust-but-anchor\results\reef-bootstrap-pull.log) {
  Get-Content C:\Users\Owner\dev\trust-but-anchor\results\reef-bootstrap-pull.log -Tail 2
}
exit 1
'@
    $b64poll = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($poll))
    $out = & ssh.exe -o LogLevel=ERROR $Reef "powershell -NoProfile -EncodedCommand $b64poll" 2>&1 | Out-String
    Write-Host ("[{0:HH:mm}] {1}" -f (Get-Date), $out.Trim())
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
}
if (-not $ready) { Write-Host "WARN: not all models ready; starting sweep anyway" -ForegroundColor Yellow }

Write-Host "`n[4/5] Start anchor2 sweep..." -ForegroundColor Yellow
Set-Location $Repo
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\reef-unstick-anchor2.ps1

Write-Host "`n[5/5] Status:" -ForegroundColor Yellow
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-reef-anchor2.ps1
