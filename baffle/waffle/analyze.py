#!/usr/bin/env python3
"""CONTROLLER stage: reads the raw MODEL data file (query.py's output) and
classifies each contributor as Human, Unknown, Bot, or AI, writing the
result to a sibling "<date>_analyzed.yaml" file for the VIEW stage
(render.py) to consume.

Heuristic: community-engagement ratio = (public_issues + public_reviews) /
public_pull_requests. Genuine human contributors -- even prolific ones --
tend to review others' work and open issues at a rate roughly proportional
to how many PRs they open; automated/AI-driven PR farms mass-produce PRs
without that reciprocal engagement. Accounts with too few PRs to trust the
ratio are marked Unknown rather than guessed at. A literal "[bot]" suffix
(GitHub Apps, e.g. mergify[bot]) is always classified as Bot, separately
from the heuristic-driven AI bucket.
"""

import os
import re
import sys

import yaml

from common import ATTESTATION_CROSS
from common import ATTESTATION_TICK
from common import ATTESTATION_WARNING
from common import CLASSIFICATION_AI
from common import CLASSIFICATION_BOT
from common import CLASSIFICATION_HUMAN
from common import CLASSIFICATION_UNKNOWN
from common import find_latest_data_file

MIN_SAMPLE_PULL_REQUESTS = 10
LOW_ENGAGEMENT_THRESHOLD = 0.15
HIGH_ENGAGEMENT_THRESHOLD = 0.5

# Matches the PR template's "### Did you use Generative AI?" heading and the
# "### Additional Information" heading that follows it, regardless of
# markdown decoration (#, *, etc.) around the words.
GENAI_QUESTION_RE = re.compile(r'did\s+you\s+use\s+generative\s+ai\??', re.IGNORECASE)
NEXT_SECTION_RE = re.compile(r'additional\s+information', re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
NON_LETTER_RE = re.compile(r'[^a-zA-Z]')


def engagement_ratio(stats):
    prs = max(stats.get('public_pull_requests', 0), 1)
    return (stats.get('public_issues', 0) + stats.get('public_reviews', 0)) / prs


def classify_user(username, stats):
    if username.endswith('[bot]'):
        return CLASSIFICATION_BOT
    if stats.get('public_pull_requests', 0) < MIN_SAMPLE_PULL_REQUESTS:
        return CLASSIFICATION_UNKNOWN
    ratio = engagement_ratio(stats)
    if ratio >= HIGH_ENGAGEMENT_THRESHOLD:
        return CLASSIFICATION_HUMAN
    # A ratio of exactly zero is as consistent with "human who has simply
    # never opened an issue or left a review" as with a PR farm, so it
    # isn't strong enough evidence on its own to call AI.
    if 0 < ratio < LOW_ENGAGEMENT_THRESHOLD:
        return CLASSIFICATION_AI
    return CLASSIFICATION_UNKNOWN


def classify_ai_attestation(body):
    """Classify a PR body's answer to the template's "Did you use Generative
    AI?" question. Missing question or blank/comment-only answer -> warning;
    an answer of exactly "No" -> cross; any other answer -> tick."""
    if not body:
        return ATTESTATION_WARNING
    question_match = GENAI_QUESTION_RE.search(body)
    if not question_match:
        return ATTESTATION_WARNING

    section_match = NEXT_SECTION_RE.search(body, question_match.end())
    section_end = section_match.start() if section_match else len(body)
    answer = HTML_COMMENT_RE.sub('', body[question_match.end():section_end]).strip()

    # Discard pure markdown noise (leftover heading markers, list bullets,
    # etc.) -- e.g. a bare "###" before the next section heading, once HTML
    # comments are stripped out, doesn't count as a real answer.
    if not NON_LETTER_RE.sub('', answer):
        return ATTESTATION_WARNING

    first_line = next((line.strip() for line in answer.splitlines() if line.strip()), '')
    if NON_LETTER_RE.sub('', first_line).lower() == 'no':
        return ATTESTATION_CROSS
    return ATTESTATION_TICK


def analyzed_file_path(data_path):
    stem, ext = os.path.splitext(os.path.basename(data_path))
    return os.path.join(os.path.dirname(data_path), '%s_analyzed%s' % (stem, ext))


def main():
    workspace = os.environ.get('BUILD_WORKSPACE_DIRECTORY', os.getcwd())
    site_dir = os.path.join(workspace, 'site')

    data_path = sys.argv[1] if len(sys.argv) > 1 else find_latest_data_file(site_dir)
    if not data_path:
        print("Error: no dated YAML file found in %s. Run the query tool first." % site_dir, file=sys.stderr)
        return 1

    with open(data_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    users = data.get('users', {})
    for username, stats in users.items():
        stats['classification'] = classify_user(username, stats)

    for row in data.get('pull_requests', []):
        row['ai_attestation'] = classify_ai_attestation(row.get('body', ''))
        row.pop('body', None)

    out_path = analyzed_file_path(data_path)
    with open(out_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, sort_keys=False)
    print('Wrote %s' % out_path)

    return 0


if __name__ == '__main__':
    sys.exit(main())
