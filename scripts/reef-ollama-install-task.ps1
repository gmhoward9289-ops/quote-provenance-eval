# Install persistent Ollama serve on reef. Run ON reef as Administrator.
# From COOPER: .\scripts\reef-bootstrap.ps1
$ErrorActionPreference = "Stop"

$models = "Z:\ollama\models"
if (-not (Test-Path (Join-Path $models "blobs"))) {
    if (Test-Path "Z:\ollama\blobs") { $models = "Z:\ollama" }
    else { throw "No ollama blobs under Z:\ollama or Z:\ollama\models" }
}

[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $models, "User")
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "http://127.0.0.1:11434", "User")
Write-Host "OLLAMA_MODELS=$models"

$lab = "C:\Users\Owner\lab"
New-Item -ItemType Directory -Force -Path $lab | Out-Null
$wrapper = Join-Path $lab "ollama-serve.ps1"
@(
    "`$env:OLLAMA_MODELS = '$models'"
    "`$env:OLLAMA_HOST = 'http://127.0.0.1:11434'"
    "`$exe = Join-Path `$env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'"
    "if (-not (Test-Path `$exe)) { throw 'ollama.exe missing' }"
    "& `$exe serve"
) | Set-Content -Path $wrapper -Encoding UTF8

$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

$taskName = "Ollama serve reef"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$wrapper`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host "Scheduled task '$taskName' registered and started."

$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    try {
        $j = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
        Write-Host "OK api/tags models=$(@($j.models).Count)"
        exit 0
    } catch { }
}
Write-Host "WARN api/tags not up after 60s - check task or logs" -ForegroundColor Yellow
exit 1
