#requires -Version 5.1
<#
.SYNOPSIS
  Estate smoke: Marvin fail-closed gate against this repo's README.

.DESCRIPTION
  Design-partner shape living outside project-marvin. Requires `marvin` on PATH
  (pip install -e C:\Users\gmhow\dev\project-marvin).

  Honest claim must exit 0; fabricated anchor must exit 2.
#>
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Readme = Join-Path $RepoRoot "README.md"
if (-not (Test-Path -LiteralPath $Readme)) {
    Write-Error "README.md not found at $Readme"
}

$cmd = Get-Command marvin -ErrorAction SilentlyContinue
if (-not $cmd) {
    Write-Error "marvin not on PATH. From project-marvin: pip install -e ."
}

Write-Host "marvin-ci-smoke: honest claim (expect exit 0)"
& marvin gate --source-file $Readme --answer "100%" --anchor "provenance fidelity is 100%"
if ($LASTEXITCODE -ne 0) {
    Write-Error "honest claim failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host "marvin-ci-smoke: fabricated anchor (expect exit 2)"
& marvin gate --source-file $Readme --answer "42" --anchor "fabricated xyzzy never in source"
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Error "FAIL: gate accepted a fabricated anchor"
    exit 1
}
Write-Host "marvin-ci-smoke: refused fabrication (exit $code)"
exit 0
