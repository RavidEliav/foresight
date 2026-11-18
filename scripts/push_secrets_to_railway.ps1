<#
Copies the secrets from the local .env file to the Railway service foresight-app.

- OPENAI_API_KEY and RUN_PASSCODE: the same value in both environments (ADR-003).
- SUPABASE_DB_URL: each environment gets its own Supabase project (ADR-026), from
  SUPABASE_DB_URL_DEV and SUPABASE_DB_URL_MAIN in .env (skipped if they are not there yet).

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
    if ($line -match '^\s*(OPENAI_API_KEY|RUN_PASSCODE|SUPABASE_DB_URL_DEV|SUPABASE_DB_URL_MAIN)\s*=\s*(.*)\s*$') {
        $values[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
}

foreach ($key in "OPENAI_API_KEY", "RUN_PASSCODE") {
    if (-not $values[$key]) { throw "$key is empty in .env" }
}

function Set-RailwaySecret($key, $value, $environment) {
    $value | railway variable set $key --stdin --service foresight-app --environment $environment --skip-deploys | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to set $key in $environment" }
    Write-Host "set $key in $environment"
}

foreach ($environment in "dev", "main") {
    foreach ($key in "OPENAI_API_KEY", "RUN_PASSCODE") {
        Set-RailwaySecret $key $values[$key] $environment
    }
    $database = $values["SUPABASE_DB_URL_$($environment.ToUpper())"]
    if ($database) {
        Set-RailwaySecret "SUPABASE_DB_URL" $database $environment
    } else {
        Write-Host "SUPABASE_DB_URL_$($environment.ToUpper()) not in .env: $environment keeps using the run folders"
    }
}
Write-Host "Done. Redeploy both environments (or merge the next change) to load the new values."
