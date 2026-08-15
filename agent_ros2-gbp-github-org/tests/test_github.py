"""Tests for GitHub issue fetching and parsing."""

import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from agent_ros2_gbp_github_org.github import fetch_issue, parse_issue_reference


def test_parse_issue_reference_number():
    assert parse_issue_reference("1107") == ("ros2-gbp", "ros2-gbp-github-org", 1107)
    assert parse_issue_reference("#1107") == ("ros2-gbp", "ros2-gbp-github-org", 1107)
    assert parse_issue_reference("  123  ") == ("ros2-gbp", "ros2-gbp-github-org", 123)


def test_parse_issue_reference_url():
    owner, repo, num = parse_issue_reference(
        "https://github.com/ros2-gbp/ros2-gbp-github-org/issues/1107"
    )
    assert (owner, repo, num) == ("ros2-gbp", "ros2-gbp-github-org", 1107)

    owner, repo, num = parse_issue_reference(
        "https://github.com/custom-org/custom-repo/issues/42#issuecomment-123"
    )
    assert (owner, repo, num) == ("custom-org", "custom-repo", 42)

    owner, repo, num = parse_issue_reference(
        "https://api.github.com/repos/ros2-gbp/ros2-gbp-github-org/issues/1107"
    )
    assert (owner, repo, num) == ("ros2-gbp", "ros2-gbp-github-org", 1107)


def test_parse_issue_reference_invalid():
    with pytest.raises(ValueError):
        parse_issue_reference("not-an-issue")

    with pytest.raises(ValueError):
        parse_issue_reference("https://example.com/other")


def test_fetch_issue_mocked():
    sample_response = {
        "number": 1107,
        "title": "Add release team",
        "user": {"login": "Masa0u0"},
        "body": "Issue body content",
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        data = fetch_issue("1107")
        assert data["number"] == 1107
        assert data["title"] == "Add release team"
        assert data["author"] == "Masa0u0"


def test_fetch_issue_not_found():
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError("url", 404, "Not Found", {}, None),
    ):
        with pytest.raises(RuntimeError, match="not found"):
            fetch_issue("999999")
