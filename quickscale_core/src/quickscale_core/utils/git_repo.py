"""Repository-state and origin checks over Git.

Owns the read-only repository probes (``is_git_repo``, working-directory
cleanliness, remote branch existence, remote URL reads, remote ref
resolution) and the trusted publication-origin validation. Re-exported from
``quickscale_core.utils.git_utils``.
"""

import subprocess
from pathlib import Path
from typing import cast

from quickscale_core.utils.git_errors import GitError
from quickscale_core.utils.git_runner import (
    GitRunner,
    _parse_nul_records,
    _run_git,
)


def is_git_repo(path: Path | None = None, *, runner: GitRunner | None = None) -> bool:
    """Check if current directory or specified path is a git repository"""
    cwd = path or Path.cwd()
    try:
        _run_git(
            ["rev-parse", "--git-dir"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            runner=runner,
        )
        return True
    except subprocess.CalledProcessError, FileNotFoundError:
        return False


def is_working_directory_clean(
    path: Path | None = None, *, runner: GitRunner | None = None
) -> bool:
    """Check if there are uncommitted changes in the git working directory"""
    cwd = path or Path.cwd()
    try:
        result = _run_git(
            [
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
                "-z",
            ],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=False,
            runner=runner,
        )
        return not _parse_nul_records(
            result.stdout, description="git status porcelain output"
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to check git status: {e.stderr}")


def check_remote_branch_exists(
    remote: str, branch: str, path: Path | None = None
) -> bool:
    """Check if branch exists on remote repository"""
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "ls-remote", "--heads", remote, branch],  # noqa: S607 - PATH-resolved executable by design
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to check remote branch: {e.stderr}")


def resolve_remote_ref(remote: str, branch: str, path: Path | None = None) -> str:
    """Resolve a remote branch to its current commit SHA.

    Uses ``git ls-remote`` to look up the tip of *branch* on *remote* and
    returns the full 40-character hex SHA.  This lets callers bind the
    exact source ref once and reuse it for both the subtree operation and
    state persistence.

    Args:
        remote: Git remote URL.
        branch: Branch name on the remote (e.g. ``splits/auth-module``).
        path: Optional working directory for the git command.

    Returns:
        The 40-character hex commit SHA string.

    Raises:
        GitError: If the remote cannot be contacted or the branch does not
            exist on the remote.
    """
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "ls-remote", "--heads", remote, branch],  # noqa: S607 - PATH-resolved executable by design
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to resolve remote ref: {e.stderr}") from e

    output = result.stdout.strip()
    if not output:
        raise GitError(
            f"Remote branch '{branch}' not found on {remote}; cannot resolve source ref"
        )

    # ls-remote output format: "<sha>\trefs/heads/<branch>"
    sha = output.split()[0]
    if len(sha) != 40:
        raise GitError(f"Unexpected ref format from ls-remote for {branch}: {sha!r}")
    return sha


def get_remote_url(
    remote_name: str = "origin",
    path: Path | None = None,
    *,
    runner: GitRunner | None = None,
) -> str:
    """Get the URL of a git remote"""
    cwd = path or Path.cwd()
    try:
        result = _run_git(
            ["remote", "get-url", remote_name],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            runner=runner,
        )
        return cast(str, result.stdout).strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get remote URL: {e.stderr}")


_TRUSTED_PUBLICATION_ORIGIN_URLS = frozenset(
    {
        "https://github.com/Experto-AI/quickscale",
        "https://github.com/Experto-AI/quickscale.git",
        "git@github.com:Experto-AI/quickscale",
        "git@github.com:Experto-AI/quickscale.git",
        "ssh://git@github.com/Experto-AI/quickscale",
        "ssh://git@github.com/Experto-AI/quickscale.git",
    }
)


def _publication_origin_identity(url: str) -> str | None:
    """Return the reviewed repository identity for an exact URL spelling."""
    if url in _TRUSTED_PUBLICATION_ORIGIN_URLS:
        return "github.com/Experto-AI/quickscale"
    return None


def _effective_remote_url_args(remote_name: str, *, push: bool) -> list[str]:
    """Build the Git arguments for reading effective remote URLs."""
    args = ["remote", "get-url"]
    if push:
        args.append("--push")
    args.extend(["--all", remote_name])
    return args


def _effective_remote_url_kind(*, push: bool) -> str:
    """Return the operator-facing URL kind for a fetch or push lookup."""
    return "push" if push else "fetch"


def _raise_effective_remote_url_error(
    error: subprocess.CalledProcessError,
    *,
    push: bool,
) -> None:
    """Translate a failed effective-URL lookup into a stable Git error."""
    kind = _effective_remote_url_kind(push=push)
    stderr = error.stderr or ""
    if "No such remote" in stderr or "does not appear" in stderr:
        raise GitError(f"Origin {kind} URL is blank or unset") from error
    raise GitError(
        f"Failed to read origin {kind} URL: {stderr or 'remote is unavailable'}"
    ) from error


def _validate_effective_remote_urls(urls: list[str], *, push: bool) -> list[str]:
    """Reject missing, blank, or whitespace-padded effective remote URLs."""
    kind = _effective_remote_url_kind(push=push)
    if not urls or any(not url for url in urls):
        raise GitError(f"Origin {kind} URL is blank or unset")
    for url in urls:
        stripped_url = url.strip()
        if not stripped_url:
            raise GitError(f"Origin {kind} URL is blank or unset")
        if url != stripped_url:
            raise GitError(
                f"Origin {kind} URL contains surrounding whitespace and is untrusted"
            )
    return urls


def _get_effective_remote_urls(
    remote_name: str,
    *,
    push: bool,
    path: Path,
    runner: GitRunner | None,
) -> list[str]:
    """Read all effective fetch or push URLs for one remote."""
    try:
        result = _run_git(
            _effective_remote_url_args(remote_name, push=push),
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
            runner=runner,
        )
    except subprocess.CalledProcessError as e:
        _raise_effective_remote_url_error(e, push=push)

    urls = result.stdout.splitlines()
    return _validate_effective_remote_urls(urls, push=push)


def validate_publication_origin(
    path: Path,
    *,
    remote_name: str = "origin",
    runner: GitRunner | None = None,
) -> tuple[str, str]:
    """Require exact trusted fetch and push identities for publication.

    Only the named remote is checked, so unrelated remotes remain allowed.
    Every effective URL configured for that remote must be one of the explicit
    HTTPS/SSH forms for ``github.com/Experto-AI/quickscale`` and fetch/push
    identities must agree.  A missing push URL is handled by Git's effective
    URL resolution, which reports the fetch URL as the push URL.
    """
    fetch_urls = _get_effective_remote_urls(
        remote_name, push=False, path=path, runner=runner
    )
    push_urls = _get_effective_remote_urls(
        remote_name, push=True, path=path, runner=runner
    )

    fetch_identities = {_publication_origin_identity(url) for url in fetch_urls}
    push_identities = {_publication_origin_identity(url) for url in push_urls}
    if None in fetch_identities:
        raise GitError(
            "Publication origin fetch URL is not the trusted "
            "github.com/Experto-AI/quickscale repository"
        )
    if None in push_identities:
        raise GitError(
            "Publication origin push URL is not the trusted "
            "github.com/Experto-AI/quickscale repository"
        )

    # Compare repository identity, not transport spelling: HTTPS and SSH are
    # both authorized, but fetch and push must target the same exact project.
    if fetch_identities != push_identities:
        raise GitError("Publication origin fetch and push identities differ")
    return fetch_urls[0], push_urls[0]
