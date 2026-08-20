# Publish trust-but-anchor v0.1.0 to PyPI, tag, and GitHub release.
# Run from repo root in PowerShell:
#   cd C:\Users\gmhow\dev\quote-provenance-eval
#   .\scripts\publish.ps1
#
# Requires: PyPI API token (pypi-...) with 2FA enabled on the account.
# Optional: set $env:TWINE_PASSWORD before running to skip the prompt.

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$Version = (Select-String -Path pyproject.toml -Pattern '^version = "(.+)"' | ForEach-Object { $_.Matches[0].Groups[1].Value })
if (-not $Version) { throw "Could not read version from pyproject.toml" }

Write-Host "==> trust-but-anchor v$Version" -ForegroundColor Cyan
Write-Host "==> $Repo`n"

Write-Host "1/6 Tests..." -ForegroundColor Yellow
python -m pip install -e ".[dev]" -q
python -m pip install build twine -q
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest tests -q -p pytest
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
python validate_corpus.py
if ($LASTEXITCODE -ne 0) { throw "validate_corpus failed" }

Write-Host "2/6 Build..." -ForegroundColor Yellow
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
python -m build
python -m twine check dist/*
if ($LASTEXITCODE -ne 0) { throw "twine check failed" }

Write-Host "3/6 PyPI upload..." -ForegroundColor Yellow
if (-not $env:TWINE_USERNAME) { $env:TWINE_USERNAME = "__token__" }
if (-not $env:TWINE_PASSWORD) {
    Write-Host "Paste your PyPI API token (pypi-...). Input is hidden." -ForegroundColor Cyan
    $secure = Read-Host -AsSecureString
    $env:TWINE_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}
if (-not $env:TWINE_PASSWORD) { throw "No PyPI token provided" }

python -m twine upload dist/*
if ($LASTEXITCODE -ne 0) { throw "twine upload failed" }
Write-Host "Uploaded to https://pypi.org/project/trust-but-anchor/" -ForegroundColor Green

Write-Host "4/6 Verify install..." -ForegroundColor Yellow
python -m pip install --force-reinstall "trust-but-anchor==$Version"
python -c "from trust_but_anchor import locate; assert locate('abc', 'bc')['method']=='exact'"
tba-preflight --help | Out-Null
Write-Host "pip install OK" -ForegroundColor Green

Write-Host "5/6 Git tag v$Version..." -ForegroundColor Yellow
$tag = "v$Version"
git tag -l $tag | ForEach-Object { if ($_ -eq $tag) { throw "Tag $tag already exists" } }
git tag -a $tag -m "trust-but-anchor $tag"
git push origin $tag
git push github $tag

Write-Host "6/6 GitHub release..." -ForegroundColor Yellow
$wheel = Get-ChildItem dist -Filter "*.whl" | Select-Object -First 1 -ExpandProperty FullName
$sdist = Get-ChildItem dist -Filter "*.tar.gz" | Select-Object -First 1 -ExpandProperty FullName
gh release create $tag `
    --repo gmhoward9289-ops/trust-but-anchor `
    --title "trust-but-anchor $tag" `
    --notes "First PyPI release.`n`npip install trust-but-anchor`n`nThe model proposes a short anchor; code locates a real source span. Fail closed." `
    $wheel $sdist

Write-Host "`nDone. https://pypi.org/project/trust-but-anchor/$Version/" -ForegroundColor Green
