"""Git utilities for module management via git subtree operations."""

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git operation fails."""

    pass


def is_git_repo(path: Path | None = None) -> bool:
    """Check if current directory or specified path is a git repository"""
    cwd = path or Path.cwd()
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_working_directory_clean(path: Path | None = None) -> bool:
    """Check if there are uncommitted changes in the git working directory"""
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to check git status: {e.stderr}")


def check_remote_branch_exists(
    remote: str, branch: str, path: Path | None = None
) -> bool:
    """Check if branch exists on remote repository"""
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", remote, branch],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to check remote branch: {e.stderr}")


def run_git_subtree_add(
    prefix: str, remote: str, branch: str, squash: bool = True, path: Path | None = None
) -> None:
    """Execute git subtree add with error handling"""
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "add", f"--prefix={prefix}", remote, branch]
    if squash:
        cmd.append("--squash")

    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to add git subtree: {e.stderr}")


def run_git_subtree_pull(
    prefix: str, remote: str, branch: str, squash: bool = True, path: Path | None = None
) -> str:
    """Execute git subtree pull with error handling and return diff summary"""
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "pull", f"--prefix={prefix}", remote, branch]
    if squash:
        cmd.append("--squash")

    try:
        result = subprocess.run(
            cmd, cwd=cwd, check=True, capture_output=True, text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to pull git subtree: {e.stderr}")


def run_git_subtree_push(
    prefix: str, remote: str, branch: str, path: Path | None = None
) -> None:
    """Execute git subtree push with error handling"""
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "push", f"--prefix={prefix}", remote, branch]

    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push git subtree: {e.stderr}")


def get_remote_url(remote_name: str = "origin", path: Path | None = None) -> str:
    """Get the URL of a git remote"""
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote_name],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get remote URL: {e.stderr}")
