from rosboss.sync.announce_freeze import add_subparser as add_announce_freeze_subparser
from rosboss.sync.announce_sync import add_subparser as add_announce_sync_subparser
from rosboss.sync.start_packaging_jobs import (
    add_subparser as add_start_packaging_jobs_subparser,
)
from rosboss.sync.tag_ros2 import add_subparser as add_tag_ros2_subparser
from rosboss.sync.tag_rosdistro import add_subparser as add_tag_rosdistro_subparser
from rosboss.sync.update_repos_file import (
    add_subparser as add_update_repos_file_subparser,
)


def add_subparsers(subparsers):
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync operations"
    )
    sync_subparsers = sync_parser.add_subparsers(
        dest="sync_subcommand",
        help="Available sync commands"
    )

    add_announce_freeze_subparser(sync_subparsers)
    add_announce_sync_subparser(sync_subparsers)
    add_start_packaging_jobs_subparser(sync_subparsers)
    add_tag_ros2_subparser(sync_subparsers)
    add_tag_rosdistro_subparser(sync_subparsers)
    add_update_repos_file_subparser(sync_subparsers)

    return sync_parser
