# Run from anywhere — finds the repo and runs the test suite.
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

Write-Host "==> $Repo" -ForegroundColor Cyan
python -m pip install -e ".[dev]" -q
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest tests -v -p pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python eval.py run --provider mock --model sloppy --limit 5
python validate_corpus.py
