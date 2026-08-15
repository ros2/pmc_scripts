"""Plan implementation agent."""

import os
from pathlib import Path
from typing import Any

from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.hooks import policy

IMPLEMENTER_SYSTEM_INSTRUCTIONS = """You are an automated implementation agent for the ros2-gbp GitHub organization.
Your task is to take a proposed Terraform change plan and apply the changes directly to the Terraform configuration files in the workspace.

Instructions:
1. Carefully read the plan provided by the user.
2. Inspect the relevant Terraform files (.tf) in the workspace.
3. Apply the exact changes specified in the plan:
   - Create any new team .tf files with the exact specified locals and module blocks.
   - Modify existing .tf files (e.g. adding team members, adding repositories, updating 00-members.tf, updating 00-repositories.tf).
4. Maintain exact formatting:
   - 2-space indents, trailing commas in lists.
   - Lists of members and repositories must follow standard ASCII alphabetical order (where uppercase letters precede lowercase letters).
   - If adding a user, check existing `.tf` files to preserve canonical username capitalization if present.
5. Do NOT commit the changes to git. Only write/edit the files in the workspace.
"""


class ImplementPlanAgent:
    """Agent that applies a Terraform plan to repository files."""

    def __init__(
        self,
        workspace: Path,
        api_key: str | None = None,
        model: str = "gemini-3.5-flash-lite",
    ):
        self.workspace = Path(workspace).resolve()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model

    async def implement(self, plan_text: str) -> str:
        """Apply the changes described in the plan to the workspace files.

        Args:
            plan_text: The markdown plan text.

        Returns:
            str: The response from the implementation agent.
        """
        config = LocalAgentConfig(
            api_key=self.api_key,
            model=self.model,
            workspaces=[str(self.workspace)],
            system_instructions=IMPLEMENTER_SYSTEM_INSTRUCTIONS,
            policies=[policy.allow_all()],
        )

        prompt = f"""Please implement the following Terraform plan in the workspace by modifying or creating the required .tf files:

{plan_text}

Apply all changes to the files now.
"""

        async with Agent(config) as agent:
            response = await agent.chat(prompt)
            return await response.text()
