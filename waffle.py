#!/usr/bin/env python3

import datetime
import os
import sys

from github import Github
from github import Auth

org_list = ['ros2', 'ament']
excluded_labels = ['backlog', 'help wanted', 'more-information-needed']
excluded_repos = ['ros2/safety_working_group', 'ros2/rmw_iceoryx', 'ros2/rosbag2', 'ros2/rclc', 'ros2/cartographer_ros', 'ros2/cartographer', 'ros2/domain_bridge', 'ros2/ros1_bridge']
excluded_projects = ['ros2/52']


def main():
    key = os.environ['GITHUB_API_TOKEN']
    if key is None:
       raise RuntimeError('Failed to get GitHub API key')
    
    today = datetime.date.today()
    start_delta = datetime.timedelta(days=14)
    start_day = today - start_delta
    updatestring = 'updated:>=%s' % start_day
    
    auth = Auth.Token(key)
    gh = Github(auth=auth)

    search_terms = []
    for org in org_list:
        search_terms.append('org:' + org)
    for xlabel in excluded_labels:
        search_terms.append('-label:"' + xlabel + '"')
    for xrepo in excluded_repos:
        search_terms.append('-repo:' + xrepo)
    for xproj in excluded_projects:
        search_terms.append('-project:' + xproj)
    search = ' '.join(search_terms) + ' state:open is:pr no:assignee -draft:true archived:false ' + updatestring
    print("Search:", search)
    issues = gh.search_issues(search)
    for issue in issues:
        if issue.pull_request is not None:
            url = issue.as_pull_request().html_url
        else:
            url = issue.html_url
        print('%s,"%s"' % (url, issue.title))

    return 0


if __name__ == '__main__':
    sys.exit(main())
