"""Git subtree operations for module management.

Owns the add/pull/push/split subtree commands with their error handling.
Re-exported from ``quickscale_core.utils.git_utils``.
"""

import subprocess
from pathlib import Path

from quickscale_core.utils.git_errors import GitError
from quickscale_core.utils.git_runner import GitRunner, _run_git


def run_git_subtree_add(
    prefix: str,
    remote: str,
    branch: str,
    squash: bool = True,
    path: Path | None = None,
) -> None:
    """Execute git subtree add with error handling.

    The *branch* parameter accepts either a branch name or a fully-spelled
    40-character hex commit SHA.  Passing a SHA binds the add to the exact
    commit so the fetched content cannot drift if the remote branch advances
    between ref resolution and the subtree operation.  This relies on
    ``git fetch <url> <hex>`` officially supporting fully-spelled hex object
    names and ``git-subtree`` forwarding the ref to ``git fetch``.  Verified
    on Git 2.43.0+.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "add", f"--prefix={prefix}", remote, branch]
    if squash:
        cmd.append("--squash")

    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)  # noqa: S603 - fixed argv list, shell disabled
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to add git subtree: {e.stderr}")


def run_git_subtree_pull(
    prefix: str, remote: str, branch: str, squash: bool = True, path: Path | None = None
) -> str:
    """Execute git subtree pull with error handling and return diff summary.

    The *branch* parameter accepts either a branch name or a fully-spelled
    40-character hex commit SHA.  Passing a SHA binds the pull to the exact
    commit so the fetched content cannot drift if the remote branch advances
    between ref resolution and the subtree operation.

    This SHA-pinned contract is verified by the integration test
    ``TestSubtreePullWithCommitSha`` in ``quickscale_core/tests/test_git_utils.py``
    and relies on ``git fetch <url> <hex>`` officially supporting fully-spelled
    hex object names (git-fetch documentation) and ``git-subtree`` forwarding
    the ref to ``git fetch``.  Verified on Git 2.43.0+.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "pull", f"--prefix={prefix}", remote, branch]
    if squash:
        cmd.append("--squash")

    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
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
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)  # noqa: S603 - fixed argv list, shell disabled
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push git subtree: {e.stderr}")


def run_git_subtree_split(
    prefix: str,
    branch: str,
    *,
    rejoin: bool = True,
    ignore_joins: bool = True,
    path: Path | None = None,
    runner: GitRunner | None = None,
) -> str:
    """Execute ``git subtree split`` and return the resulting commit SHA.

    Creates or updates the local split *branch* from the subtree at *prefix*.
    The *rejoin* and *ignore_joins* flags match the provenance-aware split
    convention used by the maintainer publish workflow (F2.8).

    Returns:
        The 40-character hex commit SHA of the split result.

    Raises:
        GitError: If the subtree split fails.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "subtree", "split", f"--prefix={prefix}", "-b", branch]
    if rejoin:
        cmd.append("--rejoin")
    if ignore_joins:
        cmd.append("--ignore-joins")

    try:
        result = _run_git(
            cmd[1:], cwd=cwd, check=True, capture_output=True, text=True, runner=runner
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to split git subtree: {e.stderr}") from e

    # ``git subtree split -b <branch>`` prints the resulting SHA to stdout.
    split_sha = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if not split_sha or len(split_sha) != 40:
        raise GitError(
            f"Unexpected subtree split output for {prefix}; "
            f"could not extract a 40-char SHA (got {split_sha!r})"
        )
    return split_sha
