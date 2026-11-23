<#
Copies the secrets from the local .env file to the Railway service foresight-app.

- OPENAI_API_KEY, the Google sign-in keys (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
  AUTH_COOKIE_SECRET, FORESIGHT_DEVELOPERS and RESEND_API_KEY: the same value in both
  environments (ADR-003). A missing AUTH_COOKIE_SECRET is generated and saved to .env first.
- SUPABASE_DB_URL: each environment gets its own Supabase project (ADR-026), from
  SUPABASE_DB_URL_DEV and SUPABASE_DB_URL_MAIN in .env (skipped if they are not there yet).
- SUPABASE_SECRET_KEY: that project's secret key, for the run files in Supabase Storage
  (ADR-033), from SUPABASE_SECRET_KEY_DEV and SUPABASE_SECRET_KEY_MAIN (skipped if missing).

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
$perEnvironment = "SUPABASE_DB_URL", "SUPABASE_SECRET_KEY"
$pattern = '^\s*(' + (($shared + ($perEnvironment | ForEach-Object { "$($_)_DEV", "$($_)_MAIN" })) -join '|') +
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

$railway = (Get-Command railway -CommandType Application).Source

function Set-RailwaySecret($key, $value, $environment) {
    # Write the exact UTF-8 bytes to the CLI's stdin. Piping a string from Windows PowerShell
    # can prepend a byte-order mark, which then becomes part of the value (2026-11-21: every
    # value started with U+FEFF and the database URL no longer parsed).
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $railway
    $info.Arguments = "variable set $key --stdin --service foresight-app --environment $environment --skip-deploys"
    $info.WorkingDirectory = $root  # the folder linked to the Railway project
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = [System.Diagnostics.Process]::Start($info)
    $bytes = (New-Object System.Text.UTF8Encoding $false).GetBytes($value)
    $process.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
    $process.StandardInput.Close()
    $null = $process.StandardOutput.ReadToEnd()
    $errors = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "Failed to set $key in $environment`: $($errors.Trim())" }
    Write-Host "set $key in $environment"
}

function Assert-RailwaySecrets($expected, $environment) {
    # Read the values back and compare them in memory (nothing is printed)
    $stored = & $railway variables --service foresight-app --environment $environment --json | Out-String | ConvertFrom-Json
    foreach ($key in $expected.Keys) {
        if ($stored.$key -cne $expected[$key]) { throw "$key in $environment does not match .env" }
    }
    Write-Host "verified $($expected.Count) values in $environment"
}

foreach ($environment in "dev", "main") {
    $expected = @{}
    foreach ($key in $shared) {
        Set-RailwaySecret $key $values[$key] $environment
        $expected[$key] = $values[$key]
    }
    foreach ($key in $perEnvironment) {
        $value = $values["$($key)_$($environment.ToUpper())"]
        if ($value) {
            Set-RailwaySecret $key $value $environment
            $expected[$key] = $value
        } else {
            Write-Host "$($key)_$($environment.ToUpper()) not in .env: skipped in $environment"
        }
    }
    Assert-RailwaySecrets $expected $environment
}
Write-Host "Done. The values take effect with the next deploy of each environment."
