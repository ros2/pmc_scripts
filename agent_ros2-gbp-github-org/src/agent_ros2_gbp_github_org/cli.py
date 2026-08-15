import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

from agent_ros2_gbp_github_org.categories import (
    IssueCategory,
    NewReleaseRepository,
    NewReleaseTeam,
    UpdateReleaseTeamMembership,
    UnknownCategory,
)
from agent_ros2_gbp_github_org.categorize import categorize_issue
from agent_ros2_gbp_github_org.github import fetch_issue
from agent_ros2_gbp_github_org.implementer import ImplementPlanAgent
from agent_ros2_gbp_github_org.planner import TerraformConfigPlanner


async def _run_plan(
    path_to_ros2_gbp_github_org: Path,
    issue_data: dict[str, Any] | None = None,
    model: str = "gemini-3.5-flash-lite",
) -> None:
    if issue_data is None:
        print("Error: No issue data provided.", file=sys.stderr)
        sys.exit(1)

    category = categorize_issue(issue_data)
    if category == UnknownCategory:
        print(f"Error: Issue category '{category}' is not supported.", file=sys.stderr)
        sys.exit(1)

    planner = TerraformConfigPlanner(
        workspace=path_to_ros2_gbp_github_org,
        model=model,
    )
    plan = await planner.plan(issue_data, category=category)
    print(plan)

    issue_number = issue_data.get("number", "unknown")
    plan_filename = f"plan_ros2-gbp-github-org_{issue_number}.md"
    plan_path = Path.cwd() / plan_filename
    plan_path.write_text(plan + "\n", encoding="utf-8")


async def _run_implement(
    path_to_ros2_gbp_github_org: Path,
    plan_path: Path,
    model: str = "gemini-3.5-flash-lite",
) -> None:
    if not plan_path.exists():
        print(f"Error: Plan file '{plan_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    plan_text = plan_path.read_text(encoding="utf-8")
    implementer = ImplementPlanAgent(
        workspace=path_to_ros2_gbp_github_org,
        model=model,
    )
    result = await implementer.implement(plan_text)
    print(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI tool for agent_ros2-gbp-github-org."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # plan subcommand
    plan_parser = subparsers.add_parser(
        "plan",
        help="Generate a Terraform configuration plan for a GitHub issue.",
    )
    plan_parser.add_argument(
        "--path-to-ros2-gbp-github-org",
        type=Path,
        required=True,
        help="Path to a git clone of https://github.com/ros2-gbp/ros2-gbp-github-org/",
    )
    plan_parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.5-flash-lite",
        help="Gemini model to use for planning (default: gemini-3.5-flash-lite).",
    )
    group = plan_parser.add_mutually_exclusive_group()
    group.add_argument(
        "--issue-json",
        type=Path,
        default=None,
        help="Used to load eval issues instead of fetching them from github.",
    )
    group.add_argument(
        "--issue",
        type=str,
        default=None,
        help="Issue number or URL (e.g., 1107 or https://github.com/ros2-gbp/ros2-gbp-github-org/issues/1107).",
    )

    # implement subcommand
    implement_parser = subparsers.add_parser(
        "implement",
        help="Apply a Terraform configuration plan to the repository.",
    )
    implement_parser.add_argument(
        "--path-to-ros2-gbp-github-org",
        type=Path,
        required=True,
        help="Path to a git clone of https://github.com/ros2-gbp/ros2-gbp-github-org/",
    )
    implement_parser.add_argument(
        "--plan",
        type=Path,
        required=True,
        help="Path to the plan markdown file.",
    )
    implement_parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.5-flash-lite",
        help="Gemini model to use for implementation (default: gemini-3.5-flash-lite).",
    )

    args = parser.parse_args()

    if args.subcommand == "plan":
        issue_data = None
        if args.issue is not None:
            try:
                issue_data = fetch_issue(args.issue)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.issue_json is not None:
            try:
                with open(args.issue_json, encoding="utf-8") as f:
                    issue_data = json.load(f)
            except Exception as e:
                print(
                    f"Error reading issue JSON file '{args.issue_json}': {e}",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            plan_parser.error("One of --issue or --issue-json is required.")

        asyncio.run(
            _run_plan(
                args.path_to_ros2_gbp_github_org,
                issue_data=issue_data,
                model=args.model,
            )
        )
    elif args.subcommand == "implement":
        asyncio.run(
            _run_implement(
                args.path_to_ros2_gbp_github_org,
                plan_path=args.plan,
                model=args.model,
            )
        )


if __name__ == "__main__":
    main()
