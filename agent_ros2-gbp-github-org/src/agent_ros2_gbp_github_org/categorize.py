"""Categorize GitHub issues for ros2-gbp-github-org."""

import re
from typing import Any, Mapping

from agent_ros2_gbp_github_org.categories import (
    IssueCategory,
    NewReleaseRepository,
    NewReleaseTeam,
    UpdateReleaseTeamMembership,
    UnknownCategory,
)


def categorize_issue(issue: Mapping[str, Any]) -> IssueCategory:
    """Categorize a GitHub issue into one of the release issue categories.

    Args:
        issue: A mapping representation of a GitHub issue.

    Returns:
        IssueCategory: NewReleaseRepository, NewReleaseTeam,
        UpdateReleaseTeamMembership, or UnknownCategory.
    """
    title = str(issue.get("title") or "").strip()
    body = str(issue.get("body") or "").strip()

    # 1. UpdateReleaseTeamMembership:
    # Look for updates to team membership template headers or phrases
    if (
        re.search(r"updates?\s+to\s+.*membership", body, re.IGNORECASE)
        or re.search(r"update\s+release\s+team\s+membership", title, re.IGNORECASE)
        or re.search(r"##\s*(?:New team members|Team members to remove)", body, re.IGNORECASE)
    ):
        return IssueCategory.UpdateReleaseTeamMembership

    # 2. NewReleaseTeam:
    # New release teams list initial team members or ask for "name of the new release team"
    has_team_members = bool(re.search(r"[*#]+\s*(?:New\s+)?team\s+members", body, re.IGNORECASE))
    has_new_team_in_body = bool(re.search(r"name\s+of\s+(?:the\s+)?new\s+release\s+team", body, re.IGNORECASE))
    has_add_team_title = bool(
        re.search(r"^add\s+(?:[^\n]*\s+)?release\s+team\b", title, re.IGNORECASE)
        and not re.search(r"repositor(?:y|ies)", title, re.IGNORECASE)
    )

    if has_new_team_in_body or has_team_members or has_add_team_title:
        return IssueCategory.NewReleaseTeam

    # 3. NewReleaseRepository:
    # Adding repositories to an existing release team
    has_add_repo_title = bool(re.search(r"add\s+(?:new\s+)?(?:release\s+)?repositor(?:y|ies)", title, re.IGNORECASE))
    has_release_team_in_body = bool(re.search(r"name\s+of\s+(?:the\s+)?release\s+team", body, re.IGNORECASE))
    has_repos_to_add_in_body = bool(re.search(r"release\s+repositories\s+to\s+add", body, re.IGNORECASE))
    has_rosdistro_source_entry = bool(re.search(r"\[ros/.*source\s+entry", body, re.IGNORECASE))

    if (
        has_add_repo_title
        or has_release_team_in_body
        or has_repos_to_add_in_body
        or has_rosdistro_source_entry
    ):
        return IssueCategory.NewReleaseRepository

    return IssueCategory.UnknownCategory
