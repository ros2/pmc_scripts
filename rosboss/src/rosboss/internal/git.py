import subprocess

from rosboss.internal.ui import pretty_command


def clone_repository(repo_url: str, branch: str = "master", target_dir: str = "."):
    """Clone a git repository from GitHub into the specified directory."""
    try:
        pretty_command(['git', 'clone', '-b', branch, repo_url, target_dir])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to clone repository '{repo_url}' on branch '{branch}': {e}") from e


def git_tag(tag_name: str):
    """Create a git tag with the specified tag name."""
    try:
        pretty_command(['git', 'tag', tag_name])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create tag '{tag_name}': {e}") from e


def git_checkout(commit_hash: str):
    """Check out the repository to the specified commit hash."""
    try:
        pretty_command(['git', 'checkout', commit_hash])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to check out commit '{commit_hash}': {e}") from e


def print_last_commit_log(file_path: str):
    """Print the last commit log for the specified file path."""
    try:
        pretty_command(['git', 'log', '-n', '1', '--', file_path])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to show git log for {file_path}: {e}") from e


def get_last_commit_hash(file_path: str) -> str:
    """Retrieve the hash of the last commit modifying the specified file."""
    try:
        result = subprocess.run(
            ['git', 'log', '-n', '1', '--format=format:%H', '--', file_path],
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()
        if not commit_hash:
            raise ValueError(f"Could not retrieve commit hash for {file_path}")
        return commit_hash
    except (subprocess.CalledProcessError, ValueError) as e:
        raise RuntimeError(f"Failed to retrieve commit hash for '{file_path}': {e}") from e
