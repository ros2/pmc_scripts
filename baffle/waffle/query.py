#!/usr/bin/env python3
"""Queries the GitHub API for open ROS 2 / ament pull requests and their
authors, and saves the result to a dated YAML file in the site directory.

If a YAML file for today's date already exists, the query is skipped
entirely so repeated runs on the same day don't hammer the GitHub API.
"""

import datetime
import os
import sys

import yaml
from github import Github
from github import Auth

from common import DATE_FILE_FORMAT
from common import ORGS
from common import ROS_MAINTAINER_OVERRIDES
from common import repo_from_url

excluded_labels = ['backlog', 'help wanted', 'more-information-needed']
excluded_repos = ['ros2/safety_working_group', 'ros2/rmw_iceoryx', 'ros2/rosbag2', 'ros2/rclc', 'ros2/cartographer_ros', 'ros2/cartographer', 'ros2/domain_bridge', 'ros2/ros1_bridge']
excluded_projects = ['ros2/52']


def build_search():
    today = datetime.date.today()
    start_delta = datetime.timedelta(days=14)
    start_day = today - start_delta
    updatestring = 'updated:>=%s' % start_day

    search_terms = []
    for org in ORGS:
        search_terms.append('org:' + org)
    for xlabel in excluded_labels:
        search_terms.append('-label:"' + xlabel + '"')
    for xrepo in excluded_repos:
        search_terms.append('-repo:' + xrepo)
    for xproj in excluded_projects:
        search_terms.append('-project:' + xproj)
    search = ' '.join(search_terms) + ' state:open is:pr no:assignee -draft:true archived:false ' + updatestring
    return search


def fetch_pull_requests(gh, search):
    rows = []
    for issue in gh.search_issues(search):
        if issue.pull_request is not None:
            url = issue.as_pull_request().html_url
            kind = 'PR'
        else:
            url = issue.html_url
            kind = 'Issue'
        rows.append({
            'repo': repo_from_url(url),
            'title': issue.title,
            'url': url,
            'kind': kind,
            'author': issue.user.login if issue.user else 'unknown',
            'updated': issue.updated_at.isoformat(),
            'body': issue.body or '',
        })
    rows.sort(key=lambda r: (r['repo'], r['title']))
    return rows


def fetch_org_members(gh, orgs):
    """Return the set of publicly-visible usernames across the given orgs."""
    members = set()
    for org in orgs:
        for member in gh.get_organization(org).get_members():
            members.add(member.login)
    return members


def fetch_user_stats(gh, username, org_members):
    user = gh.get_user(username)
    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.timezone.utc)
    account_age_days = (datetime.datetime.now(datetime.timezone.utc) - created_at).days

    pull_requests = gh.search_issues('is:pr is:public author:%s' % username).totalCount
    issues = gh.search_issues('is:issue is:public author:%s' % username).totalCount
    reviews = gh.search_issues('is:pr is:public reviewed-by:%s' % username).totalCount

    return {
        'account_created_at': created_at.isoformat(),
        'account_age_days': account_age_days,
        'public_pull_requests': pull_requests,
        'public_issues': issues,
        'public_reviews': reviews,
        'is_ros_maintainer': username in org_members or username in ROS_MAINTAINER_OVERRIDES,
    }


def data_file_path(site_dir, today):
    return os.path.join(site_dir, today.strftime(DATE_FILE_FORMAT) + '.yaml')


def main():
    workspace = os.environ.get('BUILD_WORKSPACE_DIRECTORY', os.getcwd())
    site_dir = os.path.join(workspace, 'site')

    if len(sys.argv) > 1:
        out_path = sys.argv[1]
    else:
        out_path = data_file_path(site_dir, datetime.date.today())
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

    if os.path.exists(out_path):
        print('%s already exists, skipping GitHub API query.' % out_path)
        return 0

    key = os.environ.get('GITHUB_API_TOKEN')
    if not key:
        print("Error: GITHUB_API_TOKEN environment variable is not set.", file=sys.stderr)
        print("Please set it in your environment: export GITHUB_API_TOKEN=\"your_token\"", file=sys.stderr)
        return 1

    auth = Auth.Token(key)
    gh = Github(auth=auth)

    search = build_search()
    print("Search:", search)
    pull_requests = fetch_pull_requests(gh, search)
    for row in pull_requests:
        print('%s,"%s"' % (row['url'], row['title']))

    print('Fetching org members for:', ', '.join(ORGS))
    org_members = fetch_org_members(gh, ORGS)

    usernames = sorted({row['author'] for row in pull_requests})
    users = {}
    for username in usernames:
        print('Fetching stats for user:', username)
        users[username] = fetch_user_stats(gh, username, org_members)

    data = {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'search': search,
        'pull_requests': pull_requests,
        'users': users,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, sort_keys=False)
    print('Wrote %s' % out_path)

    return 0


if __name__ == '__main__':
    sys.exit(main())
