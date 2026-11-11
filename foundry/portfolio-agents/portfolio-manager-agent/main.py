# Copyright (c) Microsoft. All rights reserved.
"""Portfolio manager: the trader and the investor are used as tools (agents as tools).

https://learn.microsoft.com/en-us/agent-framework/journey/agents-as-tools
"""

import asyncio
import os
from pathlib import Path

from agent_framework import Agent
from agent_framework.foundry import FoundryAgent, FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from report_tools import classify_portfolio, generate_pdf_report, render_chart

load_dotenv()

INSTRUCTIONS = (Path(__file__).parent / "instructions.txt").read_text(encoding="utf-8").strip()


def hosted_agent_as_tool(project_endpoint, credential, agent_name, tool_name, description):
    """Connect to a deployed Foundry hosted agent and expose it as a function tool."""
    # allow_preview=True makes the client call the agent's own endpoint,
    # which is the only way to call a hosted agent.
    agent = FoundryAgent(
        project_endpoint=project_endpoint,
        agent_name=agent_name,
        credential=credential,
        allow_preview=True,
    )
    return agent.as_tool(name=tool_name, description=description, arg_name="task")


async def main() -> None:
    credential = DefaultAzureCredential()
    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

    trader = hosted_agent_as_tool(
        project_endpoint, credential, os.environ["TRADER_AGENT_NAME"],
        "StockTraderAgent", "Stock trading agent",
    )
    investor = hosted_agent_as_tool(
        project_endpoint, credential, os.environ["INVESTOR_AGENT_NAME"],
        "InvestorAgent", "Investor Agent representing the client",
    )

    # The toolbox provides the Microsoft 365 Outlook mail tools used to send the summary.
    email_tools = FoundryToolbox(credential)

    client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    recipient = os.environ.get("EMAIL_RECIPIENT", "admin@Caldova98029632.onmicrosoft.com")
    agent = Agent(
        client=client,
        name="PortfolioManager",
        description="Portfolio manager facilitating the trader and investor agents",
        instructions=f"{INSTRUCTIONS}\nEMAIL_RECIPIENT: {recipient}",
        tools=[trader, investor, classify_portfolio, render_chart, generate_pdf_report, email_tools],
        default_options={"store": False, "reasoning": {"effort": "low"}},
    )

    await ResponsesHostServer(agent).run_async()


if __name__ == "__main__":
    asyncio.run(main())
