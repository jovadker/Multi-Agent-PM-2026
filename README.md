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

## Notes

- Use a new environment for initial deployment and demo validation
- Keep the implementation isolated before promoting anything to shared or production environments
- Treat the PAC CLI deployment as the easiest and most reliable path for this repo
