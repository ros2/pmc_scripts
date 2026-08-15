#!/usr/bin/env python3
"""Evaluation runner script for agent_ros2-gbp-github-org."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from agent_ros2_gbp_github_org import (
    IssueCategory,
    NewReleaseRepository,
    NewReleaseTeam,
    UpdateReleaseTeamMembership,
    UnknownCategory,
)

EVALS_DIR = Path(__file__).resolve().parent / "evals"

CATEGORY_TO_MARKER = {
    NewReleaseRepository: "NEW_RELEASE_REPOSITORY",
    NewReleaseTeam: "NEW_RELEASE_TEAM",
    UpdateReleaseTeamMembership: "UPDATE_RELEASE_TEAM_MEMBERSHIP",
    UnknownCategory: "NO_TEMPLATE",
}


def check_prerequisites(path_to_ros2_gbp_github_org: Path | None = None) -> bool:
    """Check that all prerequisites are satisfied before running evals.

    Returns:
        bool: True if all prerequisites are met, False otherwise.
    """
    errors = []

    if not os.environ.get("GEMINI_API_KEY"):
        errors.append(
            "Missing environment variable GEMINI_API_KEY.\n"
            "Please set your Gemini API key: export GEMINI_API_KEY='your-api-key'"
        )

    if not shutil.which("agent_ros2-gbp-github-org"):
        errors.append(
            "Executable 'agent_ros2-gbp-github-org' not found in PATH.\n"
            "Please make sure your virtual environment is activated and you have run:\n"
            "  pip install -e ."
        )

    if path_to_ros2_gbp_github_org is not None and not path_to_ros2_gbp_github_org.is_dir():
        errors.append(
            f"Path to ros2-gbp-github-org '{path_to_ros2_gbp_github_org}' does not exist or is not a directory."
        )

    if errors:
        print("=" * 60, file=sys.stderr)
        print("PREREQUISITE CHECK FAILED", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        for err in errors:
            print(f"- {err}\n", file=sys.stderr)
        return False

    print("Prerequisites verified:")
    print("  - GEMINI_API_KEY environment variable is set.")
    print("  - agent_ros2-gbp-github-org is installed and in PATH (via `pip install -e .`).")
    if path_to_ros2_gbp_github_org is not None:
        print(f"  - Path to ros2-gbp-github-org exists: {path_to_ros2_gbp_github_org}\n")
    else:
        print()
    return True


def prompt_confirmation() -> bool:
    """Display warning and prompt user for confirmation."""
    print("=" * 60)
    print("WARNING: EXPENSIVE EVALUATION SCRIPT")
    print("=" * 60)
    print("This script runs evaluations against the dataset and will invoke")
    print("the 'agent_ros2-gbp-github-org' CLI, making a large number of Gemini API calls.")
    print("This may consume significant API quota and incur costs.\n")

    try:
        user_input = input('Type "I understand" to continue: ')
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return False

    if user_input.strip() != "I understand":
        print("Confirmation failed. Aborting evaluation.")
        return False

    return True


def reset_clone(path_to_ros2_gbp_github_org: Path, ref: str = "latest") -> None:
    """Reset repository to a given git ref and clean all uncommitted/untracked changes."""
    subprocess.run(
        ["git", "-C", str(path_to_ros2_gbp_github_org), "reset", "--hard", "HEAD"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path_to_ros2_gbp_github_org), "clean", "-fdx", "--", "*.tf"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path_to_ros2_gbp_github_org), "checkout", "-f", ref],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path_to_ros2_gbp_github_org), "reset", "--hard", "HEAD"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path_to_ros2_gbp_github_org), "clean", "-fdx", "--", "*.tf"],
        capture_output=True,
    )


def normalize_diff_lines(diff_text: str) -> list[str]:
    """Strip trailing whitespace and filter out index hashes and blank lines."""
    lines = []
    for raw_line in diff_text.strip().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("index "):
            continue
        lines.append(line)
    return lines


def is_clean_diff(diff_output: str) -> bool:
    """Check if the delta diff against the resolving commit is empty or non-semantic."""
    if not diff_output.strip():
        return True
    lines = normalize_diff_lines(diff_output)
    content_lines = [
        l
        for l in lines
        if (l.startswith("+") or l.startswith("-"))
        and not l.startswith("+++")
        and not l.startswith("---")
    ]
    if not content_lines:
        return True
    # Tolerant to casing differences on added/removed lines
    plus_lines = sorted(
        [l[1:].strip().lower() for l in content_lines if l.startswith("+")]
    )
    minus_lines = sorted(
        [l[1:].strip().lower() for l in content_lines if l.startswith("-")]
    )
    return plus_lines == minus_lines


def run_evals(
    path_to_ros2_gbp_github_org: Path,
    limit: int | None = None,
    category: IssueCategory | str | None = None,
    eval_number: str | None = None,
    model: str = "gemini-3.5-flash-lite",
) -> int:
    """Run evaluations across eval directories."""
    path_to_ros2_gbp_github_org = path_to_ros2_gbp_github_org.resolve()
    eval_folders = sorted([f for f in EVALS_DIR.iterdir() if f.is_dir()])

    if eval_number is not None:
        try:
            eval_num_str = f"{int(eval_number):04d}"
            eval_folders = [
                f
                for f in eval_folders
                if f.name.startswith(eval_num_str) or f.name.startswith(eval_number)
            ]
        except ValueError:
            eval_folders = [f for f in eval_folders if eval_number in f.name]

    if category is not None:
        marker = CATEGORY_TO_MARKER.get(category)
        if marker:
            eval_folders = [f for f in eval_folders if (f / marker).exists()]

    if limit is not None:
        eval_folders = eval_folders[:limit]

    print(f"\nRunning evaluations on {len(eval_folders)} test cases...\n")

    passed = 0
    failed = 0

    try:
        for i, folder in enumerate(eval_folders, start=1):
            print(f"[{i}/{len(eval_folders)}] Evaluating: {folder.name}...")
            issue_file = folder / "issue.json"
            resolved_file = folder / "resolved-by.json"

            if not issue_file.exists() or not resolved_file.exists():
                print(f"  Missing issue.json or resolved-by.json in {folder.name}, skipping.")
                failed += 1
                continue

            with open(resolved_file, encoding="utf-8") as f:
                resolved_data = json.load(f)

            commit = resolved_data.get("commit")

            if not commit:
                print(f"  No commit specified in resolved-by.json for {folder.name}, skipping.")
                failed += 1
                continue

            with open(issue_file, encoding="utf-8") as f:
                issue_data = json.load(f)
            issue_number = issue_data.get("number", "unknown")
            plan_file = Path.cwd() / f"plan_ros2-gbp-github-org_{issue_number}.md"

            try:
                # 1. Reset repository to commit prior to resolution
                reset_clone(path_to_ros2_gbp_github_org, f"{commit}~1")

                # 2. Run plan subcommand
                plan_proc = subprocess.run(
                    [
                        "agent_ros2-gbp-github-org",
                        "plan",
                        "--path-to-ros2-gbp-github-org",
                        str(path_to_ros2_gbp_github_org),
                        "--issue-json",
                        str(issue_file),
                        "--model",
                        model,
                    ],
                    capture_output=True,
                    text=True,
                )
                if plan_proc.returncode != 0:
                    print(f"  Plan step failed (exit code {plan_proc.returncode}): {plan_proc.stderr.strip() or plan_proc.stdout.strip()}")
                    failed += 1
                    continue

                if not plan_file.exists():
                    print(f"  Plan file {plan_file.name} was not created.")
                    failed += 1
                    continue

                # 3. Run implement subcommand
                impl_proc = subprocess.run(
                    [
                        "agent_ros2-gbp-github-org",
                        "implement",
                        "--path-to-ros2-gbp-github-org",
                        str(path_to_ros2_gbp_github_org),
                        "--plan",
                        str(plan_file),
                        "--model",
                        model,
                    ],
                    capture_output=True,
                    text=True,
                )
                if impl_proc.returncode != 0:
                    print(f"  Implement step failed (exit code {impl_proc.returncode}): {impl_proc.stderr.strip() or impl_proc.stdout.strip()}")
                    failed += 1
                    continue

                # 4. Compare working tree directly against resolving commit
                subprocess.run(
                    ["git", "-C", str(path_to_ros2_gbp_github_org), "add", "-A", "--", "*.tf"],
                    check=True,
                    capture_output=True,
                )
                diff_proc = subprocess.run(
                    ["git", "-C", str(path_to_ros2_gbp_github_org), "diff", "-w", commit, "--", "*.tf"],
                    capture_output=True,
                    text=True,
                )
                delta = diff_proc.stdout.strip()

                if is_clean_diff(delta):
                    passed += 1
                    print("  PASSED: Working tree matches resolving commit.")
                else:
                    failed += 1
                    print("  FAILED: Differences against resolving commit:")
                    for line in delta.splitlines()[:10]:
                        print(f"    {line}")

            finally:
                # Always clean up the generated plan file after running the eval
                if plan_file.exists():
                    plan_file.unlink()

    finally:
        # Restore repository to latest branch
        reset_clone(path_to_ros2_gbp_github_org, "latest")

    print("\n" + "=" * 60)
    print(f"Evaluation Complete: {passed} passed, {failed} failed out of {len(eval_folders)}")
    print("=" * 60)
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run agent_ros2-gbp-github-org evaluations across evals/ dataset."
    )
    parser.add_argument(
        "--path-to-ros2-gbp-github-org",
        type=Path,
        required=True,
        help="Path to a git clone of https://github.com/ros2-gbp/ros2-gbp-github-org/",
    )
    parser.add_argument(
        "--eval-number",
        type=str,
        default=None,
        help="Run a specific eval test case by issue/eval number (e.g. 0711 or 711).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of eval test cases to run.",
    )
    parser.add_argument(
        "--category",
        type=IssueCategory,
        choices=list(IssueCategory),
        default=None,
        help="Limit eval test cases to a specific issue category.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-3.5-flash-lite",
        help="Gemini model to use (default: gemini-3.5-flash-lite).",
    )
    args = parser.parse_args()

    if not check_prerequisites(args.path_to_ros2_gbp_github_org):
        sys.exit(1)

    if not prompt_confirmation():
        sys.exit(1)

    sys.exit(
        run_evals(
            path_to_ros2_gbp_github_org=args.path_to_ros2_gbp_github_org,
            limit=args.limit,
            category=args.category,
            eval_number=args.eval_number,
            model=args.model,
        )
    )


if __name__ == "__main__":
    main()
