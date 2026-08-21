$env:OLLAMA_HOST = "http://127.0.0.1:11434"
$m = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
if ($m) { $env:OLLAMA_MODELS = $m }
$log = "C:\Users\Owner\dev\trust-but-anchor\results\reef-bootstrap-pull.log"
"start $(Get-Date -Format o)" | Out-File $log
for ($i = 0; $i -lt 40; $i++) {
    try {
        Invoke-RestMethod "$env:OLLAMA_HOST/api/tags" -TimeoutSec 5 | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 3
    }
}
foreach ($model in @("granite3.3:8b", "mistral:7b", "qwen2.5-coder:7b")) {
    $tags = @((Invoke-RestMethod "$env:OLLAMA_HOST/api/tags").models.name)
    if ($tags -contains $model) {
        "have $model" | Out-File $log -Append
        continue
    }
    "pull $model" | Out-File $log -Append
    & ollama pull $model 2>&1 | Out-File $log -Append
}
"done $(Get-Date -Format o)" | Out-File $log -Append
ollama list 2>&1 | Out-File $log -Append
