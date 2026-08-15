"""Terraform configuration planner agent."""

import os
from pathlib import Path
from typing import Any, Mapping

from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.hooks import policy

from agent_ros2_gbp_github_org.categories import (
    IssueCategory,
    NewReleaseRepository,
    NewReleaseTeam,
    UpdateReleaseTeamMembership,
)

PLANNER_SYSTEM_INSTRUCTIONS = """You are a Terraform configuration planning agent for the ros2-gbp GitHub organization.
Your role is to analyze a GitHub issue and inspect the repository's existing Terraform files (.tf), then output a concise, human-auditable plan describing what changes must be made to the Terraform configurations.

Do not edit any files. You only inspect files and write a concise plan.

Key repository conventions for ros2-gbp-github-org:
1. Team configuration files:
   - Each release team is defined in `<team_name>.tf` (e.g. `nobleo.tf`, `pal_robotics.tf`, or `_42dot.tf` if starting with a digit).
   - Format:
     ```terraform
     locals {
       <team_name>_team = [
         "member1",
         "member2",
       ]
       <team_name>_repositories = [
         "repo1-release",
         "repo2-release",
       ]
     }

     module "<team_name>_team" {
       source       = "./modules/release_team"
       team_name    = "<team_name>"
       members      = local.<team_name>_team
       repositories = local.<team_name>_repositories
       depends_on   = [github_membership.members, github_repository.repositories]
     }
     ```
   - All release repository names have `-release` appended.
   - Lists of members and repositories are kept in standard ASCII alphabetical order (uppercase letters precede lowercase letters, matching standard sort).
   - Check existing `.tf` files if a username has specific canonical capitalization.

2. Global repository list (`00-repositories.tf`):
   - Contains `locals { organization_repositories = setunion(...) }`
   - If a new team is created, `local.<team_name>_repositories` must be added in alphabetical order.

3. Global membership list (`00-members.tf`):
   - Contains `locals { members = setunion(...) }`
   - If a new team is created, `local.<team_name>_team` must be added in alphabetical order.

Output Format Rules:
- Keep the report concise.
- Omit numbers or letters for section headings and subsections (do NOT use "1.", "2.", "A.", "B.", etc.).
- Use level-2 markdown headings (`##`).
- Standard sections:
  ## <Category Name in Title Case>
  `<Author>` requests that the following new repositories be created for the team `<team>`:
  * `<repo_name>-release` - <Must state whether there is an existing release repository that needs to be imported or not. E.g. "There is no existing release repository that needs to be imported." or "Existing release repository to be imported from <URL>.">

  ## Current State
  * Bullet points covering: author membership in the team, presence of `<team>.tf` with member/repo counts, status in `00-repositories.tf` and `00-members.tf`, and whether changes to 00-*.tf are needed.

  ## Proposed Terraform Changes
  In `<filename>`, <short action description>:
  ```diff
  <diff snippet>
  ```
  (or ```terraform for newly created files)
"""


CATEGORY_TITLES = {
    IssueCategory.NewReleaseRepository: "New Release Repository",
    IssueCategory.NewReleaseTeam: "New Release Team",
    IssueCategory.UpdateReleaseTeamMembership: "Update Release Team Membership",
}


class TerraformConfigPlanner:
    """Agent that analyzes GitHub issues and plans Terraform changes."""

    def __init__(
        self,
        workspace: Path,
        api_key: str | None = None,
        model: str = "gemini-3.5-flash-lite",
    ):
        self.workspace = Path(workspace).resolve()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model

    async def plan(
        self,
        issue: Mapping[str, Any],
        category: IssueCategory | None = None,
    ) -> str:
        """Generate a Terraform change plan for the given issue.

        Args:
            issue: GitHub issue mapping containing title, body, number, author, etc.
            category: The determined IssueCategory.

        Returns:
            str: The planner agent's human-auditable plan.
        """
        config = LocalAgentConfig(
            api_key=self.api_key,
            model=self.model,
            workspaces=[str(self.workspace)],
            system_instructions=PLANNER_SYSTEM_INSTRUCTIONS,
            capabilities=types.CapabilitiesConfig(
                enabled_tools=list(types.BuiltinTools.read_only())
            ),
            policies=[policy.allow_all()],
        )

        title = issue.get("title", "")
        number = issue.get("number", "")
        author = issue.get("author", issue.get("user", {}).get("login", ""))
        body = issue.get("body", "")
        category_title = (
            CATEGORY_TITLES.get(category, category.value)
            if category
            else "Issue Plan"
        )

        prompt = f"""Please inspect the repository's Terraform files and plan the changes for this GitHub issue.

Category: {category_title}
Issue #{number}: {title}
Author: {author}

Issue Body:
{body}

Inspect the workspace (.tf files) as needed and output the plan following the concise format rules without numbering.
Make sure to include information on whether any existing release repository needs to be imported for each repository.
"""

        async with Agent(config) as agent:
            response = await agent.chat(prompt)
            return await response.text()
