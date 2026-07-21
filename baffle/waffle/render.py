#!/usr/bin/env python3
"""VIEW stage: renders the most recent "<date>_analyzed.yaml" file (the
CONTROLLER stage's output) into a static HTML waffle board (site/index.html),
grouped into Human / Unknown / Bot / AI tables in that order so
human-authored PRs are prioritized."""

import datetime
import html
import os
import sys

import yaml

from common import ATTESTATION_ICON
from common import ATTESTATION_LABEL
from common import ATTESTATION_WARNING
from common import CLASSIFICATION_AI
from common import CLASSIFICATION_BOT
from common import CLASSIFICATION_HUMAN
from common import CLASSIFICATION_ORDER
from common import CLASSIFICATION_UNKNOWN
from common import WAFFLE_BASE
from common import WAFFLE_DARK
from common import WAFFLE_DEEP
from common import WAFFLE_LIGHT
from common import WAFFLE_MID
from common import WAFFLE_MIST
from common import WAFFLE_PALE
from common import find_latest_analyzed_file
from common import waffle_favicon_data_uri
from common import waffle_icon

GROUP_ICON = {
    CLASSIFICATION_HUMAN: '&#129489;',   # person
    CLASSIFICATION_UNKNOWN: '&#10067;',  # question mark
    CLASSIFICATION_BOT: '&#129302;',     # robot
    CLASSIFICATION_AI: '&#129504;',      # brain
}


def parse_iso(value):
    return datetime.datetime.fromisoformat(value)


def format_age(days):
    years, remainder_days = divmod(days, 365)
    if years >= 1:
        return '%d yr%s' % (years, '' if years == 1 else 's')
    return '%d day%s' % (remainder_days, '' if remainder_days == 1 else 's')


def render_row(row, users, icon_sm):
    author = row['author']
    user = users.get(author, {})
    author_url = 'https://github.com/' + author
    is_maintainer = user.get('is_ros_maintainer', False)
    maintainer_badge = ' <span class="maintainer-badge" title="ROS maintainer">&#9733;</span>' if is_maintainer else ''
    tooltip_parts = []
    if user.get('account_age_days') is not None:
        tooltip_parts.append('Account age: %s' % format_age(user['account_age_days']))
    if user.get('public_pull_requests') is not None:
        tooltip_parts.append('Public PRs: %d' % user['public_pull_requests'])
    if user.get('public_issues') is not None:
        tooltip_parts.append('Public issues: %d' % user['public_issues'])
    if user.get('public_reviews') is not None:
        tooltip_parts.append('Public reviews: %d' % user['public_reviews'])
    tooltip = html.escape(' · '.join(tooltip_parts))
    attestation = row.get('ai_attestation', ATTESTATION_WARNING)
    attestation_icon = ATTESTATION_ICON[attestation]
    attestation_label = html.escape(ATTESTATION_LABEL[attestation])
    return f'''      <tr>
        <td class="col-icon">{icon_sm}</td>
        <td class="col-repo"><span class="pill">{html.escape(row['repo'])}</span></td>
        <td class="col-title"><a href="{html.escape(row['url'])}" target="_blank" rel="noopener">{html.escape(row['title'])}</a></td>
        <td class="col-author" title="{tooltip}"><a href="{html.escape(author_url)}" target="_blank" rel="noopener">@{html.escape(author)}</a>{maintainer_badge}</td>
        <td class="col-ai" title="{attestation_label}">{attestation_icon}</td>
        <td class="col-updated">{parse_iso(row['updated']).strftime('%b %d, %Y')}</td>
      </tr>'''


def render_group(classification, rows, users, icon_sm):
    if not rows:
        return ''
    body_rows = [render_row(row, users, icon_sm) for row in rows]
    return f'''    <section class="group">
      <h2 class="group-heading">{GROUP_ICON[classification]} {html.escape(classification)} <span class="count-badge">{len(rows)}</span></h2>
      <table>
        <thead>
          <tr>
            <th class="col-icon"></th>
            <th class="col-repo">Repository</th>
            <th class="col-title">Title</th>
            <th class="col-author">Author</th>
            <th class="col-ai">AI</th>
            <th class="col-updated">Last updated</th>
          </tr>
        </thead>
        <tbody>
{chr(10).join(body_rows)}
        </tbody>
      </table>
    </section>'''


def render_html(data, generated_at):
    rows = data.get('pull_requests', [])
    users = data.get('users', {})
    icon_lg = waffle_icon(size=64, cell_id='hero')
    icon_sm = waffle_icon(size=28, cell_id='row')
    favicon = waffle_favicon_data_uri()

    grouped = {classification: [] for classification in CLASSIFICATION_ORDER}
    for row in rows:
        classification = users.get(row['author'], {}).get('classification', CLASSIFICATION_UNKNOWN)
        grouped.setdefault(classification, []).append(row)

    if rows:
        sections_html = '\n'.join(
            render_group(classification, grouped.get(classification, []), users, icon_sm)
            for classification in CLASSIFICATION_ORDER
        )
        badge_text = ' · '.join(
            '%d %s' % (len(grouped.get(classification, [])), classification)
            for classification in CLASSIFICATION_ORDER
        )
    else:
        sections_html = f'''    <div class="empty-plate">
      {icon_lg}
      <p>No waffles today &mdash; the plate is clean!</p>
    </div>'''
        badge_text = '0 open on the plate'

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Baffle Board</title>
<link rel="icon" href="{favicon}">
<style>
  :root {{
    --waffle-dark: {WAFFLE_DARK};
    --waffle-deep: {WAFFLE_DEEP};
    --waffle-base: {WAFFLE_BASE};
    --waffle-mid: {WAFFLE_MID};
    --waffle-light: {WAFFLE_LIGHT};
    --waffle-pale: {WAFFLE_PALE};
    --waffle-mist: {WAFFLE_MIST};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background:
      radial-gradient(circle at 8px 8px, var(--waffle-pale) 2px, transparent 2px) 0 0 / 32px 32px,
      var(--waffle-mist);
    color: var(--waffle-dark);
    min-height: 100vh;
  }}
  .hero {{
    background: linear-gradient(135deg, var(--waffle-deep), var(--waffle-base) 55%, var(--waffle-mid));
    color: var(--waffle-mist);
    padding: 2.5rem 1.5rem 3rem;
    text-align: center;
    box-shadow: 0 6px 18px rgba(18, 50, 31, 0.35);
  }}
  .hero-icons {{
    display: flex;
    justify-content: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }}
  .hero-icons .waffle-icon {{ filter: drop-shadow(0 3px 4px rgba(0,0,0,0.25)); }}
  .hero h1 {{
    margin: 0 0 0.35rem;
    font-size: 2.25rem;
    letter-spacing: 0.02em;
  }}
  .hero p {{
    margin: 0.25rem 0;
    opacity: 0.9;
  }}
  .badge {{
    display: inline-block;
    margin-top: 0.75rem;
    padding: 0.35rem 0.9rem;
    background: rgba(232, 245, 233, 0.15);
    border: 1px solid rgba(232, 245, 233, 0.4);
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.9rem;
  }}
  main {{
    max-width: 1000px;
    margin: -1.75rem auto 3rem;
    padding: 0 1.5rem;
  }}
  .group {{
    background: white;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(18, 50, 31, 0.18);
    overflow: hidden;
    border: 1px solid var(--waffle-pale);
    margin-bottom: 1.5rem;
  }}
  .group-heading {{
    margin: 0;
    padding: 1rem 1.25rem;
    background: var(--waffle-deep);
    color: var(--waffle-mist);
    font-size: 1.1rem;
  }}
  .count-badge {{
    display: inline-block;
    background: rgba(232, 245, 233, 0.2);
    border-radius: 999px;
    padding: 0.1rem 0.6rem;
    font-size: 0.85rem;
    margin-left: 0.4rem;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
  }}
  thead th {{
    text-align: left;
    background: var(--waffle-mist);
    color: var(--waffle-deep);
    padding: 0.85rem 1rem;
    border-bottom: 2px solid var(--waffle-light);
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.06em;
  }}
  tbody tr {{
    border-bottom: 1px solid var(--waffle-mist);
    transition: background 0.15s ease;
  }}
  tbody tr:nth-child(even) {{ background: var(--waffle-mist); }}
  tbody tr:hover {{ background: var(--waffle-pale); }}
  td {{ padding: 0.65rem 1rem; vertical-align: middle; }}
  .col-icon {{ width: 44px; }}
  .pill {{
    display: inline-block;
    background: var(--waffle-pale);
    color: var(--waffle-deep);
    border-radius: 999px;
    padding: 0.2rem 0.7rem;
    font-size: 0.8rem;
    font-weight: 600;
    white-space: nowrap;
  }}
  .col-title a {{
    color: var(--waffle-base);
    text-decoration: none;
    font-weight: 600;
  }}
  .col-title a:hover {{ text-decoration: underline; }}
  .col-author a {{
    color: var(--waffle-deep);
    text-decoration: none;
    white-space: nowrap;
  }}
  .col-author a:hover {{ text-decoration: underline; }}
  .maintainer-badge {{ color: #f9a825; cursor: default; }}
  .col-ai {{ text-align: center; font-size: 1.1rem; cursor: default; }}
  .col-updated {{ color: #5a6b5f; white-space: nowrap; }}
  .empty-plate {{
    text-align: center;
    padding: 3rem 1rem;
    color: var(--waffle-base);
  }}
  .empty-plate .waffle-icon {{ margin-bottom: 1rem; }}
  footer {{
    max-width: 1000px;
    margin: 0 auto 2rem;
    padding: 0 1.5rem;
    text-align: center;
    color: var(--waffle-base);
    font-size: 0.85rem;
  }}
  footer .waffle-icon {{ width: 20px; height: 20px; vertical-align: middle; margin: 0 2px; opacity: 0.7; }}
  code {{ background: var(--waffle-mist); padding: 0.1rem 0.4rem; border-radius: 4px; }}
  @media (max-width: 640px) {{
    table {{ font-size: 0.85rem; }}
    .col-updated, .col-author {{ display: none; }}
  }}
</style>
</head>
<body>
  <div class="hero">
    <div class="hero-icons">{icon_lg}{icon_lg}{icon_lg}</div>
    <h1>The Baffle Board</h1>
    <p>Unassigned, unlabeled ROS&nbsp;2 &amp; ament pull requests waiting for a reviewer.</p>
    <span class="badge">{badge_text}</span>
  </div>
  <main>
{sections_html}
  </main>
  <footer>
    {icon_sm}{icon_sm}{icon_sm}
    <p>Generated {generated_at.strftime('%b %d, %Y %H:%M UTC')} by <code>baffle_maker</code>.</p>
  </footer>
</body>
</html>
'''


def write_site(html_content, site_dir):
    out_path = os.path.join(site_dir, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print('Wrote %s' % out_path)


def main():
    workspace = os.environ.get('BUILD_WORKSPACE_DIRECTORY', os.getcwd())
    site_dir = os.path.join(workspace, 'site')
    os.makedirs(site_dir, exist_ok=True)

    data_path = sys.argv[1] if len(sys.argv) > 1 else find_latest_analyzed_file(site_dir)
    if not data_path:
        print("Error: no analyzed YAML file found in %s. Run the query and analyze tools first." % site_dir, file=sys.stderr)
        return 1

    with open(data_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    html_content = render_html(data, datetime.datetime.now(datetime.timezone.utc))
    write_site(html_content, site_dir)

    return 0


if __name__ == '__main__':
    sys.exit(main())
