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

. (Join-Path $PSScriptRoot "reef-python.ps1")
if (-not (Test-Path (Join-Path $PSScriptRoot "reef-python.ps1"))) {
    . (Join-Path $Repo "scripts\reef-python.ps1")
}
$Py = Get-ReefPython
Write-Host "python=$Py"
$env:PYTHONPATH = Join-Path $Repo "src"
$importOk = & $Py -c "import trust_but_anchor" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install -e . (trust_but_anchor import failed)"
    & $Py -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pip failed; continuing with PYTHONPATH=$env:PYTHONPATH"
    }
}

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
. (Join-Path $Repo "scripts\reef-python.ps1")
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

$cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Worker`""
# Win32_Process.Create breaks away from OpenSSH job (Start-Process dies with SSH session).
$created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
Write-Host "HOST=$env:COMPUTERNAME"
Write-Host "REPO=$Repo"
Write-Host "started_pid=$($created.ProcessId)"
Write-Host "create_return=$($created.ReturnValue)"
Start-Sleep -Seconds 5
if (Test-Path $Log) { Get-Content $Log -Tail 20 }
$alive = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*anchor2-sweep.ps1*' }
if ($alive) { Write-Host "ALIVE_AFTER_LAUNCH pid=$($alive.ProcessId -join ',')" } else { Write-Host "WARN not alive 5s after launch" }
