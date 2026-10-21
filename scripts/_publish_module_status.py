"""
Read-only publish status diagnostics for the ``publish_module`` split.

Status is advisory: it never fails closed on untagged HEAD or an unobservable
remote, and it reports one row per module plus explicit next-action guidance.
Every git collaborator is resolved through :mod:`_publish_module_git` at call
time (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import _publish_module_core as _core
import _publish_module_git as _git
from _publish_module_git import GitError, GitRunner, SealError

#: Status label for a module whose immutable ``VERSION`` seal tag no longer
#: names the module's current subtree split.
SEAL_STALE = "sealed but stale"


def _show_provenance_diagnostics(runner: GitRunner) -> bool:
    """
    Report read-only release-provenance diagnostics (F2.9b).

    Inspects whether the source state is release-authoritative (VERSION matches
    a git tag at HEAD) and prints an operator-facing summary.  This is strictly
    read-only: it never fails closed and never exits, so operators can inspect
    untagged or mismatched split provenance without triggering the mutating
    F2.9a gate.

    Returns True when the source is release-authoritative, False otherwise.
    """
    is_auth, version, tag, reason = _git.is_release_authoritative(_core._REPO_ROOT, runner=runner)
    if is_auth:
        _core._print_success(f"Release provenance: authoritative (VERSION={version}, tag={tag})")
        return True

    _core._print_warning(f"Release provenance: NOT authoritative (VERSION={version or 'unknown'})")
    if reason:
        _core._print_warning(f"  Reason: {reason}")
    _core._print_info("  Mutating publish flows are blocked until HEAD is tagged to match VERSION.")
    return False


def _get_module_publish_state(
    module_name: str,
    runner: GitRunner,
) -> tuple[str, str, str, str]:
    """Return state from the computed local split and the live remote branch tip."""
    try:
        module_path = _git.resolve_module_path(module_name)
    except GitError as e:
        _core._print_error(str(e))
        sys.exit(1)

    local_sha = _git._get_local_split_sha(module_path, runner)
    if local_sha is None:
        _core._print_error(f"Could not compute subtree split for module '{module_name}'")
        sys.exit(1)

    published_sha = _git._observe_remote_branch_sha(module_name, runner)

    if published_sha is None:
        return "unobservable", local_sha, "", "none"
    if not published_sha:
        return "unpublished", local_sha, "", "none"
    if local_sha == published_sha:
        return "up-to-date", local_sha, published_sha, "remote-live"
    return "outdated", local_sha, published_sha, "remote-live"


@dataclass(frozen=True)
class ModuleSealInspection:
    """One module's immutable seal tag compared with its current split."""

    module: str
    tag: str
    split_sha: str
    split_tree_sha: str
    tag_sha: str
    tag_tree_sha: str
    state: str
    error: str | None = None


def _inspect_module_seal(
    module_name: str,
    version: str,
    split_sha: str,
    runner: GitRunner,
    *,
    repo_root: Path | None = None,
) -> ModuleSealInspection:
    """
    Compare the remote ``VERSION`` seal tag with the module's current split.

    Freshness follows content identity, not commit identity: sealing reuses the
    previous release commit when the split tree is unchanged
    (release_gates_policy.md Rule 6), so the comparison is between the two
    trees.  A lightweight tag has no peeled ``ls-remote`` record; the shared
    tag resolver falls back to the direct target only when peeling is absent.
    """
    try:
        tag = _git.resolve_split_tag(module_name, version)
    except (GitError, ModuleNotFoundError) as exc:
        return ModuleSealInspection(
            module_name, "", split_sha, "", "", "", "unobservable", str(exc)
        )
    try:
        if repo_root is None:
            peeled_sha = _git.resolve_remote_ref("origin", tag, runner=runner)
        else:
            peeled_sha = _git.resolve_remote_ref("origin", tag, path=repo_root, runner=runner)
    except (GitError, ModuleNotFoundError) as exc:
        return ModuleSealInspection(
            module_name, tag, split_sha, "", "", "", "unobservable", str(exc)
        )
    if not peeled_sha:
        return ModuleSealInspection(module_name, tag, split_sha, "", "", "", "unsealed")
    try:
        tag_sha = _git._seal_sha(
            peeled_sha,
            description=f"peeled remote tag {tag!r}",
            module=module_name,
            version=version,
        )
    except SealError as exc:
        return ModuleSealInspection(
            module_name, tag, split_sha, "", "", "", "unobservable", str(exc)
        )
    try:
        split_tree_sha = _git.get_tree_sha(split_sha, path=repo_root, runner=runner)
        tag_tree_sha = _git.get_tree_sha(tag_sha, path=repo_root, runner=runner)
    except (GitError, OSError) as exc:
        return ModuleSealInspection(
            module_name, tag, split_sha, "", tag_sha, "", "unobservable", str(exc)
        )
    if split_tree_sha == tag_tree_sha:
        state = "sealed"
    else:
        state = "stale"
    return ModuleSealInspection(
        module_name,
        tag,
        split_sha,
        split_tree_sha,
        tag_sha,
        tag_tree_sha,
        state,
    )


def _get_module_seal_state(
    module_name: str,
    version: str,
    split_sha: str,
    runner: GitRunner,
) -> str:
    """Return the read-only status label for one module's seal tag."""
    inspection = _inspect_module_seal(module_name, version, split_sha, runner)
    if inspection.state == "sealed":
        return f"sealed@{version}"
    if inspection.state == "stale":
        return SEAL_STALE
    # Status is diagnostic rather than a gate: an absent tag, a runner that
    # cannot resolve a remote target, or the minimal hermetic publication
    # fixture (which omits the manifest package used by the shared version
    # parser) all read as unsealed here.  The release check keeps the
    # unobservable distinction and fails closed on it.
    return "unsealed"


@dataclass
class _StatusRoll:
    """One collection pass over the frozen module set."""

    outdated: list[str]
    unpublished: list[str]
    unobservable: list[str]
    sealed_stale: list[str]
    remote_shas: dict[str, str]
    all_sealed: bool

    @property
    def needs_attention(self) -> bool:
        return bool(self.outdated or self.unpublished or self.unobservable or self.sealed_stale)


def _print_module_status(
    module_name: str,
    state: str,
    seal_state: str,
    local_sha: str,
    pub_sha: str,
    pub_source: str,
) -> None:
    """Print one module's status row exactly as the pre-split status did."""
    if state == "up-to-date":
        print(f"  {module_name:<16} {seal_state} up to date ({pub_source}, {local_sha[:12]})")
    elif state == "outdated":
        print(
            f"  {module_name:<16} {seal_state} outdated "
            f"({pub_source}: local {local_sha[:12]} != published {pub_sha[:12]})"
        )
    elif state == "unpublished":
        print(
            f"  {module_name:<16} {seal_state} unpublished "
            f"(local {local_sha[:12]}, no split branch)"
        )
    elif state == "unobservable":
        print(
            f"  {module_name:<16} {seal_state} remote state unobservable (local {local_sha[:12]})"
        )
    if state != "up-to-date":
        if state == "unpublished":
            remote_state = "absent"
        elif state == "unobservable":
            remote_state = "could not observe"
        else:
            remote_state = pub_sha
        print(f"  {'':<16} remote branch now: {remote_state}")


def _collect_module_statuses(
    frozen_modules: list[str],
    version: str,
    runner: GitRunner,
) -> _StatusRoll:
    """Inspect every frozen module and accumulate the status categories."""
    outdated: list[str] = []
    unpublished: list[str] = []
    unobservable: list[str] = []
    sealed_stale: list[str] = []
    all_sealed = True
    remote_shas: dict[str, str] = {}
    for module_name in frozen_modules:
        state, local_sha, pub_sha, pub_source = _get_module_publish_state(module_name, runner)
        seal_state = _get_module_seal_state(module_name, version, local_sha, runner)
        remote_shas[module_name] = pub_sha
        _print_module_status(module_name, state, seal_state, local_sha, pub_sha, pub_source)
        if state == "outdated":
            outdated.append(module_name)
        elif state == "unpublished":
            unpublished.append(module_name)
        elif state == "unobservable":
            unobservable.append(module_name)
        if seal_state == SEAL_STALE:
            sealed_stale.append(module_name)
        if seal_state != f"sealed@{version}":
            all_sealed = False
    return _StatusRoll(outdated, unpublished, unobservable, sealed_stale, remote_shas, all_sealed)


def _print_status_warnings(roll: _StatusRoll) -> None:
    if roll.outdated:
        _core._print_warning(f"Outdated split branches: {' '.join(roll.outdated)}")
    if roll.unpublished:
        _core._print_warning(f"Unpublished split branches: {' '.join(roll.unpublished)}")
    if roll.unobservable:
        _core._print_warning(f"Unobservable split branches: {' '.join(roll.unobservable)}")
    if roll.sealed_stale:
        _core._print_warning(f"Sealed but stale (blocking): {' '.join(roll.sealed_stale)}")


def _print_next_actions(roll: _StatusRoll, *, is_auth: bool) -> None:
    """Print the F2.9b next-action guidance for the observed attention states."""
    _core._print_info("Next actions:")
    if not is_auth:
        # NOTE: keep --status output free of the lowercase substring
        # "not release-authoritative"; the read-only status test asserts that
        # substring is absent so --status is never mistaken for the F2.9a gate.
        _core._print_info("  Tag HEAD to match VERSION so the source is release-authoritative.")
    if roll.unobservable:
        _core._print_info("  Restore remote access, then re-run status before publishing.")
    if roll.unpublished:
        _core._print_info(
            "  A confirmed absent branch is not publication authorization; "
            "restore it through maintainer recovery, then re-run status."
        )
    if roll.sealed_stale:
        _core._print_info(
            "  Delete each stale remote and local split tag, republish the split "
            "branch, then reseal:"
        )
        _core._print_info("    docs/technical/publish_procedure.md#phase-5--seal-the-split-tags")
    if roll.outdated:
        if roll.unpublished or roll.unobservable:
            _core._print_info("  Recover every blocked branch before using make publish-modules.")
        else:
            _core._print_info("  Publish every outdated module (fresh lease per module):")
            _core._print_info("    make publish-modules")
        ready = [name for name in roll.outdated if roll.remote_shas.get(name)]
        if ready:
            print()
            _core._print_info(
                "  Observed just now -- re-observe if anything else may have pushed since:"
            )
            for name in ready:
                _core._print_info(
                    f"    make publish-module MODULE={name} "
                    f"EXPECTED_REMOTE_SHA={roll.remote_shas[name]}"
                )


def _show_status(
    runner: GitRunner,
    *,
    version: str | None = None,
    modules: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """Show split-branch and peeled-tag status for one frozen module set."""
    if version is None:
        version = _core._read_repository_version()
    frozen_modules = list(_core._list_modules() if modules is None else modules)
    _git._warn_uncommitted_changes(runner)
    _core._print_info("Inspecting module publish status...")
    print()

    # F2.9b: read-only release-provenance diagnostic (never fails closed).
    is_auth = _show_provenance_diagnostics(runner)
    print()

    roll = _collect_module_statuses(frozen_modules, version, runner)

    print()
    if roll.needs_attention:
        _print_status_warnings(roll)
        print()
        _print_next_actions(roll, is_auth=is_auth)
        return roll.all_sealed

    _core._print_success("All module split branches are up to date.")
    if not is_auth:
        print()
        _core._print_info("Next action:")
        _core._print_info("  Tag HEAD to match VERSION before any mutating publish flow.")
    return roll.all_sealed
