"""Sealed-tag verification for the module update flow.

Implementation detail of :mod:`quickscale_cli.commands._module_update`; the
update path proves every installed module's mutable split branch still carries
the same tree as its immutable ``splits/<module>-module/<version>`` seal
before the first subtree pull.  A moved branch then cannot change content
under a fixed version label, and a missing seal fails closed before any
mutation (SA319).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import quickscale_core.utils.git_errors as _git_errors
import quickscale_core.utils.git_naming as _git_naming
import quickscale_core.utils.git_repo as _git_repo
import quickscale_core.utils.git_tags as _git_tags


class _UpdateSealError(RuntimeError):
    """The sealed release tag could not be verified for an update."""


@dataclass(frozen=True)
class _UpdateSealPlan:
    """One module's verified sealed-tag update source."""

    module: str
    version: str
    tag: str
    tag_sha: str
    branch: str
    branch_sha: str


def _fetch_remote_commit(remote: str, commit: str) -> None:
    """Fetch one exact remote commit so its tree can be read locally."""
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        ["git", "fetch", "--no-tags", "--quiet", "--", remote, commit],  # noqa: S607 - PATH-resolved executable by design
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git fetch failed"
        raise _git_errors.GitError(
            f"Failed to fetch commit {commit} from {remote}: {detail}"
        )


def _remote_tree_sha(remote: str, commit: str) -> str:
    """Return a remote commit's tree SHA, fetching the commit when absent."""
    try:
        return _git_tags.get_tree_sha(commit)
    except _git_errors.GitError:
        _fetch_remote_commit(remote, commit)
        return _git_tags.get_tree_sha(commit)


def _remote_trees(
    remote: str, first_commit: str, second_commit: str
) -> tuple[str, str]:
    """Return both commits' tree SHAs, fetching them when absent."""
    return (
        _remote_tree_sha(remote, first_commit),
        _remote_tree_sha(remote, second_commit),
    )


def _preflight_update_seals(
    state: Any,
    remote: str,
    version: str,
) -> tuple[dict[str, _UpdateSealPlan], tuple[str, Exception] | None]:
    """Verify every installed module's seal before the first subtree pull.

    Returns the verified plans and, when a module fails, that module's name
    with the error.  The caller aborts on a failure without mutating any
    module, so a set-wide update never starts from a half-verified module set.
    """
    plans: dict[str, _UpdateSealPlan] = {}
    for name in state.modules:
        try:
            plans[name] = _resolve_update_seal(remote, name, version)
        except _UpdateSealError as error:
            return plans, (name, error)
    return plans, None


def _resolve_update_seal(
    remote: str,
    module_name: str,
    version: str,
) -> _UpdateSealPlan:
    """Resolve and verify one module's sealed tag before its subtree pull.

    The seal tag for the running core version must exist on *remote*, and the
    canonical split branch tip must carry the same tree.  The branch tip stays
    the transport ref, so the recorded ``commit_sha`` remains a real commit in
    the project's history while its content is proven equal to the seal.

    Raises:
        _UpdateSealError: When the tag is absent, the branch cannot be
            resolved, or the branch tip's tree differs from the seal's.
    """
    try:
        tag = _git_naming.resolve_split_tag(module_name, version)
        branch = _git_naming.resolve_split_branch(module_name)
    except _git_errors.GitError as error:
        raise _UpdateSealError(
            f"invalid split reference for {module_name}: {error}"
        ) from error

    try:
        tag_sha = _git_tags.resolve_remote_tag(remote, tag)
    except _git_errors.GitError as error:
        raise _UpdateSealError(
            f"sealed release tag '{tag}' for QuickScale {version} could not be "
            f"resolved: {error}"
        ) from error

    try:
        branch_sha = _git_repo.resolve_remote_ref(remote, branch)
    except _git_errors.GitError as error:
        raise _UpdateSealError(
            f"Failed to resolve source ref for {module_name}: {error}"
        ) from error

    if tag_sha == branch_sha:
        return _UpdateSealPlan(
            module=module_name,
            version=version,
            tag=tag,
            tag_sha=tag_sha,
            branch=branch,
            branch_sha=branch_sha,
        )

    try:
        tag_tree_sha, branch_tree_sha = _remote_trees(remote, tag_sha, branch_sha)
    except _git_errors.GitError as error:
        raise _UpdateSealError(
            f"could not verify sealed tag '{tag}' against split branch "
            f"'{branch}': {error}"
        ) from error

    if tag_tree_sha != branch_tree_sha:
        raise _UpdateSealError(
            f"split branch '{branch}' moved away from sealed tag '{tag}': "
            f"branch tree {branch_tree_sha[:12]} != tag tree "
            f"{tag_tree_sha[:12]}; publish the sealed release content or "
            "reseal before updating"
        )

    return _UpdateSealPlan(
        module=module_name,
        version=version,
        tag=tag,
        tag_sha=tag_sha,
        branch=branch,
        branch_sha=branch_sha,
    )
