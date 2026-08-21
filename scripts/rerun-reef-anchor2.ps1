# Push script fixes and restart reef sweep.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

git add scripts/reef-anchor2-launch.ps1 scripts/anchor2-sweep.ps1 scripts/check-reef-anchor2.ps1
$staged = git diff --cached --name-only
if ($staged) {
    git commit -m "fix: always sync scp'd reef sweep scripts; preflight import"
}
git push origin main
git push github main
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-reef-anchor2.ps1
