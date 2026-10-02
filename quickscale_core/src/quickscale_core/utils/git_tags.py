"""Tag-name validation and tag/SHA resolution over Git.

Owns strict Git ref validation, remote and local tag resolution, commit-SHA
validation, and tree-SHA reads. Re-exported from
``quickscale_core.utils.git_utils``.
"""

import re
import subprocess
from pathlib import Path

from quickscale_core.utils.git_errors import GitError


def _tag_has_malformed_ref_syntax(tag: str) -> bool:
    """Return whether *tag* contains a malformed ref sequence or suffix."""
    return (
        tag == "@"
        or "@{" in tag
        or ".." in tag
        or tag.endswith(".")
        or tag.endswith(".lock")
    )


def _tag_has_malformed_path(tag: str) -> bool:
    """Return whether *tag* contains an invalid slash-separated path."""
    return (
        tag.startswith("/")
        or tag.endswith("/")
        or "//" in tag
        or any(part.startswith(".") or part.endswith(".") for part in tag.split("/"))
    )


def _tag_has_malformed_structure(tag: str) -> bool:
    """Return whether *tag* violates Git's structural ref-name rules."""
    return _tag_has_malformed_ref_syntax(tag) or _tag_has_malformed_path(tag)


def _tag_has_invalid_characters(tag: str) -> bool:
    """Return whether *tag* contains whitespace, controls, or ref specials."""
    return any(
        character.isspace()
        or ord(character) < 0x20
        or ord(character) == 0x7F
        or character in "~^:?*[\\"
        for character in tag
    )


def validate_tag_name(tag: str) -> None:
    """Reject tag values that are not one literal, valid Git ref name.

    Tag values are interpolated into explicit ``refs/tags`` arguments and
    refspecs.  Keep this validation local and deterministic so malformed,
    wildcard, or option-like values cannot reach a Git subprocess.
    """
    if not isinstance(tag, str) or not tag:
        raise GitError("Tag name must not be empty")
    if tag.startswith("-"):
        raise GitError(f"Invalid tag name {tag!r}; option-like values are not allowed")
    if tag.startswith("refs/"):
        raise GitError(f"Invalid tag name {tag!r}; expected a tag name, not a full ref")
    if _tag_has_malformed_structure(tag):
        raise GitError(f"Invalid tag name {tag!r}; malformed Git ref")
    if _tag_has_invalid_characters(tag):
        raise GitError(
            f"Invalid tag name {tag!r}; wildcard, control, or ref-special "
            "characters are not allowed"
        )


_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _validate_commit_sha(sha: str, *, description: str) -> str:
    """Validate and return a full, non-ambiguous Git object SHA."""
    if not _SHA_RE.fullmatch(sha):
        raise GitError(f"Unexpected {description}: {sha!r}; expected a 40-hex SHA")
    return sha


def _parse_remote_tag_record(
    line: str,
    tag: str,
    expected_direct_ref: str,
    expected_peeled_ref: str,
) -> tuple[str, str]:
    """Parse one expected ``ls-remote`` tag record."""
    if not line.strip():
        raise GitError(f"Malformed ls-remote tag output for {tag!r}: blank record")
    fields = line.split("\t")
    if len(fields) != 2:
        raise GitError(f"Malformed ls-remote tag output for {tag!r}: {line!r}")

    sha, ref = fields
    if ref == expected_peeled_ref:
        return "peeled", sha
    if ref == expected_direct_ref:
        return "direct", sha
    raise GitError(f"Malformed ls-remote tag output for {tag!r}: unknown ref {ref!r}")


def _parse_remote_tag_output(output: str, tag: str) -> str | None:
    """Parse ``ls-remote`` output and return the tag's commit SHA."""
    expected_direct_ref = f"refs/tags/{tag}"
    expected_peeled_ref = f"{expected_direct_ref}^{{}}"
    direct_sha: str | None = None
    peeled_sha: str | None = None
    if not output:
        return None

    for line in output.splitlines():
        record_kind, sha = _parse_remote_tag_record(
            line, tag, expected_direct_ref, expected_peeled_ref
        )
        if record_kind == "peeled":
            if peeled_sha is not None:
                raise GitError(
                    f"Malformed ls-remote tag output for {tag!r}: "
                    "duplicate peeled record"
                )
            peeled_sha = _validate_commit_sha(sha, description=f"peeled tag {tag}")
        elif direct_sha is not None:
            raise GitError(
                f"Malformed ls-remote tag output for {tag!r}: duplicate direct record"
            )
        else:
            direct_sha = _validate_commit_sha(sha, description=f"tag {tag}")

    if direct_sha is None:
        raise GitError(
            f"Malformed ls-remote tag output for {tag!r}: peeled record without direct record"
        )
    return peeled_sha or direct_sha


def _resolve_remote_tag_commit(
    remote: str, tag: str, path: Path | None = None
) -> str | None:
    """Resolve a remote tag, returning ``None`` when the tag is absent."""
    validate_tag_name(tag)
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            [  # noqa: S607 - PATH-resolved executable by design
                "git",
                "ls-remote",
                "--tags",
                "--",
                remote,
                f"refs/tags/{tag}",
                f"refs/tags/{tag}^{{}}",
            ],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to resolve remote tag '{tag}': {e.stderr}") from e

    return _parse_remote_tag_output(result.stdout, tag)


def resolve_remote_tag(remote: str, tag: str, path: Path | None = None) -> str:
    """Resolve *tag* on *remote* to its peeled 40-hex commit SHA.

    Annotated tags are returned via their ``^{{}}`` peeled entry.  Lightweight
    tags use the direct entry.  A missing tag is an error rather than a
    fallback to another ref.
    """
    commit_sha = _resolve_remote_tag_commit(remote, tag, path)
    if commit_sha is None:
        raise GitError(f"Remote tag '{tag}' not found on {remote}")
    return commit_sha


def check_remote_tag_exists(remote: str, tag: str, path: Path | None = None) -> bool:
    """Return whether *tag* exists on *remote* without resolving another ref."""
    return _resolve_remote_tag_commit(remote, tag, path) is not None


def get_tree_sha(commit: str, path: Path | None = None) -> str:
    """Return the tree SHA for *commit* using Git's verified tree peel."""
    cwd = path or Path.cwd()
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "rev-parse", "--verify", f"{commit}^{{tree}}"],  # noqa: S607 - PATH-resolved executable by design
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to resolve tree for {commit}: {e.stderr}") from e
    return _validate_commit_sha(result.stdout.strip(), description="tree")


def get_local_tag_commit(tag: str, path: Path | None = None) -> str | None:
    """Return the commit resolved by a local tag, or ``None`` if absent."""
    validate_tag_name(tag)
    cwd = path or Path.cwd()
    tag_ref = f"refs/tags/{tag}"
    try:
        presence = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "show-ref", "--verify", "--quiet", tag_ref],  # noqa: S607 - PATH-resolved executable by design
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        raise GitError(f"Failed to inspect local tag '{tag}': {e}") from e
    if presence.returncode == 1:
        return None
    if presence.returncode != 0:
        raise GitError(
            f"Failed to inspect local tag '{tag}': "
            f"{presence.stderr or 'git returned a non-zero status'}"
        )

    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "rev-parse", "--verify", f"{tag_ref}^{{commit}}"],  # noqa: S607 - PATH-resolved executable by design
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        raise GitError(f"Failed to resolve local tag '{tag}': {e}") from e
    if result.returncode != 0:
        raise GitError(
            f"Failed to resolve local tag '{tag}': "
            f"{result.stderr or 'git returned a non-zero status'}"
        )
    return _validate_commit_sha(result.stdout.strip(), description=f"tag {tag}")


def create_annotated_tag(tag: str, commit: str, path: Path | None = None) -> None:
    """Create an annotated local tag, accepting only an identical existing tag.

    The absence of a force option is intentional: a local tag can be reused
    only when it already resolves to the requested commit.  A conflicting tag
    fails closed and reports both commit SHAs.
    """
    validate_tag_name(tag)
    requested_sha = _validate_commit_sha(commit, description="requested commit")
    existing_sha = get_local_tag_commit(tag, path)
    if existing_sha is not None:
        if existing_sha == requested_sha:
            return
        raise GitError(
            f"Local tag '{tag}' resolves to {existing_sha}, requested {requested_sha}"
        )

    cwd = path or Path.cwd()
    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "tag", "--annotate", tag, requested_sha, "--message", tag],  # noqa: S607 - PATH-resolved executable by design
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to create annotated tag '{tag}': {e.stderr}") from e


def push_tag(tag: str, remote: str = "origin", path: Path | None = None) -> None:
    """Push exactly one tag ref without force flags or tag sweeping."""
    validate_tag_name(tag)
    cwd = path or Path.cwd()
    refspec = f"refs/tags/{tag}:refs/tags/{tag}"
    try:
        subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "push", "--", remote, refspec],  # noqa: S607 - PATH-resolved executable by design
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to push tag '{tag}': {e.stderr}") from e
