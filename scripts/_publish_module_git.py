"""
Git seam for the ``publish_module`` facade and its private siblings.

The trusted publication runner bindings come from
``quickscale_core.utils.git_utils``; the SHA/ref parsing wrappers, the
publication tags/branch helpers, and the working-tree checks live here.  The
private siblings resolve each git collaborator through this module at call
time, so a test's seam is the module that defines the name
(decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import _publish_module_core as _core

from quickscale_core.utils.git_utils import (
    GitError as GitError,
)
from quickscale_core.utils.git_utils import (
    GitRunner as GitRunner,
)
from quickscale_core.utils.git_utils import (
    build_publication_git_runner as build_publication_git_runner,
)
from quickscale_core.utils.git_utils import (
    is_git_repo as is_git_repo,
)
from quickscale_core.utils.git_utils import (
    is_release_authoritative as is_release_authoritative,
)
from quickscale_core.utils.git_utils import (
    is_working_directory_clean as is_working_directory_clean,
)
from quickscale_core.utils.git_utils import (
    push_split_branch as push_split_branch,
)
from quickscale_core.utils.git_utils import (
    resolve_module_path as resolve_module_path,
)
from quickscale_core.utils.git_utils import (
    resolve_split_branch as resolve_split_branch,
)
from quickscale_core.utils.git_utils import (
    resolve_split_tag as resolve_split_tag,
)
from quickscale_core.utils.git_utils import (
    run_git_subtree_split as run_git_subtree_split,
)
from quickscale_core.utils.git_utils import (
    validate_expected_sha as validate_expected_sha,
)
from quickscale_core.utils.git_utils import (
    validate_module_name as validate_module_name,
)
from quickscale_core.utils.git_utils import (
    validate_publication_local_config as validate_publication_local_config,
)
from quickscale_core.utils.git_utils import (
    validate_publication_origin as validate_publication_origin,
)
from quickscale_core.utils.git_utils import (
    validate_tag_name as validate_tag_name,
)

# ---------------------------------------------------------------------------
# Working-tree checks
# ---------------------------------------------------------------------------


def _has_uncommitted_changes(runner: GitRunner) -> bool:
    """Return True if the working directory has uncommitted changes."""
    try:
        # Publication uses git_utils' binary, NUL-safe status parser.  Any
        # malformed non-empty stream is treated as dirty/fail-closed rather
        # than being silently normalized by text or newline parsing.
        return not is_working_directory_clean(_core._REPO_ROOT, runner=runner)
    except GitError:
        return True


def _warn_uncommitted_changes(runner: GitRunner) -> None:
    if _has_uncommitted_changes(runner):
        _core._print_warning(
            "You have uncommitted changes. "
            "Split status and published branches only include committed history."
        )


def _confirm_uncommitted_changes(runner: GitRunner) -> bool:
    """
    Prompt the user when uncommitted changes are present.

    Returns True if the user wants to continue, False to abort.
    """
    if not _has_uncommitted_changes(runner):
        return True
    _core._print_warning(
        "You have uncommitted changes. Published split branches only include committed history."
    )
    print()
    reply = input("Continue anyway? (y/N): ")
    if reply.strip().lower() not in ("y", "yes"):
        _core._print_info("Aborted by user")
        return False
    return True


def _maybe_clean_subtree_cache(clean: bool) -> None:
    if clean:
        _core._print_info("Cleaning git subtree cache...")
        cache_dir = _core._REPO_ROOT / ".git" / "subtree-cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


def _get_local_split_sha(
    module_path: str,
    runner: GitRunner,
    *,
    repo_root: Path | None = None,
) -> str | None:
    """Compute the subtree split SHA for *module_path* without creating a branch."""
    result = runner.run(
        ["subtree", "split", f"--prefix={module_path}", "--ignore-joins"],
        cwd=repo_root or _core._REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return sha if sha else None


def _observe_remote_branch_sha(module_name: str, runner: GitRunner) -> str | None:
    """
    Freshly observe the remote split-branch SHA for *module_name*, read-only.

    This live ``ls-remote`` result is the publication-status authority.  Local
    and remote-tracking refs can be stale, and feeding one to
    ``EXPECTED_REMOTE_SHA`` could satisfy the wrong lease.

    The empty string means the remote was observed and the branch is absent;
    ``None`` means origin, network, or another resolution failure prevented an
    observation.  Status remains diagnostic, while mutating paths reject both.
    """
    try:
        return resolve_remote_ref("origin", resolve_split_branch(module_name), runner=runner)
    except RemoteBranchAbsentError:
        return ""
    except GitError, SealError, ModuleNotFoundError:
        return None


# ---------------------------------------------------------------------------
# SA136d seal primitives
# ---------------------------------------------------------------------------

_SEAL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class SealError(GitError):
    """A fail-closed seal error with machine-readable operation context."""

    def __init__(
        self,
        message: str,
        *,
        module: str,
        version: str,
        cleanup_error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.module = module
        self.version = version
        self.cleanup_error = cleanup_error


class RemoteBranchAbsentError(GitError):
    """The named remote split branch was observed successfully and is absent."""


def _seal_error(
    message: str,
    *,
    module: str,
    version: str,
    cleanup_error: str | None = None,
) -> SealError:
    return SealError(
        message,
        module=module,
        version=version,
        cleanup_error=cleanup_error,
    )


def _seal_sha(value: object, *, description: str, module: str, version: str) -> str:
    """Return a canonical SHA or reject ambiguous Git output."""
    if not isinstance(value, str):
        raise _seal_error(
            f"Malformed {description}: expected a 40-hex SHA",
            module=module,
            version=version,
        )
    sha = value.strip()
    if not _SEAL_SHA_RE.fullmatch(sha):
        raise _seal_error(
            f"Malformed {description}: expected one 40-hex SHA, got {value!r}",
            module=module,
            version=version,
        )
    return sha.lower()


def _parse_remote_records(
    output: object,
    *,
    expected_refs: set[str],
    description: str,
    module: str,
    version: str,
) -> dict[str, str]:
    """Parse one strict ``ls-remote`` response without accepting ambiguity."""
    if not isinstance(output, str):
        raise _seal_error(
            f"Malformed {description}: expected text output",
            module=module,
            version=version,
        )
    records = output.splitlines()
    if any(not record.strip() for record in records):
        raise _seal_error(
            f"Malformed {description}: blank record",
            module=module,
            version=version,
        )
    parsed: dict[str, str] = {}
    for record in records:
        fields = record.split()
        if len(fields) != 2:
            raise _seal_error(
                f"Malformed {description}: expected SHA and ref, got {record!r}",
                module=module,
                version=version,
            )
        sha, ref = fields
        if ref not in expected_refs:
            raise _seal_error(
                f"Unexpected ref in {description}: {ref!r}",
                module=module,
                version=version,
            )
        if ref in parsed:
            raise _seal_error(
                f"Duplicate ref in {description}: {ref!r}",
                module=module,
                version=version,
            )
        parsed[ref] = _seal_sha(
            sha,
            description=f"{description} SHA",
            module=module,
            version=version,
        )
    return parsed


def resolve_remote_ref(
    remote: str,
    ref: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> str:
    """
    Resolve a branch or split tag using the trusted publication runner.

    A tag lookup reads its direct and peeled records together.  A peeled
    lookup (used for post-action verification) reads only the peeled record.
    The empty string is reserved for an absent tag; branches are required.
    """
    module = "seal"
    version = "unknown"
    # The wrapper is also a test seam.  The seal itself supplies the precise
    # module/version context when validating the returned value.
    cwd = path or _core._REPO_ROOT
    if ref.endswith("^{}"):
        tag = ref[:-3]
        validate_tag_name(tag)
        args = ["ls-remote", "--tags", "--", remote, f"refs/tags/{tag}^{{}}"]
        result = runner.run(args, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GitError(f"Failed to resolve remote tag {tag!r}: {result.stderr}")
        parsed = _parse_remote_records(
            result.stdout,
            expected_refs={f"refs/tags/{tag}^{{}}"},
            description=f"peeled remote tag {tag!r}",
            module=module,
            version=version,
        )
        return next(iter(parsed.values()), "")

    if ref.startswith("splits/") and ref.count("/") == 1:
        args = ["ls-remote", "--heads", remote, ref]
        result = runner.run(args, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GitError(f"Failed to resolve remote branch {ref!r}: {result.stderr}")
        parsed = _parse_remote_records(
            result.stdout,
            expected_refs={f"refs/heads/{ref}"},
            description=f"remote branch {ref!r}",
            module=module,
            version=version,
        )
        if not parsed:
            raise RemoteBranchAbsentError(f"Remote branch {ref!r} is absent")
        return next(iter(parsed.values()))

    validate_tag_name(ref)
    direct_ref = f"refs/tags/{ref}"
    peeled_ref = f"{direct_ref}^{{}}"
    args = ["ls-remote", "--tags", "--", remote, direct_ref, peeled_ref]
    result = runner.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitError(f"Failed to resolve remote tag {ref!r}: {result.stderr}")
    parsed = _parse_remote_records(
        result.stdout,
        expected_refs={direct_ref, peeled_ref},
        description=f"remote tag {ref!r}",
        module=module,
        version=version,
    )
    return parsed.get(peeled_ref) or parsed.get(direct_ref, "")


def get_tree_sha(
    commit: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> str:
    """Resolve a commit's verified tree through the trusted runner."""
    result = runner.run(
        ["rev-parse", f"{commit}^{{tree}}"],
        cwd=path or _core._REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to resolve tree for {commit}: {result.stderr}")
    return _seal_sha(
        result.stdout,
        description=f"tree for {commit}",
        module="seal",
        version="unknown",
    )


def get_local_tag_commit(
    tag: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> str | None:
    """Return a local tag's peeled commit SHA, or ``None`` when absent."""
    validate_tag_name(tag)

    cwd = path or _core._REPO_ROOT
    presence_ref = f"refs/tags/{tag}"
    try:
        presence = runner.run(
            ["show-ref", "--verify", "--quiet", presence_ref],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Failed to inspect local tag {tag!r}: {exc}") from exc

    if presence.returncode == 1:
        return None

    if presence.returncode != 0:
        raise GitError(f"Failed to inspect local tag {tag!r}: {presence.stderr}")

    peeled_ref = f"{presence_ref}^{{commit}}"
    try:
        result = runner.run(
            ["rev-parse", "--verify", peeled_ref],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Failed to resolve local tag {tag!r}: {exc}") from exc
    if result.returncode != 0:
        raise GitError(f"Failed to resolve local tag {tag!r}: {result.stderr}")
    return _seal_sha(
        result.stdout,
        description=f"local tag commit {tag!r}",
        module="seal",
        version="unknown",
    )


def create_annotated_tag(
    tag: str,
    commit: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> None:
    """Create one annotated local tag without force or replacement flags."""
    validate_tag_name(tag)
    result = runner.run(
        ["tag", "--annotate", tag, commit, "--message", tag],
        cwd=path or _core._REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to create local tag {tag!r}: {result.stderr}")


def push_tag(
    tag: str,
    remote: str = "origin",
    path: Path | None = None,
    *,
    refspec: str | None = None,
    runner: GitRunner,
) -> None:
    """Push exactly one tag ref through the trusted runner."""
    validate_tag_name(tag)
    expected_refspec = f"{tag}:refs/tags/{tag}"
    if refspec is not None and refspec != expected_refspec:
        raise GitError(f"Unexpected tag refspec: {refspec!r}")
    result = runner.run(
        ["push", "--", remote, f"refs/tags/{tag}:refs/tags/{tag}"],
        cwd=path or _core._REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to push tag {tag!r}: {result.stderr}")


def delete_local_tag(
    tag: str,
    path: Path | None = None,
    *,
    runner: GitRunner,
) -> None:
    """Delete only the local tag named by the seal cleanup obligation."""
    validate_tag_name(tag)
    result = runner.run(
        ["tag", "--delete", tag],
        cwd=path or _core._REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GitError(f"Failed to delete local tag {tag!r}: {result.stderr}")
