[CmdletBinding()]
param(
    [switch]$SkipSmokeTest,
    [switch]$SkipTests,
    [string]$SmokeTestPrompt
)

# Deploys the three Python Foundry hosted agents (InvestorAgent, StockTraderAgent,
# PortfolioManagerAgent) with code deploy (no Docker) into an existing Foundry project.
$ErrorActionPreference = "Stop"
$previousEnvironment = @{}
$locationPushed = $false

function Invoke-Native {
    param([string]$Description, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Description failed (exit code $LASTEXITCODE)." }
}

try {
    $projectRoot = Join-Path $PSScriptRoot "portfolio-agents"
    $envFile = Join-Path $projectRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        $envFile = Join-Path $projectRoot ".env.example"
    }
    $required = @(
        "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "AZURE_LOCATION",
        "FOUNDRY_ACCOUNT_NAME", "FOUNDRY_PROJECT_NAME", "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        "AZURE_ENV_NAME", "AGENT_NAME_SUFFIX", "TRADER_TOOLBOX_NAME", "MANAGER_TOOLBOX_NAME",
        "EMAIL_RECIPIENT"
    )
    $settings = @{}
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*(?:#.*)?$') { continue }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { throw "Invalid assignment in '$envFile'." }
        $settings[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
    }
    foreach ($key in $required) {
        if ([string]::IsNullOrWhiteSpace($settings[$key])) { throw "Required setting '$key' is missing from '$envFile'." }
    }
    foreach ($key in "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID") {
        $guid = [guid]::Empty
        if (-not [guid]::TryParse($settings[$key], [ref]$guid)) { throw "Setting '$key' must be a GUID." }
    }

    $suffix = $settings["AGENT_NAME_SUFFIX"]
    $agentNames = @{
        "investor-agent"          = "InvestorAgent-$suffix"
        "stocktrader-agent"       = "StockTraderAgent-$suffix"
        "portfolio-manager-agent" = "PortfolioManagerAgent-$suffix"
    }
    $azureYaml = Get-Content -LiteralPath (Join-Path $projectRoot "azure.yaml") -Raw
    foreach ($name in $agentNames.Values) {
        if ($azureYaml -notmatch [regex]::Escape($name)) {
            throw "azure.yaml does not define '$name'. Keep AGENT_NAME_SUFFIX and azure.yaml in sync."
        }
    }

    $projectResourceId = "/subscriptions/$($settings['AZURE_SUBSCRIPTION_ID'])/resourceGroups/$($settings['AZURE_RESOURCE_GROUP'])/providers/Microsoft.CognitiveServices/accounts/$($settings['FOUNDRY_ACCOUNT_NAME'])/projects/$($settings['FOUNDRY_PROJECT_NAME'])"
    $projectEndpoint = "https://$($settings['FOUNDRY_ACCOUNT_NAME']).services.ai.azure.com/api/projects/$($settings['FOUNDRY_PROJECT_NAME'])"

    foreach ($tool in "azd", "az", "python") {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "'$tool' is not installed or not on PATH." }
    }

    # Authentication is interactive and user-owned; fail early with instructions.
    $account = az account show --query "{t:tenantId,s:id}" -o json 2>$null | ConvertFrom-Json
    if (-not $account -or $account.t -ne $settings["AZURE_TENANT_ID"] -or $account.s -ne $settings["AZURE_SUBSCRIPTION_ID"]) {
        throw "Run: az login --tenant $($settings['AZURE_TENANT_ID']); az account set --subscription $($settings['AZURE_SUBSCRIPTION_ID'])"
    }
    & azd auth login --check-status --tenant-id $settings["AZURE_TENANT_ID"] *> $null
    if ($LASTEXITCODE -ne 0) { throw "Run: azd auth login --tenant-id $($settings['AZURE_TENANT_ID'])" }

    $previousEnvironment["AZURE_DEV_USER_AGENT"] = $env:AZURE_DEV_USER_AGENT
    $env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"

    & (Join-Path $projectRoot "sync-skills.ps1")

    if (-not $SkipTests) {
        $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
        if (Test-Path -LiteralPath $venvPython) {
            Invoke-Native "Unit tests" { & $venvPython -m pytest (Join-Path $projectRoot "tests") -q -p no:cacheprovider }
        }
        else {
            Write-Warning "No .venv found in portfolio-agents; skipping unit tests."
        }
    }

    Push-Location $projectRoot
    $locationPushed = $true

    $environments = (& azd env list --output json) | ConvertFrom-Json
    if ($settings["AZURE_ENV_NAME"] -in @($environments.Name)) {
        Invoke-Native "azd env select" { & azd env select $settings["AZURE_ENV_NAME"] }
    }
    else {
        Invoke-Native "azd env new" { & azd env new $settings["AZURE_ENV_NAME"] --no-prompt }
    }
    $azdValues = @{
        AZURE_TENANT_ID                = $settings["AZURE_TENANT_ID"]
        AZURE_SUBSCRIPTION_ID          = $settings["AZURE_SUBSCRIPTION_ID"]
        AZURE_RESOURCE_GROUP           = $settings["AZURE_RESOURCE_GROUP"]
        AZURE_LOCATION                 = $settings["AZURE_LOCATION"]
        AZURE_AI_PROJECT_ID            = $projectResourceId
        AZURE_AI_PROJECT_ENDPOINT      = $projectEndpoint
        FOUNDRY_PROJECT_ENDPOINT       = $projectEndpoint
        FOUNDRY_PROJECT_RESOURCE_ID    = $projectResourceId
        AZURE_AI_MODEL_DEPLOYMENT_NAME = $settings["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
        EMAIL_RECIPIENT                = $settings["EMAIL_RECIPIENT"]
    }
    foreach ($key in $azdValues.Keys) {
        Invoke-Native "azd env set $key" { & azd env set $key $azdValues[$key] }
    }

    # Project connections (user identity passthrough for Outlook mail; web search needs none).
    Invoke-Native "Create the Outlook mail connection" {
        & azd ai connection create outlook-mail-conn --kind remote-tool `
            --target "https://agent365.svc.cloud.microsoft/agents/servers/mcp_MailTools" `
            --auth-type user-entra-token --audience "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1" `
            --project-endpoint $projectEndpoint --force --no-prompt
    }

    # Toolboxes are recreated so that the definition always matches the files in toolboxes\.
    $existing = ((& azd ai toolbox list --output json | Where-Object { $_ -notmatch '^\d{4}/' }) -join "`n" | ConvertFrom-Json).toolboxes.name
    foreach ($pair in @(@($settings["TRADER_TOOLBOX_NAME"], "trader-tools.yaml"), @($settings["MANAGER_TOOLBOX_NAME"], "manager-tools.yaml"))) {
        if ($pair[0] -in @($existing)) {
            Invoke-Native "Delete toolbox $($pair[0])" { & azd ai toolbox delete $pair[0] --no-prompt --force }
        }
        Invoke-Native "Create toolbox $($pair[0])" { & azd ai toolbox create $pair[0] --from-file (Join-Path "toolboxes" $pair[1]) --no-prompt }
    }
    Invoke-Native "Set TRADER_TOOLBOX_ENDPOINT" { & azd env set TRADER_TOOLBOX_ENDPOINT "$projectEndpoint/toolboxes/$($settings['TRADER_TOOLBOX_NAME'])/mcp?api-version=v1" }
    Invoke-Native "Set MANAGER_TOOLBOX_ENDPOINT" { & azd env set MANAGER_TOOLBOX_ENDPOINT "$projectEndpoint/toolboxes/$($settings['MANAGER_TOOLBOX_NAME'])/mcp?api-version=v1" }

    # The manager calls the other two agents, so they are deployed first.
    foreach ($service in "investor-agent", "stocktrader-agent", "portfolio-manager-agent") {
        Invoke-Native "azd deploy $service" { & azd deploy $service --no-prompt }
        Invoke-Native "Verify $service" { & azd ai agent show $service --output json }
    }

    if (-not $SkipSmokeTest) {
        if ([string]::IsNullOrWhiteSpace($SmokeTestPrompt)) {
            $SmokeTestPrompt = @"
Change the portfolio to maximize the win and minimize the risk.
Name,Ticker,Qty,Invested,P&L,P&L %
Pepsico Inc.,US7134481081,10,1 445.68 USD,-127.17 USD,-8.8%
Microsoft Corp.,US5949181045,5,2 100.00 USD,150 USD,+7.1%
"@
        }
        Invoke-Native "Smoke test" {
            & azd ai agent invoke portfolio-manager-agent --new-session --new-conversation $SmokeTestPrompt
        }
    }
}
finally {
    if ($locationPushed) { Pop-Location }
    foreach ($key in $previousEnvironment.Keys) {
        if ($null -eq $previousEnvironment[$key]) { Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($key, $previousEnvironment[$key], "Process") }
    }
}
