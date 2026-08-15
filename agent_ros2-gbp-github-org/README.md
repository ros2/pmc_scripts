# agent_ros2-gbp-github-org

An automated agent tool for planning and implementing Terraform configuration changes in [ros2-gbp/ros2-gbp-github-org](https://github.com/ros2-gbp/ros2-gbp-github-org).

## Prerequisites

- **Git clone** of `ros2-gbp/ros2-gbp-github-org`:
  ```bash
  git clone https://github.com/ros2-gbp/ros2-gbp-github-org.git ~/projects/ros2-gbp/ros2-gbp-github-org
  ```
- **Gemini API Key**:
  ```bash
  export GEMINI_API_KEY="your-api-key"
  ```
- *(Optional)* **GitHub Token** (to prevent rate-limiting when fetching issues):
  ```bash
  export GITHUB_TOKEN="your-github-token"
  ```

## Installation

Install in editable mode:

```bash
pip install -e .
```

## Usage

### 1. `plan`

Analyzes an issue, categorizes it, inspects existing Terraform configuration files, prints a human-auditable plan, and saves it to `plan_ros2-gbp-github-org_<number>.md`.

```bash
# Plan from a GitHub issue URL or issue number
agent_ros2-gbp-github-org plan \
  --path-to-ros2-gbp-github-org ~/projects/ros2-gbp/ros2-gbp-github-org \
  --issue https://github.com/ros2-gbp/ros2-gbp-github-org/issues/1107

# Or plan from a local issue JSON file
agent_ros2-gbp-github-org plan \
  --path-to-ros2-gbp-github-org ~/projects/ros2-gbp/ros2-gbp-github-org \
  --issue-json evals/0702_Add_release_team_synapticon/issue.json
```

Options:
- `--path-to-ros2-gbp-github-org` (required): Path to the clone of `ros2-gbp-github-org`.
- `--issue`: GitHub issue number or full URL.
- `--issue-json`: Path to a JSON file containing the issue payload. (used only for evals)
- `--model`: Gemini model to use (default: `gemini-3.5-flash-lite`).

---

### 2. `implement`

Applies the changes specified in a plan file directly to the `.tf` files in the repository (without committing).

```bash
agent_ros2-gbp-github-org implement \
  --path-to-ros2-gbp-github-org ~/projects/ros2-gbp/ros2-gbp-github-org \
  --plan plan_ros2-gbp-github-org_1107.md
```

Options:
- `--path-to-ros2-gbp-github-org` (required): Path to the clone of `ros2-gbp-github-org`.
- `--plan` (required): Path to the plan markdown file.
- `--model`: Gemini model to use (default: `gemini-3.5-flash-lite`).

---

## Running Evaluations

Run evaluations against historical issues:

```bash
# Run 10 evaluation test cases
./run_evals.py \
  --path-to-ros2-gbp-github-org ~/projects/ros2-gbp/ros2-gbp-github-org \
  --limit 10

# Filter by issue category
./run_evals.py \
  --path-to-ros2-gbp-github-org ~/projects/ros2-gbp/ros2-gbp-github-org \
  --category NewReleaseTeam \
  --limit 5
```
