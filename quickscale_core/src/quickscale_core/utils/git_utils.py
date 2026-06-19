"""Git utilities for module management via git subtree operations."""

import re
import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a git operation fails."""

    pass


# Strict module-name allowlist: alphanumeric, hyphens, underscores; must start
# with an alphanumeric character.  This prevents path-traversal (``..``, ``/``),
# flag-injection (``-leading``), and shell-meta characters from reaching
# ``git subtree --prefix=`` or branch-name arguments.
_MODULE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def validate_module_name(module_name: str) -> None:
    """Reject *module_name* unless it is a safe bare slug.

    Raises :class:`GitError` with an operator-facing message when the name is
    empty, contains path separators, starts with ``-``, or includes any
    character outside ``[a-zA-Z0-9_-]``.
    """
    if not module_name:
        raise GitError("Module name must not be empty")
    if not _MODULE_NAME_RE.match(module_name):
        raise GitError(
            f"Invalid module name {module_name!r}; "
            "expected a bare slug matching [a-zA-Z0-9][a-zA-Z0-9_-]*"
        )


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
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
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
        result = subprocess.run(
            ["git", "ls-remote", "--heads", remote, branch],
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


# ---------------------------------------------------------------------------
# F2.8 — Provenance-aware split-publish helper surface
# ---------------------------------------------------------------------------


def resolve_module_path(module_name: str) -> str:
    """Return the canonical maintainer-side module path for *module_name*.

    Centralizes the ``quickscale_modules/<name>`` convention so split-publish
    callers do not hardcode the path template.  Raises :class:`GitError` when
    *module_name* is not a valid bare module slug (empty, path separators,
    ``..`` traversal, flag-injection prefixes, or shell-meta characters).
    """
    validate_module_name(module_name)
    return f"quickscale_modules/{module_name}"


def resolve_split_branch(module_name: str) -> str:
    """Return the canonical split branch name for *module_name*.

    Centralizes the ``splits/<name>-module`` convention so split-publish
    callers do not hardcode the branch template.  Raises :class:`GitError`
    when *module_name* is not a valid bare module slug (empty, path
    separators, ``..`` traversal, flag-injection prefixes, or shell-meta
    characters).
    """
    validate_module_name(module_name)
    return f"splits/{module_name}-module"


def run_git_subtree_split(
    prefix: str,
    branch: str,
    *,
    rejoin: bool = True,
    ignore_joins: bool = True,
    path: Path | None = None,
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
        result = subprocess.run(
            cmd, cwd=cwd, check=True, capture_output=True, text=True
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


def push_split_branch(
    branch: str,
    remote: str = "origin",
    *,
    force: bool = True,
    path: Path | None = None,
) -> None:
    """Push a split *branch* to *remote*.

    Split branches are force-pushed by default because they are rewritten
    history derived from subtree splits.  Set *force* to ``False`` for a
    non-destructive push.

    Raises:
        GitError: If the push fails.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "push"]
    if force:
        cmd.append("--force")
    cmd.extend([remote, branch])

    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push split branch {branch}: {e.stderr}") from e


# ---------------------------------------------------------------------------
# F2.9a — Release-authoritative source gate
# ---------------------------------------------------------------------------


def read_version_file(repo_root: Path) -> str:
    """Read and return the trimmed version string from the VERSION file.

    Raises:
        GitError: If the VERSION file does not exist or cannot be read.
    """
    version_file = repo_root / "VERSION"
    if not version_file.is_file():
        raise GitError(f"VERSION file not found at {version_file}")
    try:
        content = version_file.read_text(encoding="utf-8")
        # Match the publish workflow's trimming: strip CR, leading/trailing whitespace
        version = content.replace("\r", "").strip()
        if not version:
            raise GitError("VERSION file is empty")
        return version
    except OSError as e:
        raise GitError(f"Failed to read VERSION file: {e}") from e


def get_all_tags_at_head(path: Path | None = None) -> list[str]:
    """Return all tag names pointing at HEAD (may be empty if untagged).

    Uses ``git tag --points-at HEAD`` to find tags that point directly at
    the current commit.  Works with both lightweight and annotated tags.
    Returns all tags if multiple tags point at HEAD, or an empty list if no
    tags point at HEAD.

    Raises:
        GitError: If the git command fails.
    """
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "tag", "--points-at", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise GitError(f"Failed to get tags at HEAD: {result.stderr}")
        tags = result.stdout.strip().splitlines()
        return [t for t in tags if t]
    except FileNotFoundError as e:
        raise GitError(f"git command not found: {e}") from e


def get_tag_at_head(path: Path | None = None) -> str | None:
    """Return the tag name pointing at HEAD, or None if HEAD is untagged.

    Uses ``git tag --points-at HEAD`` to find tags that point directly at
    the current commit.  Works with both lightweight and annotated tags.
    Returns the first tag if multiple tags point at HEAD, or None if no
    tags point at HEAD.

    Raises:
        GitError: If the git command fails.
    """
    tags = get_all_tags_at_head(path)
    return tags[0] if tags else None


def is_release_authoritative(
    repo_root: Path,
) -> tuple[bool, str, str | None, str | None]:
    """Check if the source state is release-authoritative (F2.9a).

    Release-authoritative means the VERSION file content matches at least one
    git tag pointing at HEAD using one of the two workflow-authoritative tag
    forms (see .github/workflows/publish.yml):

    * exact VERSION match (e.g. ``0.86.0``), or
    * single lowercase ``v`` prefix + VERSION (e.g. ``v0.86.0``).

    Uppercase ``V``, multiple ``v`` prefixes, and other tag shapes are **not**
    accepted — they do not trigger the publish workflow and must not be treated
    as release-authoritative here either.  When multiple tags point at HEAD,
    the gate succeeds if *any* of them matches VERSION in one of these two
    forms — this prevents a stale or unrelated tag from shadowing a valid
    release tag.

    Returns:
        A tuple ``(is_authoritative, version_from_file, tag_at_head, mismatch_reason)``:
        - ``is_authoritative``: True if VERSION matches at least one tag at HEAD
        - ``version_from_file``: The version string from the VERSION file
        - ``tag_at_head``: The matching tag name, or the first tag if none match,
          or None if untagged
        - ``mismatch_reason``: Human-readable reason if not authoritative, or None

    This function does not raise on expected conditions (missing VERSION, untagged
    HEAD, version mismatch).  It returns structured diagnostics so callers can
    decide how to report or handle the situation.
    """
    try:
        version_from_file = read_version_file(repo_root)
    except GitError as e:
        return False, "", None, str(e)

    tags_at_head = get_all_tags_at_head(repo_root)

    if not tags_at_head:
        return (
            False,
            version_from_file,
            None,
            f"HEAD is not tagged; VERSION file contains {version_from_file}",
        )

    # Check each tag against the two workflow-authoritative forms only:
    # exact VERSION (e.g. "0.86.0") or single lowercase v + VERSION
    # (e.g. "v0.86.0").  Uppercase V, multiple v prefixes, and other shapes
    # do not trigger the publish workflow and must not match here either.
    # The gate succeeds if ANY tag matches VERSION in one of these forms.
    def _is_authoritative_tag(tag: str) -> bool:
        return tag == version_from_file or tag == f"v{version_from_file}"

    for tag in tags_at_head:
        if _is_authoritative_tag(tag):
            return True, version_from_file, tag, None

    # No tag matched.  Report the first tag in the mismatch reason for
    # operator clarity, but note if multiple tags were present.
    first_tag = tags_at_head[0]
    # Compute the stripped form for diagnostic parity with prior messages.
    first_version = first_tag.lstrip("vV")
    if len(tags_at_head) > 1:
        return (
            False,
            version_from_file,
            first_tag,
            f"VERSION file ({version_from_file}) does not match any of the "
            f"{len(tags_at_head)} tags at HEAD "
            f"(e.g. {first_tag} -> {first_version})",
        )
    return (
        False,
        version_from_file,
        first_tag,
        f"VERSION file ({version_from_file}) does not match tag at HEAD "
        f"({first_tag} -> {first_version})",
    )
