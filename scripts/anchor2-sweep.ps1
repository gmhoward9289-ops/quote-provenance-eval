# Worker: anchor vs anchor2 models on questions_anchor2.json (3 repeats each).
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

$Log = Join-Path $PWD "results\anchor2-sweep.log"
$Nohup = Join-Path $PWD "results\anchor2-sweep.nohup"
"anchor2 sweep $(Get-Date -Format o)" | Tee-Object -FilePath $Log -Append | Out-File $Nohup -Append

$Models = @("granite3.3:8b", "qwen2.5-coder:7b", "mistral:7b")
foreach ($model in $Models) {
    foreach ($arm in @("anchor", "anchor2")) {
        "==> $model $arm" | Tee-Object -FilePath $Log -Append | Out-File $Nohup -Append
        python eval.py run --provider ollama --model $model --arm $arm `
            --questions corpus/questions_anchor2.json --repeats 3 2>&1 `
            | Tee-Object -FilePath $Log -Append | Out-File $Nohup -Append
    }
}
"done $(Get-Date -Format o)" | Tee-Object -FilePath $Log -Append | Out-File $Nohup -Append
