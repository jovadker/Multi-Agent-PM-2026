# Multi-Agent PM 2026

This repository contains a Microsoft Copilot / Power Platform demo for multi-agent portfolio management. It brings together reusable skills and a Power Platform solution that includes four agents, using the bot names defined in the solution folder:

- `portfoliomanager`
- `stocktraderagent`
- `investoragent`
- `superagent`

The repo is organized into two main areas:

- `skills/` — reusable agent skills for portfolio analysis, PDF generation, and watchlist review
- `solution/` — extracted Power Platform solution package containing the agent definitions and supporting components

## What this repo demonstrates

The scenario is built around a portfolio management workflow where different agents focus on different tasks:

- `portfoliomanager_20260920` focuses on portfolio health and prioritization
- `stocktraderagent_20260920` evaluates market opportunities and watchlist items
- `investoragent_20260920` supports investment reasoning and scenario evaluation
- `superagent` performs broader orchestration across the workflow

This follows the core idea that portfolio management is not a single-agent task; it is a multi-agent workflow with specialized reasoning and role separation.

## Skills included

The repo currently includes the following skills under `skills/`:

- `portfolio-complexity` — helps identify which holdings or names deserve more attention
- `pdf-generator` — generates polished output for summaries and briefing packs
- `watchlist-review` — ranks watchlist items by actionability and opportunity quality

## Recommended deployment option

Important: the simplest and safest deployment path is to deploy the solution with the Power Platform CLI (`pac cli`) into a new environment.

This is the preferred option because it:

- creates a clean sandbox for demos and validation
- avoids conflicts with an existing production or shared environment
- reduces tenant governance and configuration risk
- is the fastest way to get a working deployment live for experimentation

### Recommended flow

Run these commands from the repository root. They package the extracted solution in `solution/` and import that package into the new environment:

```powershell
pac auth create --url https://<your-environment>.crm.dynamics.com
pac solution pack --folder .\solution --zipfile .\cfobrunch_20260920.zip
pac solution import --path .\cfobrunch_20260920.zip --environment https://<your-environment>.crm.dynamics.com
```

The solution is already extracted in this repository, so `pac solution init` is not needed. The pack step creates the importable ZIP from the repository's solution files; the import step deploys it to the environment you authenticated against.

## Repository structure

```text
Multi-Agent-PM-2026/
├── README.md
├── skills/
│   ├── portfolio-complexity/
│   ├── pdf-generator/
│   └── watchlist-review/
├── solution/
│   ├── bots/
│   ├── botcomponents/
│   ├── Assets/
│   ├── Workflows/
│   ├── customizations.xml
│   ├── solution.xml
│   └── [Content_Types].xml
├── transcript.txt
├── *.zip
└── _results/
```

## Private Blob Storage networking

The standalone Bicep template [infra/storage-private-endpoint.bicep](./infra/storage-private-endpoint.bicep) adds a VNet, a Blob private endpoint for the existing storage account, and the linked `privatelink.blob.core.windows.net` DNS zone. The default network is `172.20.0.0/16`, with a reserved delegated agent subnet (`172.20.0.0/24`) and a private-endpoint subnet (`172.20.1.0/24`). Private Endpoint, DNS, and data-processing charges apply.

Preview and deploy from the repository root:

```powershell
az deployment group what-if --subscription af8480ab-0054-4500-bdd8-bf0b553c8812 --resource-group rg-portfoliomanagement --template-file .\infra\storage-private-endpoint.bicep --parameters location=swedencentral
az deployment group create --subscription af8480ab-0054-4500-bdd8-bf0b553c8812 --resource-group rg-portfoliomanagement --name storage-private-network --template-file .\infra\storage-private-endpoint.bicep --parameters location=swedencentral
```

This template alone is a network foundation: it does **not** configure Foundry VNet integration, alter agents, change storage public access or authentication, or assign roles. It reserves a delegated subnet; the separate private Foundry deployment below attaches the new account to that subnet. Agents in the original public account still have no private outbound route. An inbound Foundry private endpoint alone would not provide that outbound route.

Verify the approved Blob private endpoint and DNS A record in Azure. From a client connected to the VNet (or a correctly configured peered/VPN network), resolve `saportfoliomanagement.blob.core.windows.net` and confirm it returns the endpoint's private IP, then test an authenticated upload and download. A local workstation outside the VNet cannot validate private connectivity without an appropriate network connection and DNS configuration.

### Separate private Foundry account

[infra/foundry-private.bicep](./infra/foundry-private.bicep) creates a separate Basic Foundry account and project on the existing VNet. It configures outbound injection into `snet-agents`, a Foundry private endpoint in `snet-private-endpoints`, three private DNS zones and VNet links, a project-level agent capability host, and the specified user's project-scoped Foundry User role. The existing public Foundry account, agents, and storage are not modified.

The template uses the supported Basic VNet setup with **platform-managed agent storage**, not `saportfoliomanagement` as its default Files store. It does not deploy models, migrate agents/skills/connections, or configure a VPN, runner, or jump host. New private endpoints and DNS incur charges; agent/model usage is billed separately. Access to the new project's data plane requires a VNet-connected client with private DNS resolution.

```powershell
$projectUserObjectId = az ad signed-in-user show --query id -o tsv
az deployment group what-if --subscription af8480ab-0054-4500-bdd8-bf0b553c8812 --resource-group rg-portfoliomanagement --template-file .\infra\foundry-private.bicep --parameters projectUserObjectId=$projectUserObjectId
az deployment group create --subscription af8480ab-0054-4500-bdd8-bf0b553c8812 --resource-group rg-portfoliomanagement --name foundry-private --template-file .\infra\foundry-private.bicep --parameters projectUserObjectId=$projectUserObjectId
```

The account/project APIs support VNet injection; the capability-host declaration retains the legacy API used by Microsoft's [Basic VNet sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet). Capability-host provisioning can take 10-20 minutes. Do not repoint the agent subnet to the original account: outbound injection is a creation-time setting, and the subnet is exclusive to the new account.

The deployed private account is `foundry-portfoliomanagement-private`, with project `proj-portfoliomanagement-private` in `rg-portfoliomanagement` (Sweden Central). Its project endpoint is `https://foundry-portfoliomanagement-private.services.ai.azure.com/api/projects/proj-portfoliomanagement-private`. The deployment, VNet injection, agent capability host, private endpoint approval, DNS records/links, and project user role were verified through Azure management APIs. Agent execution and file uploads still require a model/agent deployment and testing from a VNet-connected client; they have not been verified.

### Optional project storage connection

The private Foundry template above uses platform-managed storage. If you subsequently connect `saportfoliomanagement` as the project's default storage, use [infra/foundry-project-storage.bicep](./infra/foundry-project-storage.bicep) to update that **existing connection** to Entra managed-identity authentication and grant the project's identity **Storage Blob Data Contributor** on the storage account. Set `connectionName` to the actual connection name; the provided default matches the connection created in this environment.

```powershell
az deployment group what-if --subscription af8480ab-0054-4500-bdd8-bf0b553c8812 --resource-group rg-portfoliomanagement --template-file .\infra\foundry-project-storage.bicep
az deployment group create --subscription af8480ab-0054-4500-bdd8-bf0b553c8812 --resource-group rg-portfoliomanagement --name foundry-project-storage --template-file .\infra\foundry-project-storage.bicep
```

This template does not change networking, the original Foundry account, or agent definitions. The project's storage identity differs from both the original project's identity and the agent's identity; permissions do not transfer when you create a new project. Account-key connections cannot work when shared-key storage access is disabled.

A failed skill upload can leave a skill in `Creating` with no published versions. Subsequent uploads then return 409. Correct the underlying storage/network error before deleting the incomplete registration and retrying. Do not delete a working skill or its versions merely to clear a conflict.

After deploying this storage fix, the `pdf-generator` ZIP was uploaded successfully to `proj-portfoliomanagement-private`; version `1` and its default-version reference were verified through the Skills API. This verifies skill publication, not PDF execution or agent attachment.

## Notes

- Use a new environment for initial deployment and demo validation
- Keep the implementation isolated before promoting anything to shared or production environments
- Treat the PAC CLI deployment as the easiest and most reliable path for this repo
