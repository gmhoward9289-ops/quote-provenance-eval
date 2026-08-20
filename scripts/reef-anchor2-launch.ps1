# Anchor vs anchor2 on repeated-anchor trap corpus. Run on reef (Windows + local Ollama).
$ErrorActionPreference = "Stop"

$Candidates = @(
    "C:\Users\Owner\dev\trust-but-anchor",
    "C:\Users\Owner\dev\quote-provenance-eval"
)
$Repo = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Repo) {
    $Parent = "C:\Users\Owner\dev"
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    $Repo = Join-Path $Parent "trust-but-anchor"
    if (-not (Test-Path $Repo)) {
        git clone https://github.com/gmhoward9289-ops/trust-but-anchor.git $Repo
    }
}
Set-Location $Repo
git pull

$Worker = Join-Path $Repo "scripts\anchor2-sweep.ps1"
$PyHelper = Join-Path $Repo "scripts\reef-python.ps1"
$TempWorker = "C:\Users\Owner\AppData\Local\Temp\anchor2-sweep.ps1"
$TempPy = "C:\Users\Owner\AppData\Local\Temp\reef-python.ps1"
foreach ($pair in @(
    @($TempWorker, $Worker),
    @($TempPy, $PyHelper)
)) {
    if ((-not (Test-Path $pair[1])) -and (Test-Path $pair[0])) {
        New-Item -ItemType Directory -Force -Path (Split-Path $pair[1]) | Out-Null
        Copy-Item $pair[0] $pair[1] -Force
    }
}
if (-not (Test-Path $Worker)) {
    throw "missing scripts\anchor2-sweep.ps1 (pull or scp failed)"
}
. $PyHelper
$null = Get-ReefPython

$LogDir = Join-Path $Repo "results"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "anchor2-sweep.log"

$running = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*anchor2-sweep.ps1*' }
if ($running) {
    Write-Host "ALREADY_RUNNING"
    $running | ForEach-Object { Write-Host $_.ProcessId $_.CommandLine }
    exit 0
}

$p = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Worker
)
Write-Host "HOST=$env:COMPUTERNAME"
Write-Host "REPO=$Repo"
Write-Host "started_pid=$($p.Id)"
Start-Sleep -Seconds 3
if (Test-Path $Log) { Get-Content $Log -Tail 15 }
