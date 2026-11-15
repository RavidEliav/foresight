<#
Copies OPENAI_API_KEY and RUN_PASSCODE from the local .env file to the Railway
service foresight-app in both environments (dev and main), so they stay identical.
Values are sent through stdin and never printed.

Usage (from the repo root, after `railway login`):
    .\scripts\push_secrets_to_railway.ps1
#>
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw "No .env file found at $envFile" }

$values = @{}
foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*(OPENAI_API_KEY|RUN_PASSCODE)\s*=\s*(.*)\s*$') {
        $values[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
}

foreach ($key in "OPENAI_API_KEY", "RUN_PASSCODE") {
    if (-not $values[$key]) { throw "$key is empty in .env" }
}

foreach ($environment in "dev", "main") {
    foreach ($key in "OPENAI_API_KEY", "RUN_PASSCODE") {
        $values[$key] | railway variable set $key --stdin --service foresight-app --environment $environment --skip-deploys | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to set $key in $environment" }
        Write-Host "set $key in $environment"
    }
}
Write-Host "Done. Redeploy both environments (or merge the next change) to load the new values."
