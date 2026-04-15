$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$electronRoot = Join-Path $repoRoot "electron_app"
$npmCmd = Get-Command npm.cmd -ErrorAction Stop

Push-Location $electronRoot
try {
    & $npmCmd.Source start
}
finally {
    Pop-Location
}
