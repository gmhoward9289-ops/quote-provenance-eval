function Get-ReefPython {
    $paths = @(
        "X:\venvs\quote-provenance-eval\Scripts\python.exe",
        "X:\venvs\trust-but-anchor\Scripts\python.exe",
        "C:\Users\Owner\AppData\Local\Programs\Python\Python313\python.exe",
        "C:\Users\Owner\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Users\Owner\AppData\Local\Programs\Python\Python311\python.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return (Get-Command python).Source
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py -3"
    }
    throw "python not found on reef (tried Owner profile paths, python, py -3)"
}
