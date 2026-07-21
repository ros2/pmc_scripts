# Baffle (baffle_maker)

Baffle is a PR triage and classification toolchain designed to automatically identify, analyze, and group open, unassigned, and unlabeled pull requests from the `ros2` and `ament` organizations. By classifying contributors and extracting Generative AI disclosures, it helps maintainers prioritize human-authored PRs and efficiently manage incoming contributions.

## History

Baffle evolved from `waffle_maker.py`, a script originally used by the Waffle team to triage PRs for review. The Waffle team meets every Thursday at 9:30 AM PST to run and review triaged PRs.

## How it Works

The pipeline is split into three main stages:

1. **Query** (`waffle/query.py`):
   Queries the GitHub API for open, unassigned, non-draft, and non-archived pull requests across the configured GitHub organizations. It also fetches public statistics for the PR authors (such as account age, public PR count, public issue count, and review count). The results are saved as a raw YAML file in the `site/` directory (e.g., `site/YYYY-MM-DD.yaml`).

2. **Analyze** (`waffle/analyze.py`):
   Reads the raw data, analyzes the contributors, and writes a `<date>_analyzed.yaml` file.
   - **Contributor Classification**: Classifies contributors into `Human`, `Unknown`, `Bot`, or `AI` categories. It calculates an *engagement ratio* (`(public_issues + public_reviews) / public_pull_requests`) to identify potential AI-driven PR farms (accounts with low engagement relative to their PR count) versus active community members.
   - **AI Attestation**: Examines the PR description to check if the author answered the template's "Did you use Generative AI?" question.

3. **Render** (`waffle/render.py`):
   Renders the analyzed YAML data into a clean, Bazel-themed static HTML dashboard: **The Baffle Board** (`site/index.html`). PRs are grouped into separate tables based on author classification (Human, Unknown, Bot, AI) to ensure maintainers focus first on genuine human contributions.

## Setup & Running

This project uses Bazel and `rules_python` with `uv` for dependency management.

### Prerequisites

Set your GitHub token in your environment:
```bash
export GITHUB_API_TOKEN="your_personal_access_token"
```

### Steps

1. **Query the GitHub API**:
   ```bash
   bazel run //waffle:query
   ```

2. **Analyze the fetched data**:
   ```bash
   bazel run //waffle:analyze
   ```

3. **Render the dashboard**:
   ```bash
   bazel run //waffle:render
   ```

After running the render tool, open `site/index.html` in your browser to view the Baffle Board.
