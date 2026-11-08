# Copyright (c) Microsoft. All rights reserved.

import os
from pathlib import Path

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

INSTRUCTIONS = (Path(__file__).parent / "instructions.txt").read_text(encoding="utf-8").strip()


def main() -> None:
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )

    agent = Agent(
        client=client,
        name="InvestorAgent",
        description="Investor Agent representing the client",
        instructions=INSTRUCTIONS,
        # The hosting infrastructure manages conversation history; low reasoning effort keeps the debate cheap.
        default_options={"store": False, "reasoning": {"effort": "low"}},
    )

    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
