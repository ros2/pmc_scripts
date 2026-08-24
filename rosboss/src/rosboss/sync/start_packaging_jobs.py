import os
import sys
import time
from dataclasses import dataclass
from functools import cache

import requests
from rosdistro import get_distribution_file, get_index, get_index_url

from rosboss.internal.supported_distros import (
    PackagingJob,
    get_distro_info,
)
from rosboss.internal.ui import console, display_and_interactive_copy


@cache
def fetch_distribution(distro_name: str):
    index_url = get_index_url()
    index = get_index(index_url)
    return get_distribution_file(index, distro_name)


@dataclass
class PackagingJobParameters:
    ci_ros2_repos_url: str
    ci_pixi_toml_url: str
    ci_ubuntu_distro: str
    ci_el_release: str
    ci_ros_distro: str
    jenkins_user: str
    packaging_jobs: list[PackagingJob]
    jenkins_token: str | None = None


def get_jenkins_auth(username: str) -> tuple[str, str | None]:
    """Retrieve Jenkins username and API token using keyring."""
    try:
        import keyring
        token = keyring.get_password("ci.ros2.org", username)
    except Exception:  # noqa: BLE001
        token = None
    return username, token


def generate_packaging_markdown(job_builds: dict[str, int | str], packaging_jobs: list[PackagingJob]) -> str:
    """Generate Markdown snippet for packaging build status links."""
    lines = ["Packaging:", ""]
    for pjob in packaging_jobs:
        build_num = job_builds.get(pjob.job_name, "???")
        icon_url = f"http://ci.ros2.org/buildStatus/icon?job={pjob.job_name}&build={build_num}"
        job_url = f"https://ci.ros2.org/job/{pjob.job_name}/{build_num}/"
        lines.append(f"* {pjob.label} [![Build Status]({icon_url})]({job_url})")
    return "\n".join(lines)


def gather_info(rosdistro: str, ros2_commit: str, jenkins_user: str) -> PackagingJobParameters:
    distro_name = rosdistro.lower()
    try:
        dist = fetch_distribution(distro_name)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch distribution file for '{distro_name}': {e}") from e

    release_platforms = getattr(dist, "release_platforms", {})
    ubuntu_distros = release_platforms.get("ubuntu")
    if not ubuntu_distros:
        raise RuntimeError(f"No ubuntu release platform found for distribution '{distro_name}'")
    ci_ubuntu_distro = str(ubuntu_distros[0])

    rhel_releases = release_platforms.get("rhel")
    if not rhel_releases:
        raise RuntimeError(f"No RHEL release platform found for distribution '{distro_name}'")
    ci_el_release = str(rhel_releases[0])

    ci_ros2_repos_url = f"https://raw.githubusercontent.com/ros2/ros2/{ros2_commit}/ros2.repos"
    ci_pixi_toml_url = f"https://raw.githubusercontent.com/ros2/ros2/{ros2_commit}/pixi.toml"

    username, token = get_jenkins_auth(jenkins_user)
    distro_info = get_distro_info(distro_name)

    return PackagingJobParameters(
        ci_ros2_repos_url=ci_ros2_repos_url,
        ci_pixi_toml_url=ci_pixi_toml_url,
        ci_ubuntu_distro=ci_ubuntu_distro,
        ci_el_release=ci_el_release,
        ci_ros_distro=distro_name,
        jenkins_user=username,
        packaging_jobs=distro_info.packaging_jobs,
        jenkins_token=token,
    )


def start_packaging_jobs(params: PackagingJobParameters) -> dict[str, int]:
    """Start packaging jobs on ci.ros2.org via Jenkins API and return job build numbers."""
    if not params.jenkins_token:
        raise RuntimeError(f"No Jenkins API token found in keyring for user '{params.jenkins_user}'.")

    auth = (params.jenkins_user, params.jenkins_token)
    session = requests.Session()
    session.auth = auth

    payload = {
        "CI_ROS2_REPOS_URL": params.ci_ros2_repos_url,
        "CI_PIXI_TOML_URL": params.ci_pixi_toml_url,
        "CI_UBUNTU_DISTRO": params.ci_ubuntu_distro,
        "CI_EL_RELEASE": params.ci_el_release,
        "CI_ROS_DISTRO": params.ci_ros_distro,
    }

    queue_items = {}

    for pjob in params.packaging_jobs:
        url = f"https://ci.ros2.org/job/{pjob.job_name}/buildWithParameters"

        console.print(f"[bold cyan]Triggering Jenkins job for {pjob.label} ({pjob.job_name})...[/bold cyan]")
        response = session.post(url, data=payload, timeout=15)
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to trigger Jenkins job '{pjob.job_name}' at {url} (HTTP {response.status_code}): {response.text[:200]}"
            )

        queue_url = response.headers.get("Location")
        if not queue_url:
            raise RuntimeError(f"Jenkins job '{pjob.job_name}' response did not include a Location header.")

        if not queue_url.endswith("/"):
            queue_url += "/"

        queue_items[pjob.job_name] = queue_url

    console.print("[bold cyan]Waiting for Jenkins build numbers...[/bold cyan]")
    job_builds = {}
    max_wait_seconds = 60
    poll_interval = 2

    for job_name, queue_url in queue_items.items():
        api_url = f"{queue_url}api/json"
        start_time = time.time()
        build_num = None

        while time.time() - start_time < max_wait_seconds:
            r = session.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("cancelled"):
                    raise RuntimeError(f"Jenkins queue item for '{job_name}' was cancelled.")
                executable = data.get("executable")
                if executable and "number" in executable:
                    build_num = executable["number"]
                    break
            time.sleep(poll_interval)

        if build_num is None:
            raise RuntimeError(f"Timed out waiting for build number from Jenkins queue item for '{job_name}'.")

        job_builds[job_name] = build_num

    return job_builds


def add_subparser(subparser):
    parser = subparser.add_parser(
        "start-packaging-jobs",
        help="Start packaging jobs on ci.ros2.org."
    )
    parser.add_argument(
        "--rosdistro",
        required=True,
        help="The name of the ROS distribution (e.g., lyrical, humble, rolling)."
    )
    parser.add_argument(
        "--ros2-commit",
        required=True,
        help="The git commit or release tag of ros2/ros2 (e.g., release-lyrical-20260807)."
    )
    parser.add_argument(
        "--jenkins-user",
        default=os.environ.get("USER", ""),
        help="Jenkins username. Defaults to $USER environment variable."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gather and print job parameters without triggering Jenkins jobs."
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive copy menu."
    )
    parser.set_defaults(func=main)
    return parser


def main(args):
    try:
        params = gather_info(args.rosdistro, args.ros2_commit, args.jenkins_user)
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    interactive = not getattr(args, "no_interactive", False)

    if args.dry_run:
        console.print("[bold green]Gathered Packaging Job Parameters (Dry Run):[/bold green]")
        console.print(f"  [bold]CI_ROS2_REPOS_URL:[/bold] {params.ci_ros2_repos_url}")
        console.print(f"  [bold]CI_PIXI_TOML_URL:[/bold]  {params.ci_pixi_toml_url}")
        console.print(f"  [bold]CI_UBUNTU_DISTRO:[/bold]  {params.ci_ubuntu_distro}")
        console.print(f"  [bold]CI_EL_RELEASE:[/bold]     {params.ci_el_release}")
        console.print(f"  [bold]CI_ROS_DISTRO:[/bold]     {params.ci_ros_distro}")
        console.print(f"  [bold]Packaging Jobs:[/bold]    {', '.join(j.job_name for j in params.packaging_jobs)}")
        console.print(f"  [bold]Jenkins User:[/bold]      {params.jenkins_user}")
        console.print(f"  [bold]Jenkins Token:[/bold]     {'***' if params.jenkins_token else '(none)'}\n")
        return

    try:
        job_builds = start_packaging_jobs(params)
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    markdown_content = generate_packaging_markdown(job_builds, params.packaging_jobs)
    sections = [
        {
            "key": "1",
            "label": "Packaging Build Status Markdown",
            "content": markdown_content,
            "render_as": "text",
        }
    ]
    display_and_interactive_copy(
        sections,
        header_info="Post this packaging build status to GitHub:",
        header_title="Packaging Jobs Triggered",
        interactive=interactive,
    )
