import argparse
import sys

from rosboss.sync.cli import add_subparsers as add_sync_subparsers


def create_parser():
    parser = argparse.ArgumentParser(
        prog="rosboss",
        description="CLI tool for ROS bossing."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    add_sync_subparsers(subparsers)

    return parser


def main(args=None):
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    if hasattr(parsed_args, "func"):
        parsed_args.func(parsed_args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
