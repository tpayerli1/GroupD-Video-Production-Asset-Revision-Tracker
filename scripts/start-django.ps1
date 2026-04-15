$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Expected Python virtual environment at $pythonExe"
}

Push-Location $repoRoot
try {
    & $pythonExe manage.py runserver
}
finally {
    Pop-Location
}
