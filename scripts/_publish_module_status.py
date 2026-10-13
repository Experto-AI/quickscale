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

import _publish_module_core as _core
import _publish_module_git as _git
from _publish_module_git import GitError, GitRunner, SealError


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


def _get_module_seal_state(
    module_name: str,
    version: str,
    published_sha: str,
    runner: GitRunner,
) -> str:
    """Determine seal state from the remote tag target, read-only."""
    try:
        tag = _git.resolve_split_tag(module_name, version)
        # A lightweight tag has no peeled ls-remote record.  The shared tag
        # resolver prefers that record for annotated tags and falls back to
        # the direct target only when peeling is absent.  This fallback is
        # intentionally limited to read-only status; newly pushed tags below
        # still use the peeled-only verification path.
        peeled_sha = _git.resolve_remote_ref("origin", tag, runner=runner)
    except GitError, ModuleNotFoundError:
        # Status is diagnostic rather than a gate.  A runner that cannot resolve
        # a remote target is represented as unsealed instead of causing a
        # mutation or turning inspection into a release-authority failure.  The
        # minimal hermetic publication fixture also omits the manifest package
        # used by the shared version parser; that is the same unsealed state for
        # this read-only diagnostic.
        return "unsealed"
    if not peeled_sha:
        return "unsealed"
    try:
        normalized_peeled = _git._seal_sha(
            peeled_sha,
            description=f"peeled remote tag {tag!r}",
            module=module_name,
            version=version,
        )
    except SealError:
        return "unsealed"
    if published_sha and normalized_peeled == published_sha.lower():
        return f"sealed@{version}"
    return "sealed-conflict"


@dataclass
class _StatusRoll:
    """One collection pass over the frozen module set."""

    outdated: list[str]
    unpublished: list[str]
    unobservable: list[str]
    remote_shas: dict[str, str]
    all_sealed: bool

    @property
    def needs_attention(self) -> bool:
        return bool(self.outdated or self.unpublished or self.unobservable)


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
    all_sealed = True
    remote_shas: dict[str, str] = {}
    for module_name in frozen_modules:
        state, local_sha, pub_sha, pub_source = _get_module_publish_state(module_name, runner)
        seal_state = _get_module_seal_state(module_name, version, pub_sha, runner)
        remote_shas[module_name] = pub_sha
        _print_module_status(module_name, state, seal_state, local_sha, pub_sha, pub_source)
        if state == "outdated":
            outdated.append(module_name)
        elif state == "unpublished":
            unpublished.append(module_name)
        elif state == "unobservable":
            unobservable.append(module_name)
        if seal_state != f"sealed@{version}":
            all_sealed = False
    return _StatusRoll(outdated, unpublished, unobservable, remote_shas, all_sealed)


def _print_status_warnings(roll: _StatusRoll) -> None:
    if roll.outdated:
        _core._print_warning(f"Outdated split branches: {' '.join(roll.outdated)}")
    if roll.unpublished:
        _core._print_warning(f"Unpublished split branches: {' '.join(roll.unpublished)}")
    if roll.unobservable:
        _core._print_warning(f"Unobservable split branches: {' '.join(roll.unobservable)}")


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
