[CmdletBinding()]
param()

# Stages the repo-level skills (single source of truth in <repo>\skills) into the agent
# folders that are packaged by azd. The staged copies are git-ignored.
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$skillsRoot = Join-Path $repoRoot "skills"

function Sync-Skill {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path -LiteralPath $Source)) { throw "Skill source not found: $Source" }
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
    Get-ChildItem -LiteralPath $Destination -Recurse -Directory -Filter "__pycache__" |
        Remove-Item -Recurse -Force
}

Sync-Skill (Join-Path $skillsRoot "watchlist-review") `
    (Join-Path $PSScriptRoot "stocktrader-agent\skills\watchlist-review")
Sync-Skill (Join-Path $skillsRoot "portfolio-complexity") `
    (Join-Path $PSScriptRoot "portfolio-manager-agent\skills\portfolio-complexity")
Sync-Skill (Join-Path $skillsRoot "pdf-generator\skills\pdf-generator") `
    (Join-Path $PSScriptRoot "portfolio-manager-agent\skills\pdf-generator")

Write-Host "Skills staged."
