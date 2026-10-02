"""Provenance-aware split publication and release-authoritative gates.

Owns force-with-lease split pushes, the VERSION-file reads, the tags-at-HEAD
probes, and the release-authoritative source gate (F2.8/F2.9a). Re-exported
from ``quickscale_core.utils.git_utils``.
"""

import subprocess
from pathlib import Path

from quickscale_core.utils.git_errors import GitError
from quickscale_core.utils.git_runner import (
    GitRunner,
    _run_git,
    assert_staged_index_empty,
)
from quickscale_core.utils.git_tags import _validate_commit_sha


def validate_expected_sha(expected_remote_sha: str) -> None:
    """Validate an expected-remote-SHA value for force-with-lease safety.

    *expected_remote_sha* must be a non-zero 40-character hex SHA.

    Raises :class:`GitError` with an operator-facing message when the value
    is malformed.
    """
    if not expected_remote_sha:
        raise GitError("expected_remote_sha must not be empty")
    if expected_remote_sha == "ABSENT":
        raise GitError(
            "expected_remote_sha must be a non-zero 40-hex SHA; "
            "literal 'ABSENT' is not supported"
        )
    if len(expected_remote_sha) != 40:
        raise GitError(
            f"expected_remote_sha must be exactly 40 hex characters; "
            f"got {len(expected_remote_sha)}-char value"
        )
    if not all(c in "0123456789abcdefABCDEF" for c in expected_remote_sha):
        raise GitError(
            f"expected_remote_sha contains non-hex characters: {expected_remote_sha!r}"
        )
    if all(c == "0" for c in expected_remote_sha):
        raise GitError("expected_remote_sha must not be all-zero")


def _split_push_refspec(branch: str, source_sha: str | None) -> str:
    """Return the refspec for a split push, binding an explicit source SHA."""
    if source_sha is None:
        return branch

    source_ref = _validate_commit_sha(source_sha, description="split source SHA")
    if all(character == "0" for character in source_ref):
        raise GitError("Split source SHA must not be all-zero")
    return f"{source_ref}:refs/heads/{branch}"


def _publication_index_guard_active(runner: GitRunner | None) -> bool:
    """Return whether the publication staged-index guard applies."""
    return runner is not None and runner.publication


def push_split_branch(
    branch: str,
    remote: str = "origin",
    *,
    expected_remote_sha: str | None = None,
    source_sha: str | None = None,
    path: Path | None = None,
    runner: GitRunner | None = None,
) -> None:
    """Push a split *branch* to *remote* using force-with-lease safety.

    When *expected_remote_sha* is provided, the push uses
    ``--force-with-lease`` instead of bare ``--force``:

    - A 40-character hex SHA produces
      ``--force-with-lease=refs/heads/<branch>:<sha>``, which rejects the
      push if the remote ref has moved away from the expected commit.

    When *source_sha* is provided, the push source is that exact commit object
    rather than the mutable local branch name.  Publication callers use this
    to bind their ancestry proof to the object Git sends.

    When *expected_remote_sha* is ``None``, the push is performed without
    any ``--force`` flag (fast-forward-only).  Callers that require
    force-capable pushes **must** provide ``expected_remote_sha`` (SA117
    Phase 4).  The legacy bare ``--force`` fallback has been removed.

    Raises:
        GitError: If validation fails or the push fails.
    """
    cwd = path or Path.cwd()
    cmd = ["git", "push"]

    if expected_remote_sha is not None:
        validate_expected_sha(expected_remote_sha)
        cmd.append(f"--force-with-lease=refs/heads/{branch}:{expected_remote_sha}")

    cmd.extend([remote, _split_push_refspec(branch, source_sha)])

    try:
        if _publication_index_guard_active(runner):
            assert_staged_index_empty(path=cwd, runner=runner)

        _run_git(
            cmd[1:], cwd=cwd, check=True, capture_output=True, text=True, runner=runner
        )

        if _publication_index_guard_active(runner):
            assert_staged_index_empty(path=cwd, runner=runner)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push split branch {branch}: {e.stderr}") from e


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


def get_all_tags_at_head(
    path: Path | None = None, *, runner: GitRunner | None = None
) -> list[str]:
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
        result = _run_git(
            ["tag", "--points-at", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            runner=runner,
        )
        if result.returncode != 0:
            raise GitError(f"Failed to get tags at HEAD: {result.stderr}")
        tags = result.stdout.strip().splitlines()
        return [t for t in tags if t]
    except FileNotFoundError as e:
        raise GitError(f"git command not found: {e}") from e


def get_tag_at_head(
    path: Path | None = None, *, runner: GitRunner | None = None
) -> str | None:
    """Return the tag name pointing at HEAD, or None if HEAD is untagged.

    Uses ``git tag --points-at HEAD`` to find tags that point directly at
    the current commit.  Works with both lightweight and annotated tags.
    Returns the first tag if multiple tags point at HEAD, or None if no
    tags point at HEAD.

    Raises:
        GitError: If the git command fails.
    """
    tags = get_all_tags_at_head(path, runner=runner)
    return tags[0] if tags else None


def is_release_authoritative(
    repo_root: Path,
    *,
    runner: GitRunner | None = None,
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

    tags_at_head = get_all_tags_at_head(repo_root, runner=runner)

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
