# Merge github/main when origin is swamplink and GitHub got commits first.
#   cd C:\Users\gmhow\dev\trust-but-anchor
#   .\scripts\sync-github-main.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

git fetch github

$mergeBase = git merge-base HEAD github/main 2>$null
$githubTip = git rev-parse github/main 2>$null
if ($mergeBase -eq $githubTip) {
    Write-Host "Already contains github/main ($githubTip)" -ForegroundColor DarkGray
} else {
    git merge github/main -m "merge: sync github/main (CI, CHANGELOG, publish-doctor)"
}

Write-Host "`nRestore a clean tree:" -ForegroundColor Green
git checkout HEAD -- .
git clean -fd -- scripts/sync-github-main.ps1 2>$null

Write-Host "Push both remotes if ahead:" -ForegroundColor Green
Write-Host "  git push origin main"
Write-Host "  git push github main"
Write-Host "`nDoctor:" -ForegroundColor Cyan
Write-Host "  & 'C:\Program Files\Git\bin\bash.exe' packaging/publish-doctor.sh"
