import os
import sys
import tempfile

from rosboss.internal.git import clone_repository, git_tag
from rosboss.internal.ui import console, display_and_interactive_copy


def add_subparser(subparser):
    parser = subparser.add_parser(
        "tag-ros2",
        help="Tag ros2/ros2 repository at branch {rosdistro}-release."
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
        help="The date to use for the tag (format: YYYY-MM-DD or YYYYMMDD)."
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
    date_yyyymmdd = args.sync_date.replace("-", "")

    tag_name = f"release-{rosdistro}-{date_yyyymmdd}"

    repo_dir = tempfile.mkdtemp(prefix='ros2_tag_')
    os.chdir(repo_dir)

    try:
        clone_repository("git@github.com:ros2/ros2.git", branch=f"{rosdistro}-release")
        git_tag(tag_name)
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    sections = [
        {"key": "1", "label": "ros2/ros2 Clone Directory", "content": repo_dir, "render_as": "text"},
        {"key": "2", "label": "Push Git Tag Command", "content": f"git push origin {tag_name}", "render_as": "text"},
    ]
    interactive = not getattr(args, "no_interactive", False)
    display_and_interactive_copy(sections, header_info="If this looks good, then run:", header_title="Next Steps", interactive=interactive)
