"""GitHub API utilities for fetching issues."""

import json
import os
from pathlib import Path
import re
from typing import Any
import urllib.error
import urllib.request


def parse_issue_reference(
    issue_ref: str,
    default_owner: str = "ros2-gbp",
    default_repo: str = "ros2-gbp-github-org",
) -> tuple[str, str, int]:
    """Parse an issue reference (URL or number) into (owner, repo, issue_number).

    Args:
        issue_ref: Issue number (e.g. 1107 or #1107) or GitHub URL.
        default_owner: Default repository owner if only an issue number is given.
        default_repo: Default repository name if only an issue number is given.

    Returns:
        tuple[str, str, int]: (owner, repo, issue_number)

    Raises:
        ValueError: If the issue reference is invalid.
    """
    issue_ref = issue_ref.strip()

    # Pattern 1: https://github.com/{owner}/{repo}/issues/{number}
    m = re.match(
        r"^https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)(?:[/?#].*)?$",
        issue_ref,
    )
    if m:
        return m.group(1), m.group(2), int(m.group(3))

    # Pattern 2: https://api.github.com/repos/{owner}/{repo}/issues/{number}
    m = re.match(
        r"^https?://api\.github\.com/repos/([^/]+)/([^/]+)/issues/(\d+)(?:[/?#].*)?$",
        issue_ref,
    )
    if m:
        return m.group(1), m.group(2), int(m.group(3))

    # Pattern 3: #1107 or 1107
    m = re.match(r"^#?(\d+)$", issue_ref)
    if m:
        return default_owner, default_repo, int(m.group(1))

    raise ValueError(
        f"Invalid issue reference: '{issue_ref}'. Expected an issue number (e.g. 1107) "
        "or a GitHub URL (e.g. https://github.com/ros2-gbp/ros2-gbp-github-org/issues/1107)."
    )


def fetch_issue(
    issue_ref: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Fetch an issue from GitHub given an issue number or URL.

    Args:
        issue_ref: Issue number (e.g. 1107) or URL (e.g. https://github.com/ros2-gbp/ros2-gbp-github-org/issues/1107).
        token: Optional GitHub token. If None, checks GITHUB_TOKEN / GH_TOKEN env vars.

    Returns:
        dict[str, Any]: The issue JSON data.

    Raises:
        ValueError: If the issue reference cannot be parsed.
        RuntimeError: If fetching the issue fails.
    """
    owner, repo, issue_number = parse_issue_reference(issue_ref)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agent_ros2-gbp-github-org",
    }
    github_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_msg = f"Failed to fetch issue {issue_ref} from GitHub API ({e.code} {e.reason})"
        if e.code == 404:
            error_msg += f": Issue #{issue_number} not found in repository {owner}/{repo}."
        elif e.code == 403:
            error_msg += ": Rate limit exceeded or access forbidden. Try setting GITHUB_TOKEN."
        raise RuntimeError(error_msg) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error while fetching issue {issue_ref}: {e.reason}") from e

    # Ensure author is populated for compatibility
    if "author" not in data and "user" in data and isinstance(data["user"], dict):
        data["author"] = data["user"].get("login", "")

    return data
