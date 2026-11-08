# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os
from pathlib import Path

from agent_framework import Agent, SkillsProvider
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

HERE = Path(__file__).parent
INSTRUCTIONS = (HERE / "instructions.txt").read_text(encoding="utf-8").strip()


async def main() -> None:
    credential = DefaultAzureCredential()

    # The toolbox provides the web_search tool used for analyst recommendations and
    # 52-week targets. It is mandatory when hosted; ALLOW_NO_TOOLBOX is for local smoke tests only.
    tools = None
    if os.environ.get("TOOLBOX_ENDPOINT") or os.environ.get("TOOLBOX_NAME"):
        tools = FoundryToolbox(credential)
    elif os.environ.get("ALLOW_NO_TOOLBOX") != "1":
        raise RuntimeError("TOOLBOX_ENDPOINT is not set; the trader needs the web_search toolbox.")

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    # The agent runs unattended (called by the portfolio manager), so skill loading must not wait for approval.
    skills = SkillsProvider.from_paths(
        skill_paths=HERE / "skills",
        disable_load_skill_approval=True,
        disable_read_skill_resource_approval=True,
        disable_run_skill_script_approval=True,
    )

    agent = Agent(
        client=client,
        name="StockTraderAgent",
        description="Stock trading agent",
        instructions=INSTRUCTIONS,
        tools=tools,
        context_providers=[skills],
        default_options={"store": False},
    )

    await ResponsesHostServer(agent).run_async()


if __name__ == "__main__":
    asyncio.run(main())
