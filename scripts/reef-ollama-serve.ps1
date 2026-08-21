# Start Ollama serve on reef with the correct model store. Run in RDP (keep window open).
$ErrorActionPreference = "Stop"

$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollamaExe)) { throw "ollama.exe not found" }

$models = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
if (-not $models) {
    foreach ($c in @("Z:\ollama", "V:\ollama", "$env:USERPROFILE\.ollama")) {
        if (Test-Path (Join-Path $c "blobs")) { $models = $c; break }
        if (Test-Path (Join-Path $c "models\blobs")) { $models = Join-Path $c "models"; break }
    }
}
if (-not $models) { throw "Set OLLAMA_MODELS or create Z:\ollama with blobs" }

$env:OLLAMA_MODELS = $models
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $models, "User")
Write-Host "OLLAMA_MODELS=$models"

Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Starting ollama serve (leave this window open)..." -ForegroundColor Cyan
& $ollamaExe serve
