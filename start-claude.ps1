# PhilReview Beta Testing Launcher (Windows)
#
# This script loads your .env file before starting Claude Code,
# ensuring telemetry and credentials are properly configured.
#
# Usage: .\start-claude.ps1

$ErrorActionPreference = "Stop"

# Change to script directory so .env lookup works regardless of where user invokes this
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Write-Host "Error: .env file not found in $(Get-Location)"
    Write-Host ""
    Write-Host "Please copy your personalized .env file (provided by the research team)"
    Write-Host "to this directory before running PhilReview."
    exit 1
}

# Load .env safely (parse KEY=VALUE only, don't execute arbitrary commands)
# This mirrors the safe parsing in start-claude.sh and setup-environment.sh
function Load-DotEnv {
    param([string]$EnvFile)

    if (-not (Test-Path $EnvFile)) { return }

    foreach ($line in Get-Content $EnvFile) {
        $line = $line.Trim()

        # Skip empty lines and comments
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith('#')) {
            continue
        }

        # Match KEY=VALUE pattern only
        if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim()

            # Strip surrounding quotes (single or double)
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }

            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

Load-DotEnv ".env"

# Run claude
& claude @args
