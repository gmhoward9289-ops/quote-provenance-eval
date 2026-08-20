# Commit publish-doctor fix, push both remotes, run doctor. Does NOT reset the tree.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

git add packaging/publish-doctor.sh scripts/fix-and-doctor.ps1 scripts/sync-github-main.ps1
$staged = git diff --cached --name-only
if ($staged) {
    git commit -m "fix: publish-doctor on Windows Git Bash (grep version, python fallbacks)"
}
git push origin main
git push github main
& 'C:\Program Files\Git\bin\bash.exe' packaging/publish-doctor.sh
exit $LASTEXITCODE
