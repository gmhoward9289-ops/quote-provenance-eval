# Commit and push parallel track (run from PowerShell).
#   cd C:\Users\gmhow\dev\trust-but-anchor
#   .\scripts\ship-parallel-track.ps1

$ErrorActionPreference = "Stop"

function Ship-Repo($Path, $Message, $Files) {
    Write-Host "`n==> $Path" -ForegroundColor Yellow
    Push-Location $Path
    git add @Files
    $staged = git diff --cached --name-only
    if (-not $staged) {
        Write-Host "Nothing to commit" -ForegroundColor DarkGray
        Pop-Location
        return
    }
    git status --short
    git commit -m $Message
    git push
    Pop-Location
}

Write-Host "Sync trust-but-anchor from GitHub (already pushed via API)" -ForegroundColor DarkGray
Push-Location "C:\Users\gmhow\dev\trust-but-anchor"
git pull
Pop-Location

Ship-Repo "C:\Users\gmhow\dev\swamplink-root" "data/trust: pip install trust-but-anchor on trust page" @(
    "data/trust/index.html"
)

Ship-Repo "C:\Users\gmhow\dev\blog" "blog: PyPI library paragraph on anchor post" @(
    "content/posts/dont-trust-model-quotes-use-anchors.md"
)

Write-Host "`nReef anchor2 (manual, long-running):" -ForegroundColor Cyan
Write-Host "  ssh owner@192.168.68.20 'cd ~/dev/trust-but-anchor && git pull && nohup bash scripts/anchor2-sweep.sh &'"
Write-Host "`nProof stack PyPI: henhouse 0.1.2, pytest-session-trace 0.1.4, pytest-mcp-contract 0.1.3" -ForegroundColor Green
