import importlib.resources
import re
import sys
from string import Template

import requests
import rosdistro

from rosboss.internal.anubis import detect_anubis
from rosboss.internal.ui import display_and_interactive_copy, parse_tmpl_sections

arch_details_template = """[details=Updates to Ubuntu ${suite_title} (${arch})]

### Added Packages [${num_added}]:

${added_packages}

### Updated Packages [${num_updated}]:

${updated_packages}

### Removed Packages [${num_removed}]:

${removed_packages}
[/details]"""


def non_dbgsym_pkgs(content, distro_lower):
    """Return all lines that are non dbgsym packages"""
    for line in content.split('\n'):
        pkg_line = re.match(rf'^ \* \[?(ros-{distro_lower}-[-a-z0-9]*)\]?\(?.*\)?:.+$', line)
        if not pkg_line:
            # print('skipping', repr(line))
            continue
        if pkg_line and pkg_line.group(1).endswith('-dbgsym'):
            # print('skipping', pkg_line.group(1))
            continue
        else:
            yield line


def get_ubuntu_codename(distro_lower):
    index = rosdistro.get_index(rosdistro.get_index_url())
    try:
        cached_dist = rosdistro.get_cached_distribution(index, distro_lower)
    except RuntimeError as e:
        sys.exit(f"Failed to get distribution data: {e}")

    dist_file = cached_dist._distribution_file
    data = dist_file.get_data()
    # Override version to 1 for ReleaseFile constructor compatibility
    data['version'] = 1

    release_file = rosdistro.ReleaseFile(distro_lower, data)

    if 'ubuntu' not in release_file.platforms or not release_file.platforms['ubuntu']:
        sys.exit(f"Could not find Ubuntu release suite for {distro_lower} in rosdistro")
    return release_file.platforms['ubuntu'][0]


def add_subparser(subparser):
    parser = subparser.add_parser(
        "announce-sync",
        help="Make sync announcement"
    )
    parser.add_argument(
        "--rosdistro",
        required=True,
        help="The name of the ROS distribution (e.g., noetic, humble, rolling)."
    )
    parser.add_argument(
        "--sync-date",
        "--date",
        dest="sync_date",
        help="The actual day that the sync happened (format: YYYY-MM-DD). If unspecified, extracted from build logs."
    )
    parser.add_argument(
        "--log-file",
        help="Path to downloaded plain text build log (consoleText). If provided, skips downloading from Jenkins."
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive copy menu."
    )
    parser.set_defaults(func=main)
    return parser


def main(args):
    rosdistro_arg = args.rosdistro
    distro_lower = rosdistro_arg.lower()
    distro_title = rosdistro_arg.capitalize()
    distro_char = distro_lower[0].upper()
    job_name = f"{distro_char}rel_sync-packages-to-main"

    if args.log_file:
        try:
            with open(args.log_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            sys.exit(f"Failed to read log file '{args.log_file}': {e}")
        if detect_anubis(content):
            sys.exit(
                f"Bot protection (Anubis) challenge page detected in log file '{args.log_file}'.\n"
                f"Please download the plain text consoleText logs from the latest {job_name} job in your browser."
            )
    else:
        url = f"https://build.ros2.org/job/{job_name}/lastSuccessfulBuild/consoleText"
        r = requests.get(url)
        if r.status_code != 200:
            sys.exit(f"Failed to fetch page :( status code {r.status_code}")

        content = r.text
        if detect_anubis(content, response=r):
            sys.exit(
                f"Bot protection (Anubis) detected when fetching logs from {url}.\n"
                f"Please download the consoleText logs from the latest {job_name} job in your browser and pass the file using --log-file."
            )

    if args.sync_date:
        sync_date = args.sync_date
    else:
        match = re.search('computed at ([0-9]{4}-[0-9]{2}-[0-9]{2})', content)
        if not match:
            sys.exit("Could not find sync date ('computed at YYYY-MM-DD') in the log content. Specify it manually with --sync-date.")
        sync_date = match.group(1)

    suite = get_ubuntu_codename(distro_lower)

    header_expr = re.compile(
        r"Difference between 'file:///var/repos/ubuntu/main/dists/([a-z]+)/main/binary-([a-z0-9]+)/Packages'"
    )
    matches = list(header_expr.finditer(content))

    blocks = []
    for i, m in enumerate(matches):
        m_suite = m.group(1)
        m_arch = m.group(2)
        if m_suite != suite:
            continue

        start_idx = m.start()
        if i + 1 < len(matches):
            end_idx = matches[i + 1].start()
        else:
            end_idx = len(content)

        block_content = content[start_idx:end_idx]
        blocks.append((m_arch, block_content))

    if not blocks:
        sys.exit(f"No sync architecture blocks found for suite '{suite}' in the logs.")

    all_added_pkgs = set()
    all_updated_pkgs = set()
    all_removed_pkgs = set()
    all_maintainers = set()

    details_sections = []
    suite_title = suite.capitalize()

    for arch, block_content in blocks:
        added_match = re.search(r'### Added Packages \[[0-9]+\]', block_content)
        updated_match = re.search(r'### Updated Packages \[[0-9]+\]', block_content)
        removed_match = re.search(r'### Removed Packages \[[0-9]+\]', block_content)
        maintainers_match = re.search('Thanks to all ROS maintainers', block_content)

        if not (added_match and updated_match and removed_match and maintainers_match):
            continue

        added_packages = []
        for line in non_dbgsym_pkgs(block_content[added_match.end():updated_match.start()], distro_lower):
            added_packages.append(line)
            pkg_line = re.match(rf'^ \* \[?(ros-{distro_lower}-[-a-z0-9]*)\]?\(?.*\)?:.+$', line)
            if pkg_line:
                all_added_pkgs.add(pkg_line.group(1))

        updated_packages = []
        for line in non_dbgsym_pkgs(block_content[updated_match.end():removed_match.start()], distro_lower):
            updated_packages.append(line)
            pkg_line = re.match(rf'^ \* \[?(ros-{distro_lower}-[-a-z0-9]*)\]?\(?.*\)?:.+$', line)
            if pkg_line:
                all_updated_pkgs.add(pkg_line.group(1))

        removed_packages = []
        for line in non_dbgsym_pkgs(block_content[removed_match.end():maintainers_match.start()], distro_lower):
            removed_packages.append(line)
            pkg_line = re.match(rf'^ \* \[?(ros-{distro_lower}-[-a-z0-9]*)\]?\(?.*\)?:.+$', line)
            if pkg_line:
                all_removed_pkgs.add(pkg_line.group(1))

        if not added_packages and not updated_packages and not removed_packages:
            continue

        for line in block_content[maintainers_match.start():].split('\n'):
            if line.startswith(' * '):
                name = line[3:].strip().strip('"')
                if name:
                    all_maintainers.add(name)

        arch_mapping = {
            'suite_title': suite_title,
            'arch': arch,
            'num_added': len(added_packages),
            'added_packages': '\n'.join(added_packages) if added_packages else '',
            'num_updated': len(updated_packages),
            'updated_packages': '\n'.join(updated_packages) if updated_packages else '',
            'num_removed': len(removed_packages),
            'removed_packages': '\n'.join(removed_packages) if removed_packages else '',
        }
        details_sections.append(Template(arch_details_template).substitute(arch_mapping))

    sorted_maintainers = sorted(all_maintainers, key=lambda x: x.lower())
    maintainers_str = '\n'.join([f" * {name}" for name in sorted_maintainers])

    mapping = {
        'distro_lower': distro_lower,
        'distro_title': distro_title,
        'sync_date': sync_date,
        'num_added': len(all_added_pkgs),
        'num_updated': len(all_updated_pkgs),
        'details_sections': '\n\n'.join(details_sections),
        'maintainers': maintainers_str,
    }

    raw_template = importlib.resources.files("rosboss.sync").joinpath("announce_sync.tmpl").read_text()
    parsed_sections = parse_tmpl_sections(raw_template)

    url_text = Template(parsed_sections.get("url", "")).substitute(mapping)
    tags_text = Template(parsed_sections.get("tags", "")).substitute(mapping)
    title_text = Template(parsed_sections.get("title", "")).substitute(mapping)
    body_text = Template(parsed_sections.get("body", "")).substitute(mapping)
    chat_text = Template(parsed_sections.get("chat", "")).substitute(mapping)
    reply_text = Template(parsed_sections.get("reply", "")).substitute(mapping)

    sections = [
        {"key": "1", "label": "Discourse Category URL", "content": url_text, "render_as": "text"},
        {"key": "2", "label": "Discourse Tags", "content": tags_text, "render_as": "text"},
        {"key": "3", "label": "Discourse Title", "content": title_text, "render_as": "text"},
        {"key": "4", "label": "Discourse Body", "content": body_text, "render_as": "markdown"},
        {"key": "5", "label": "Zulip Chat Message", "content": chat_text, "render_as": "text"},
        {"key": "6", "label": "Discourse Sync Hold Reply", "content": reply_text, "render_as": "markdown"},
    ]

    interactive = not getattr(args, "no_interactive", False)
    display_and_interactive_copy(sections, interactive=interactive)



