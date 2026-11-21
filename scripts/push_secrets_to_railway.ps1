<#
Copies the secrets from the local .env file to the Railway service foresight-app.

- OPENAI_API_KEY, the Google sign-in keys (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
  AUTH_COOKIE_SECRET, FORESIGHT_DEVELOPERS and RESEND_API_KEY: the same value in both
  environments (ADR-003). A missing AUTH_COOKIE_SECRET is generated and saved to .env first.
- SUPABASE_DB_URL: each environment gets its own Supabase project (ADR-026), from
  SUPABASE_DB_URL_DEV and SUPABASE_DB_URL_MAIN in .env (skipped if they are not there yet).

Values are sent through stdin and never printed. Variables are set without redeploying; they
take effect with the next deploy.

Usage (from the repo root, after `railway login`):
    .\scripts\push_secrets_to_railway.ps1
#>
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw "No .env file found at $envFile" }

$shared = "OPENAI_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "AUTH_COOKIE_SECRET",
          "FORESIGHT_DEVELOPERS", "RESEND_API_KEY"
$pattern = '^\s*(' + (($shared + "SUPABASE_DB_URL_DEV", "SUPABASE_DB_URL_MAIN") -join '|') +
           ')\s*=\s*(.*)\s*$'

function Read-Values {
    $found = @{}
    foreach ($line in Get-Content $envFile) {
        if ($line -match $pattern) { $found[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'") }
    }
    return $found
}

$values = Read-Values
if (-not $values["AUTH_COOKIE_SECRET"]) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    Add-Content -Path $envFile -Value "AUTH_COOKIE_SECRET=$secret" -Encoding ascii
    Write-Host "generated AUTH_COOKIE_SECRET and saved it to .env"
    $values = Read-Values
}
foreach ($key in $shared) {
    if (-not $values[$key]) { throw "$key is empty in .env" }
}

function Set-RailwaySecret($key, $value, $environment) {
    $value | railway variable set $key --stdin --service foresight-app --environment $environment --skip-deploys | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to set $key in $environment" }
    Write-Host "set $key in $environment"
}

foreach ($environment in "dev", "main") {
    foreach ($key in $shared) {
        Set-RailwaySecret $key $values[$key] $environment
    }
    $database = $values["SUPABASE_DB_URL_$($environment.ToUpper())"]
    if ($database) {
        Set-RailwaySecret "SUPABASE_DB_URL" $database $environment
    } else {
        Write-Host "SUPABASE_DB_URL_$($environment.ToUpper()) not in .env: $environment keeps using the run folders"
    }
}
Write-Host "Done. The values take effect with the next deploy of each environment."
