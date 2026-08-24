import importlib.resources
from datetime import datetime, timedelta, timezone
from string import Template

import requests

from rosboss.internal.ui import display_and_interactive_copy, parse_tmpl_sections


def add_subparser(subparser):
    parser = subparser.add_parser(
        "announce-freeze",
        help="Prepare freeze announcement"
    )
    parser.add_argument(
        "--rosdistro",
        required=True,
        help="The name of the ROS distribution (e.g., humble, rolling)."
    )
    parser.add_argument(
        "--sync-date",
        "--date",
        dest="sync_date",
        help="The intended release date (format: YYYY-MM-DD). If unspecified, calculated automatically."
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive copy menu."
    )
    parser.set_defaults(func=main)
    return parser


def main(args):
    rosdistro = args.rosdistro
    distro_lower = rosdistro.lower()
    distro_title = rosdistro.capitalize()

    mapping = {
        'distro_lower': distro_lower,
        'distro_title': distro_title,
        'num_packages': '???',
        'num_regressions': '???',
        'sync_target_date': '???'
    }

    try:
        r = requests.get(f'https://repo.ros2.org/status_page/ros_{distro_lower}_default.html')
        if r.status_code == 200:
            content = r.text
            sync = 0
            regression = 0
            for line in content.split('\n'):
                if line.startswith('<tr><td><div>'):
                    if 'SYNC' in line:
                        sync += 1
                    if 'REGRESSION' in line:
                        regression += 1
            mapping['num_packages'] = sync
            mapping['num_regressions'] = regression
        else:
            print("Failed to fetch page :(", r)
    except requests.RequestException as e:
        print(f"Failed to fetch page due to connection error: {e}")

    if args.sync_date:
        mapping['sync_target_date'] = args.sync_date
    else:
        sync_date = datetime.now(timezone.utc).date() + timedelta(days=2)
        while sync_date.weekday() > 4:
            sync_date += timedelta(days=1)
        mapping['sync_target_date'] = sync_date.strftime("%Y-%m-%d")

    raw_template = importlib.resources.files("rosboss.sync").joinpath("announce_freeze.tmpl").read_text()
    parsed_sections = parse_tmpl_sections(raw_template)

    url_text = Template(parsed_sections.get("url", "")).substitute(mapping)
    tags_text = Template(parsed_sections.get("tags", "")).substitute(mapping)
    title_text = Template(parsed_sections.get("title", "")).substitute(mapping)
    body_text = Template(parsed_sections.get("body", "")).substitute(mapping)
    chat_text = Template(parsed_sections.get("chat", "")).substitute(mapping)

    sections = [
        {"key": "1", "label": "Discourse Category URL", "content": url_text, "render_as": "text"},
        {"key": "2", "label": "Discourse Tags", "content": tags_text, "render_as": "text"},
        {"key": "3", "label": "Discourse Title", "content": title_text, "render_as": "text"},
        {"key": "4", "label": "Discourse Body", "content": body_text, "render_as": "markdown"},
        {"key": "5", "label": "Zulip Chat Message", "content": chat_text, "render_as": "markdown"},
    ]

    interactive = not getattr(args, "no_interactive", False)
    display_and_interactive_copy(sections, interactive=interactive)



