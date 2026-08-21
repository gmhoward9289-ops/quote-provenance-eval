# Commit reef Windows sweep scripts, push, start on reef.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

git add scripts/anchor2-sweep.ps1 scripts/reef-anchor2-launch.ps1 scripts/start-reef-anchor2.ps1 docs/reef-anchor2.md
$staged = git diff --cached --name-only
if ($staged) {
    git commit -m "feat: Windows reef anchor2 sweep (PowerShell remote launch)"
}
git push origin main
git push github main
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-reef-anchor2.ps1
