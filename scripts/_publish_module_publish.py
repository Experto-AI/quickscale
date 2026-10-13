"""
Publish, publish-all, and release-gate flows for the ``publish_module`` split.

Every git collaborator is resolved through :mod:`_publish_module_git` at call
time, so a test's seam is the module that defines the name (decisions.md,
Split-Facade Seams).
"""

from __future__ import annotations

import sys

import _publish_module_core as _core
import _publish_module_git as _git
from _publish_module_git import GitError, GitRunner


def _check_release_authoritative(runner: GitRunner) -> None:
    """
    Gate: refuse mutating publish flows unless source is release-authoritative (F2.9a).

    Release-authoritative means the VERSION file matches a git tag pointing at
    HEAD, aligned with the publish workflow authority in
    .github/workflows/publish.yml.

    Raises SystemExit with a clear operator-facing message when the source is
    not release-authoritative.  This gate applies to mutating flows only
    (single-module publish); --status remains read-only
    and must not fail closed just because HEAD is untagged.
    (--publish-outdated was disabled in SA117 Phase 4.)
    """
    is_auth, version, tag, reason = _git.is_release_authoritative(_core._REPO_ROOT, runner=runner)
    if is_auth:
        _core._print_success(f"Source is release-authoritative (VERSION={version}, tag={tag})")
        return

    _core._print_error("Source is not release-authoritative (F2.9a gate)")
    if reason:
        _core._print_error(f"  Reason: {reason}")
    _core._print_info(
        "Mutating publish flows require the source state to match the publish workflow authority:"
    )
    _core._print_info("  - VERSION file must contain the release version")
    _core._print_info("  - HEAD must be tagged with that version")
    _core._print_info("  - The tag must match the VERSION file content")
    _core._print_info("See .github/workflows/publish.yml for the authority chain.")
    _core._print_info(
        "Use --status for read-only inspection (does not require release-authoritative state)."
    )
    sys.exit(1)


def _require_fast_forward(
    expected_remote_sha: str,
    local_split_sha: str,
    *,
    runner: GitRunner,
) -> None:
    """Fail closed unless the observed remote tip can fast-forward to the local split."""
    _git.validate_expected_sha(expected_remote_sha)
    try:
        result = runner.run(
            ["merge-base", "--is-ancestor", expected_remote_sha, local_split_sha],
            cwd=_core._REPO_ROOT,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise GitError(f"Could not verify split-branch ancestry: {exc}") from exc

    if result.returncode == 0:
        return
    if result.returncode == 1:
        raise GitError(
            f"observed remote tip {expected_remote_sha} is not an ancestor of "
            f"local split {local_split_sha}; refusing a non-fast-forward overwrite"
        )

    detail = (result.stderr or result.stdout).strip()
    if not detail:
        detail = f"git merge-base exited with status {result.returncode}"
    raise GitError(
        "Could not verify that the split publication is a fast-forward; "
        f"fetch the remote history and retry ({detail})"
    )


def _publish_module(
    module_name: str,
    *,
    expected_remote_sha: str,
    runner: GitRunner,
) -> None:
    """
    Split and push a single module using the provenance-aware helpers.

    *expected_remote_sha* is required (SA117 Phase 4): a freshly observed
    exact 40-hex SHA for force-with-lease pinning.  The bare ``--force``
    fallback has been removed.
    """
    # Defense-in-depth: validate name shape before any path/branch resolution
    # so callers that bypass main() still get a clean GitError, not a
    # traceback (CR-M5-P1-001).
    try:
        module_path = _git.resolve_module_path(module_name)
        split_branch = _git.resolve_split_branch(module_name)
    except GitError as e:
        _core._print_error(str(e))
        sys.exit(1)

    _core._print_info(f"Publishing module: {module_name}")
    _core._print_info(f"Module path: {module_path}")
    _core._print_info(f"Split branch: {split_branch}")
    print()

    local_split_sha = _git._get_local_split_sha(module_path, runner)
    if local_split_sha is None:
        _core._print_error(f"Could not compute subtree split for module '{module_name}'")
        sys.exit(1)

    _core._print_info("Checking that publication fast-forwards the observed remote tip...")
    try:
        _require_fast_forward(expected_remote_sha, local_split_sha, runner=runner)
    except GitError as e:
        _core._print_error(f"Refusing to publish module '{module_name}': {e}")
        sys.exit(1)

    _core._print_info("Running git subtree split...")
    try:
        split_sha = _git.run_git_subtree_split(
            prefix=module_path,
            branch=split_branch,
            rejoin=True,
            ignore_joins=True,
            path=_core._REPO_ROOT,
            runner=runner,
        )
        _core._print_success(f"Git subtree split completed (SHA: {split_sha[:12]}...)")
    except GitError as e:
        _core._print_error(f"Git subtree split failed: {e}")
        if "cache for" in str(e) and "already exists" in str(e):
            _core._print_error("Git subtree split failed due to cache error.")
            _core._print_info("Try running with --clean to fix this:")
            _core._print_info(f"  {sys.argv[0]} {module_name} --clean")
        sys.exit(1)

    if split_sha.lower() != local_split_sha.lower():
        _core._print_error(
            f"Refusing to publish module '{module_name}': split identity changed "
            "after the ancestry check; retry from a stable worktree"
        )
        sys.exit(1)

    _core._print_info("Pushing split branch to origin...")
    try:
        _git.push_split_branch(
            split_branch,
            remote="origin",
            expected_remote_sha=expected_remote_sha,
            source_sha=split_sha,
            path=_core._REPO_ROOT,
            runner=runner,
        )
        _core._print_success("Split branch pushed to origin")
    except GitError as e:
        _core._print_error(f"Failed to push split branch to origin: {e}")
        sys.exit(1)

    print()
    _core._print_success(f"Module '{module_name}' published successfully!")
    _core._print_info(f"Split branch: {split_branch}")
    _core._print_info(
        f"Users can now embed this module with: quickscale embed --module {module_name}"
    )


def _publish_all(runner: GitRunner, *, modules: list[str]) -> None:
    """
    Publish every outdated module serially, each against its own fresh lease.

    This is not the disabled ``--publish-outdated``: that path pushed with a
    bare ``--force``.  Here each module's remote SHA is observed live
    immediately before its own push and handed to ``_publish_module`` as the
    force-with-lease expectation, exactly as a hand-pasted
    ``make publish-module`` would.  Before pushing, ``_publish_module`` also
    requires that observed tip to be an ancestor of the newly generated local
    split.  A module whose remote tip already equals its local split is skipped.
    An absent, unobservable, or divergent remote branch stops the batch.  The
    first failure leaves later modules untouched.

    The release gate runs once, before the batch.  Each publish's ``--rejoin``
    merge moves HEAD without changing its tree, so the batch instead pins the
    gated HEAD tree and refuses to continue if any iteration sees another one:
    every module is split from exactly the release-authoritative bytes.
    """
    gated_tree = _head_tree(runner)
    published: list[str] = []
    skipped: list[str] = []
    try:
        for module_name in modules:
            if _head_tree(runner) != gated_tree:
                _core._print_error(
                    "HEAD tree changed during the batch; refusing to publish from bytes the "
                    "release gate did not check"
                )
                sys.exit(1)
            local_sha = _git._get_local_split_sha(_git.resolve_module_path(module_name), runner)
            if local_sha is None:
                _core._print_error(f"Could not compute subtree split for module '{module_name}'")
                sys.exit(1)
            remote_sha = _git._observe_remote_branch_sha(module_name, runner)
            if not remote_sha:
                _core._print_error(
                    f"Remote split branch for '{module_name}' is absent or could not be "
                    "observed; an absent branch is not authorization"
                )
                sys.exit(1)
            if remote_sha.lower() == local_sha.lower():
                _core._print_info(f"{module_name}: up to date ({local_sha[:12]}), skipping")
                skipped.append(module_name)
                continue
            _core._print_info(f"{module_name}: remote {remote_sha[:12]} -> local {local_sha[:12]}")
            _publish_module(module_name, expected_remote_sha=remote_sha, runner=runner)
            published.append(module_name)
            print()
    finally:
        # Runs on success and on every exit above, so a partial batch still
        # reports what was pushed and how to restore the release gate.
        _core._print_success(f"Published: {' '.join(published) or 'none'}")
        if skipped:
            _core._print_info(f"Already up to date: {' '.join(skipped)}")
        if published:
            _core._print_warning(
                "Each publish added a --rejoin merge commit, so HEAD is no longer tagged "
                "(the tree is unchanged)."
            )
            _core._print_info("  Move the local release tag before sealing or publishing again:")
            _core._print_info(f"    git tag -f {_core._read_repository_version()}")


def _head_tree(runner: GitRunner) -> str:
    """Return the tree SHA of HEAD."""
    result = runner.run(
        ["rev-parse", "HEAD^{tree}"],
        cwd=_core._REPO_ROOT,
        capture_output=True,
        text=True,
    )
    tree = result.stdout.strip() if result.returncode == 0 else ""
    if not tree:
        _core._print_error("Could not resolve the HEAD tree")
        sys.exit(1)
    return tree


def _run_release_gates(runner: GitRunner) -> None:
    """Apply every read-only pre-mutation publication gate with one runner."""
    try:
        _check_release_authoritative(runner)
        _git.validate_publication_origin(_core._REPO_ROOT, runner=runner)
        _git.validate_publication_local_config(_core._REPO_ROOT, runner=runner)
    except GitError as exc:
        _core._print_error(f"Publication preflight failed: {exc}")
        sys.exit(1)
