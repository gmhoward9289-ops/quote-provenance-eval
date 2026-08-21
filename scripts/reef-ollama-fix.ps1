# Run ON reef (Owner session). Restarts Ollama serve — not the desktop tray app.
# From COOPER: .\scripts\reef-fix-ollama.ps1
$ErrorActionPreference = "Stop"

Write-Host "=== reef ollama fix $(Get-Date -Format o) ===" -ForegroundColor Cyan

function Test-OllamaUp {
    try {
        $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:11434/api/tags" -TimeoutSec 8
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

Write-Host "--- stop ollama processes ---"
Get-CimInstance Win32_Process -Filter "Name='ollama.exe'" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Host "stop PID=$($_.ProcessId) $($_.CommandLine)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 3

Write-Host "--- port 11434 ---"
$on11434 = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($on11434) {
    Write-Host "WARN listener still on 11434 PID=$($on11434.OwningProcess)"
} else {
    Write-Host "11434 free"
}

Write-Host "--- disk ---"
foreach ($d in @("C", "V", "X", "Y", "Z")) {
    $root = "${d}:\"
    if (-not (Test-Path $root)) { continue }
    $ps = Get-PSDrive -Name $d -ErrorAction SilentlyContinue
    if ($ps) {
        Write-Host ("{0}: free {1:N1} GB" -f $d, ($ps.Free / 1GB))
    }
}

Write-Host "--- model store ---"
function Resolve-OllamaModelsRoot {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root)) { return $null }
    $withModels = Join-Path $Root "models"
    if (Test-Path (Join-Path $withModels "blobs")) { return $withModels }
    if (Test-Path (Join-Path $Root "blobs")) { return $Root }
    return $Root
}

function Get-OllamaStoreScore {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root)) { return $null }
    $resolved = Resolve-OllamaModelsRoot $Root
    $blobs = Join-Path $resolved "blobs"
    $manifests = Join-Path $resolved "manifests"
    $bytes = 0
    $files = 0
    foreach ($sub in @($blobs, $manifests)) {
        if (-not (Test-Path -LiteralPath $sub)) { continue }
        $m = Get-ChildItem -LiteralPath $sub -Recurse -File -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum
        $bytes += [int64]($m.Sum)
        $files += $m.Count
    }
    [pscustomobject]@{ Root = $Root; Resolved = $resolved; Bytes = $bytes; Files = $files }
}

$candidates = @(
    "$env:USERPROFILE\.ollama",
    "V:\ollama",
    "X:\ollama",
    "Y:\ollama",
    "Z:\ollama"
)
$scored = $candidates | ForEach-Object { Get-OllamaStoreScore $_ } | Where-Object { $_ } |
    Sort-Object -Property Bytes -Descending
foreach ($s in $scored) {
    Write-Host ("  {0} -> {1}: {2:N1} GB, {3} files" -f $s.Root, $s.Resolved, ($s.Bytes / 1GB), $s.Files)
}
$pick = $scored | Where-Object { $_.Bytes -gt 100MB } | Select-Object -First 1
if (-not $pick) { $pick = $scored | Select-Object -First 1 }
if ($pick) {
    $modelsRoot = $pick.Resolved
    $env:OLLAMA_MODELS = $modelsRoot
    [Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $modelsRoot, "User")
    Write-Host "OLLAMA_MODELS=$modelsRoot (also set User env)"
} else {
    Write-Host "WARN no model store found; using default $env:USERPROFILE\.ollama"
}

$ollamaExe = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollamaExe)) {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { $ollamaExe = $cmd.Source }
}
if (-not (Test-Path $ollamaExe)) {
    throw "ollama.exe not found (install Ollama or fix PATH)"
}
Write-Host "ollama=$ollamaExe"

if (Test-OllamaUp) {
    Write-Host "already up - restarting with correct OLLAMA_MODELS" -ForegroundColor Yellow
    Get-CimInstance Win32_Process -Filter "Name='ollama.exe'" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

Write-Host "--- start ollama serve (hidden) ---"
$logDir = "C:\Users\Owner\dev\trust-but-anchor\results"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$serveOut = Join-Path $logDir "ollama-serve.out.log"
$serveErr = Join-Path $logDir "ollama-serve.err.log"
Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden `
    -RedirectStandardOutput $serveOut -RedirectStandardError $serveErr

function Get-TagCount {
    try {
        $j = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 8
        return @($j.models).Count
    } catch { return -1 }
}

$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (Test-OllamaUp) {
        Write-Host "OK ollama up on 127.0.0.1:11434" -ForegroundColor Green
        $n = Get-TagCount
        Write-Host "api/tags model count: $n"
        $list = & $ollamaExe list 2>&1 | Out-String
        Write-Host $list
        if ($n -le 0 -and $list -notmatch "(?m)^\S+\s+\S+\s+\d") {
            Write-Host "WARN no models visible - sweep will ollama pull; blobs on disk: $modelsRoot" -ForegroundColor Yellow
        }
        exit 0
    }
}

Write-Host "FAIL ollama did not start in 45s" -ForegroundColor Red
Write-Host "--- tail stdout ---"
if (Test-Path $serveOut) { Get-Content $serveOut -Tail 20 }
Write-Host "--- tail stderr ---"
if (Test-Path $serveErr) { Get-Content $serveErr -Tail 20 }
Write-Host ""
Write-Host "Next steps if 'Unable to init instance':"
Write-Host "  1. On reef (RDP/console): disable Ollama from Startup; kill all ollama.exe"
Write-Host "  2. In Owner cmd: set OLLAMA_MODELS=Z:\ollama && ollama serve"
Write-Host "  3. If still failing: reboot reef, then re-run this script"
Write-Host "Do NOT launch the Ollama desktop tray app (second serve binds ::11434)."
exit 1
