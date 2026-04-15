$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$djangoScript = Join-Path $PSScriptRoot "start-django.ps1"
$electronScript = Join-Path $PSScriptRoot "start-electron.ps1"

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", $djangoScript
) -WorkingDirectory $repoRoot

Start-Sleep -Seconds 3

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", $electronScript
) -WorkingDirectory $repoRoot
