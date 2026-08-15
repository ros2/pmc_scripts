"""Tests for categorize_issue against the evals dataset and edge cases."""

from collections.abc import Iterator
import json
from pathlib import Path
import pytest

from agent_ros2_gbp_github_org import (
    IssueCategory,
    NewReleaseRepository,
    NewReleaseTeam,
    UpdateReleaseTeamMembership,
    UnknownCategory,
    categorize_issue,
)

EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"

MARKER_MAP = {
    "NEW_RELEASE_REPOSITORY": NewReleaseRepository,
    "NEW_RELEASE_TEAM": NewReleaseTeam,
    "UPDATE_RELEASE_TEAM_MEMBERSHIP": UpdateReleaseTeamMembership,
    "NO_TEMPLATE": UnknownCategory,
}


def get_eval_cases():
    """Discover all test cases in the evals directory."""
    cases = []
    for folder in sorted(EVALS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        marker_name = None
        expected_cat = None
        for marker, category in MARKER_MAP.items():
            if (folder / marker).exists():
                marker_name = marker
                expected_cat = category
                break
        if marker_name is not None:
            cases.append((folder.name, folder, expected_cat))
    return cases


EVAL_CASES = get_eval_cases()


def get_template_folders(category: IssueCategory) -> Iterator[Path]:
    """Yield template folders matching the given IssueCategory."""
    yielded = False
    for _, folder, expected in EVAL_CASES:
        if expected == category:
            yielded = True
            yield folder
    assert yielded, f"No template folders found for category {category}"


@pytest.mark.parametrize("case_name, folder, expected_category", EVAL_CASES)
def test_categorize_issue_evals(case_name, folder, expected_category):
    """Test categorize_issue against each case in the evals directory."""
    issue_file = folder / "issue.json"
    assert issue_file.exists(), f"Missing issue.json in {folder}"

    with open(issue_file, encoding="utf-8") as f:
        issue_dict = json.load(f)

    result = categorize_issue(issue_dict)
    assert result == expected_category, (
        f"Failed for {case_name}: expected {expected_category}, got {result}"
    )


def test_categorize_no_template():
    """Verify that NO_TEMPLATE marker evals return UnknownCategory."""
    for folder in get_template_folders(UnknownCategory):
        with open(folder / "issue.json", encoding="utf-8") as f:
            issue_dict = json.load(f)
        assert categorize_issue(issue_dict) == UnknownCategory


def test_categorize_empty_or_unknown():
    """Verify unknown / empty issues return UnknownCategory."""
    assert categorize_issue({}) == UnknownCategory
    assert categorize_issue({"title": "Random question", "body": "How do I do X?"}) == UnknownCategory
    assert categorize_issue({"title": "Test", "body": ""}) == UnknownCategory
