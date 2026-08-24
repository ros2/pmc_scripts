import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache

import requests
import yaml
from rosdistro import get_distribution_file, get_index, get_index_url

from rosboss.internal.git import clone_repository
from rosboss.internal.ui import display_and_interactive_copy, pretty_command


@cache
def fetch_distribution(distro_name):
    index_url = get_index_url()
    index = get_index(index_url)
    return get_distribution_file(index, distro_name)


def get_track(url):
    response = requests.get(url)
    response.raise_for_status()
    return yaml.safe_load(response.text)


def release_tag_from_track(rosdistro, release_url):
    # Convert git URL to HTTP url for tracks.yaml
    release_url = release_url.removesuffix('.git')
    if 'github.com' in release_url:
        release_url = release_url.replace('github.com', 'raw.githubusercontent.com')
    url = f"{release_url}/refs/heads/master/tracks.yaml"

    try:
        data = get_track(url)
    except Exception as e:  # noqa: BLE001
        print(f"# WARNING: Failed to download tracks.yaml from {url}: {e}")
        return None

    tracks = data.get('tracks', {})
    track = tracks.get(rosdistro)
    if not track:
        print(f"# WARNING: Track '{rosdistro}' not found in tracks.yaml")
        return None

    release_tag_template = track.get('release_tag')
    last_version = track.get('last_version')

    if not release_tag_template or not last_version:
        return None

    tag = release_tag_template.replace(':{version}', last_version)
    return tag


def latest_release_tag_by_source_url(distro_name, target_git_url):
    """
    Finds the current release tag of a ROS package based on its source repository URL.
    """
    dist = fetch_distribution(distro_name)

    for repo_data in dist.repositories.values():
        source_repo = repo_data.source_repository

        if source_repo and source_repo.url == target_git_url:
            release_repo = repo_data.release_repository
            if release_repo:
                return release_tag_from_track(distro_name, release_repo.url)
            else:
                return None

    return None


@dataclass
class Repository:
    name: str
    url: str
    version: str


def yaml_to_repository_list(data):
    repos = []
    repositories = data.get('repositories', {})
    for name, info in repositories.items():
        url = info.get('url')
        version = info.get('version')
        repos.append(Repository(name=name, url=url, version=version))
    return repos


def repos_from_file(input_repos):
    if input_repos is not None:
        with open(input_repos) as f:
            data = yaml.safe_load(f)
        return yaml_to_repository_list(data)
    return []


def repository_list_to_yaml(repos):
    repo_dict = {}
    for repo in repos:
        repo_dict[repo.name] = {
            'type': 'git',
            'url': repo.url,
            'version': repo.version
        }
    return {'repositories': repo_dict}


def parse_pins(pin_args):
    pins = {}
    if pin_args:
        for pin in pin_args:
            if '=' not in pin:
                print(f"Error: Invalid pin format '{pin}'. Expected 'repo_name=version'", file=sys.stderr)
                sys.exit(1)
            name, version = pin.split('=', 1)
            pins[name] = version
    return pins


def clone_ros2_repo(rosdistro):
    """Clone the ros2/ros2 repository into current directory on {rosdistro}-release branch."""
    clone_repository("git@github.com:ros2/ros2.git", branch=f"{rosdistro}-release")


def add_subparser(subparser):
    parser = subparser.add_parser(
        "update-repos-file",
        help="Update ros2.repos in ros2/ros2 with current release versions."
    )
    parser.add_argument(
        "--rosdistro",
        required=True,
        help="The name of the ROS distribution (e.g., lyrical, humble, rolling)."
    )
    parser.add_argument(
        "--input-repos",
        help="Path to a file containing target git URLs."
    )
    parser.add_argument(
        "--pin",
        action="append",
        help="Pin a repository to a specific version. Format: repo_name=version"
    )
    parser.add_argument(
        "--sync-date",
        "--date",
        dest="sync_date",
        help="The date to use for the branch name (format: YYYY-MM-DD). If unspecified, current date is used."
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

    if args.sync_date:
        date_str = args.sync_date
        date_yyyymmdd = args.sync_date.replace("-", "")
    else:
        now = datetime.now(timezone.utc)
        date_str = now.strftime('%Y-%m-%d')
        date_yyyymmdd = now.strftime('%Y%m%d')

    new_branch_name = f"update_{rosdistro}-release_{date_yyyymmdd}"

    repo_dir = tempfile.mkdtemp(prefix='ros2_release_')
    os.chdir(repo_dir)

    try:
        clone_ros2_repo(rosdistro)

        pretty_command(['git', 'checkout', '-b', new_branch_name])

        target_repos_path = args.input_repos if args.input_repos else "ros2.repos"
        if not os.path.exists(target_repos_path):
            raise RuntimeError(f"Input repos file '{target_repos_path}' not found in repository.")

        repos = repos_from_file(target_repos_path)
        pins = parse_pins(args.pin)

        repo_names = {repo.name for repo in repos}
        for pinned_name in pins:
            if pinned_name not in repo_names:
                print(f"Error: Pinned repository '{pinned_name}' not found in input repos.", file=sys.stderr)
                sys.exit(1)

        output_repos = []
        for repo in repos:
            if repo.name in pins:
                latest_version = pins[repo.name]
            else:
                latest_version = latest_release_tag_by_source_url(rosdistro, repo.url)

            if not latest_version:
                print(f"# WARNING: Did not find a release for: {repo.name} in {rosdistro}")
                continue
            repo.version = latest_version
            output_repos.append(repo)

        yaml_data = repository_list_to_yaml(output_repos)
        yaml_string = yaml.dump(yaml_data, sort_keys=False)

        todays_date_and_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        header_comments = [
            f"# ROS {rosdistro.capitalize()} repos file",
            f"# Generated on {todays_date_and_time}"
        ]
        for pin_name, pin_version in pins.items():
            header_comments.append(f"# --pin {pin_name}={pin_version}")

        full_content = "\n".join(header_comments) + "\n" + yaml_string.rstrip() + "\n"

        with open("ros2.repos", "w") as f:
            f.write(full_content)

        pretty_command(['git', 'diff', 'ros2.repos'])

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    commit_push_cmd = f'git commit -am "Update {rosdistro} ros2.repos for {date_str} sync" && git push -u origin {new_branch_name}'

    sections = [
        {"key": "1", "label": "ros2/ros2 Clone Directory", "content": repo_dir, "render_as": "text"},
        {"key": "2", "label": "Commit and Push Branch Command", "content": commit_push_cmd, "render_as": "text"},
    ]

    interactive = not getattr(args, "no_interactive", False)
    display_and_interactive_copy(sections, header_info="If this looks good, then run:", header_title="Next Steps", interactive=interactive)
