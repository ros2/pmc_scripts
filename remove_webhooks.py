#!/usr/bin/env python3
"""Remove stale webhooks (build.ros2.org, waffle) from a list of GitHub repositories.

Usage:
    remove_webhooks.py --repos-file repos.txt              # dry run: list what would be deleted
    remove_webhooks.py --repos-file repos.txt --apply      # actually delete
    remove_webhooks.py ros2/rclcpp ros2/rclpy --apply      # repos on the command line

The token is read from --token or, if absent, the GITHUB_TOKEN environment variable.

Token permissions required:
    * Classic PAT: the ``admin:repo_hook`` scope (``write:repo_hook`` can read
      and edit hooks but cannot delete them).
    * Fine-grained PAT: repository permission "Webhooks" set to "Read and write",
      granted on every repository listed.
    * In both cases the token's owner must have admin access to each repository,
      since only repo admins may manage webhooks.

Only the Python standard library is used.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = 'https://api.github.com'

# Substrings matched case-insensitively against each webhook's config.url.
DEFAULT_PATTERNS = ('build.ros2.org', 'waffle')


class GitHubError(Exception):
    def __init__(self, status, message, url):
        super().__init__(f'HTTP {status} for {url}: {message}')
        self.status = status


class GitHub:
    def __init__(self, token):
        self._headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'ros2-remove-webhooks',
        }

    def _request(self, method, url):
        req = urllib.request.Request(url, method=method, headers=self._headers)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read()
                data = json.loads(body) if body else None
                return data, resp.headers
        except urllib.error.HTTPError as e:
            try:
                message = json.loads(e.read()).get('message', '')
            except Exception:
                message = e.reason
            raise GitHubError(e.code, message, url) from None

    def list_hooks(self, repo):
        """Yield every webhook on ``repo`` (``owner/name``), following pagination."""
        url = f'{API_ROOT}/repos/{repo}/hooks?per_page=100'
        while url:
            page, headers = self._request('GET', url)
            yield from page
            url = _next_link(headers.get('Link'))

    def delete_hook(self, repo, hook_id):
        self._request('DELETE', f'{API_ROOT}/repos/{repo}/hooks/{hook_id}')


def _next_link(link_header):
    """Extract the rel="next" URL from a GitHub Link header, or None."""
    if not link_header:
        return None
    for part in link_header.split(','):
        pieces = part.split(';')
        if len(pieces) >= 2 and pieces[1].strip() == 'rel="next"':
            return pieces[0].strip().strip('<>')
    return None


def hook_url(hook):
    return (hook.get('config') or {}).get('url') or ''


def matches(hook, patterns):
    url = hook_url(hook).lower()
    return any(p.lower() in url for p in patterns)


def read_repos(args):
    repos = list(args.repos)
    if args.repos_file:
        with open(args.repos_file) as f:
            for line in f:
                line = line.split('#', 1)[0].strip()
                if line:
                    repos.append(line)
    cleaned = []
    for r in repos:
        # Accept full URLs as well as owner/name.
        r = r.strip().rstrip('/')
        if r.startswith('https://github.com/'):
            r = r[len('https://github.com/'):]
        if r.endswith('.git'):
            r = r[:-4]
        if r.count('/') != 1:
            sys.exit(f'error: repository must be in owner/name form: {r!r}')
        if r not in cleaned:
            cleaned.append(r)
    return cleaned


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('repos', nargs='*', help='repositories as owner/name (or GitHub URLs)')
    p.add_argument('--repos-file', help='file with one owner/name per line; # starts a comment')
    p.add_argument('--token', help='GitHub personal access token (default: $GITHUB_TOKEN)')
    p.add_argument('--pattern', action='append', dest='patterns', metavar='SUBSTRING',
                   help='substring of the webhook URL to match; may be repeated '
                        f'(default: {", ".join(DEFAULT_PATTERNS)})')
    p.add_argument('--apply', action='store_true',
                   help='actually delete matching webhooks (default is a dry run)')
    return p.parse_args()


def main():
    args = parse_args()
    token = args.token or os.environ.get('GITHUB_TOKEN')
    if not token:
        sys.exit('error: provide --token or set GITHUB_TOKEN')
    patterns = args.patterns or list(DEFAULT_PATTERNS)
    repos = read_repos(args)
    if not repos:
        sys.exit('error: no repositories given (use positional args or --repos-file)')

    gh = GitHub(token)
    mode = 'DELETE' if args.apply else 'DRY RUN'
    print(f'[{mode}] patterns: {patterns}; repositories: {len(repos)}')

    total_matched = total_deleted = 0
    failed_repos = []
    for repo in repos:
        try:
            hooks = list(gh.list_hooks(repo))
        except GitHubError as e:
            print(f'{repo}: cannot list hooks ({e})')
            failed_repos.append(repo)
            continue

        targets = [h for h in hooks if matches(h, patterns)]
        print(f'{repo}: {len(hooks)} hook(s), {len(targets)} matching')
        for h in targets:
            total_matched += 1
            label = f'  id={h["id"]} url={hook_url(h)}'
            if not args.apply:
                print(f'{label}  (would delete)')
                continue
            try:
                gh.delete_hook(repo, h['id'])
            except GitHubError as e:
                print(f'{label}  FAILED: {e}')
                failed_repos.append(repo)
            else:
                total_deleted += 1
                print(f'{label}  deleted')

    print()
    print(f'matched: {total_matched}, deleted: {total_deleted}, '
          f'repositories with errors: {len(set(failed_repos))}')
    if failed_repos:
        print('errors in: ' + ', '.join(sorted(set(failed_repos))))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

