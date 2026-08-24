import os
import sys
import tempfile

from rosboss.internal.git import (
    clone_repository,
    get_last_commit_hash,
    git_checkout,
    git_tag,
    print_last_commit_log,
)
from rosboss.internal.ui import console, display_and_interactive_copy


def add_subparser(subparser):
    parser = subparser.add_parser(
        "tag-rosdistro",
        help="Tag rosdistro repository at the last commit that changed a distribution file."
    )
    parser.add_argument(
        "--rosdistro",
        required=True,
        help="The name of the ROS distribution (e.g., lyrical, humble, rolling)."
    )
    parser.add_argument(
        "--sync-date",
        "--date",
        dest="sync_date",
        required=True,
        help="The date to use for the tag (format: YYYY-MM-DD)."
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive copy menu."
    )
    parser.set_defaults(func=main)
    return parser


def main(args):
    rosdistro = args.rosdistro.lower()
    date_str = args.sync_date

    tag_name = f"{rosdistro}/{date_str}"

    repo_dir = tempfile.mkdtemp(prefix='rosdistro_')
    os.chdir(repo_dir)

    try:
        clone_repository("git@github.com:ros/rosdistro.git", branch="master")

        distribution_file = f"{rosdistro}/distribution.yaml"

        # Check if the distribution file exists in the repo
        if not os.path.exists(distribution_file):
            raise RuntimeError(f"Distribution file '{distribution_file}' does not exist in the repository.")

        print_last_commit_log(distribution_file)

        commit_hash = get_last_commit_hash(distribution_file)

        git_checkout(commit_hash)

        git_tag(tag_name)
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    sections = [
        {"key": "1", "label": "ros/rosdistro Clone Directory", "content": repo_dir, "render_as": "text"},
        {"key": "2", "label": "Push Git Tag Command", "content": f"git push origin {tag_name}", "render_as": "text"},
    ]
    interactive = not getattr(args, "no_interactive", False)
    display_and_interactive_copy(sections, header_info="If this looks good, then run:", header_title="Next Steps", interactive=interactive)
