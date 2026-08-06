#!/usr/bin/env python3
r"""
Provenance-aware split-publish wrapper for QuickScale modules (F2.8, F2.9a, F2.9b).

This script replaces the hardcoded module-path and branch-resolution logic
that previously lived entirely in ``scripts/publish_module.sh``.  It uses
the provenance-aware helper surface from
``quickscale_core.utils.git_utils`` so the split/publish execution path
shares the same resolution conventions as the embed/update paths.

F2.9a adds a release-authoritative gate: mutating publish flows refuse to
run unless the source state is release-authoritative (VERSION file matches
a git tag pointing at HEAD), aligned with the publish workflow authority in
.github/workflows/publish.yml.  The --status flag remains read-only and
does not require release-authoritative state.

F2.9b adds operator-facing diagnostics: --status reports release provenance
(tagged/untagged/mismatched source state), per-module split-branch state with
local-vs-published SHAs, and explicit next-action guidance.  --status stays
read-only and never fails closed; the mutating flows continue to fail closed
with the same explicit next-action guidance.

    Usage:
        poetry run python scripts/publish_module.py \\
            <module_name> --expected-remote-sha <sha|ABSENT> [--clean]
        poetry run python scripts/publish_module.py --status
        poetry run python scripts/publish_module.py --publish-outdated [--clean]

    Phase 4 (SA117): All mutating single-module publish calls require
    ``--expected-remote-sha``.  The value must be a 40-character hex SHA
    or the literal ``ABSENT``.  ``--publish-outdated`` and ``--status``
    reject the flag.

    Phase 4 also disables ``--publish-outdated`` entirely: it used bare
    ``--force`` internally, which violates the force-with-lease safety
    contract.  Use single-module publish with per-module
    ``--expected-remote-sha`` instead.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Ensure the quickscale_core package is importable when running from the
# repository root via ``poetry run python scripts/publish_module.py``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORE_SRC = _REPO_ROOT / "quickscale_core" / "src"
if str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

from quickscale_core.utils.git_utils import (  # noqa: E402
    GitError,
    GitRunner,
    build_publication_git_runner,
    is_git_repo,
    is_release_authoritative,
    is_working_directory_clean,
    push_split_branch,
    resolve_module_path,
    resolve_split_branch,
    run_git_subtree_split,
    validate_expected_sha,
    validate_module_name,
    validate_publication_origin,
)

# ---------------------------------------------------------------------------
# Output helpers (match the bash script's color conventions)
# ---------------------------------------------------------------------------

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def _print_info(msg: str) -> None:
    print(f"{BLUE}ℹ️  {msg}{NC}")


def _print_success(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{NC}")


def _print_warning(msg: str) -> None:
    print(f"{YELLOW}⚠️  {msg}{NC}")


def _print_error(msg: str) -> None:
    print(f"{RED}❌ {msg}{NC}")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _list_modules() -> list[str]:
    """Return the fail-hard authoritative shipped-module inventory."""
    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        authoritative_module_names,
    )

    return authoritative_module_names()


def _has_uncommitted_changes(runner: GitRunner) -> bool:
    """Return True if the working directory has uncommitted changes."""
    try:
        # Publication uses git_utils' binary, NUL-safe status parser.  Any
        # malformed non-empty stream is treated as dirty/fail-closed rather
        # than being silently normalized by text or newline parsing.
        return not is_working_directory_clean(_REPO_ROOT, runner=runner)
    except GitError:
        return True


def _warn_uncommitted_changes(runner: GitRunner) -> None:
    if _has_uncommitted_changes(runner):
        _print_warning(
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
    _print_warning(
        "You have uncommitted changes. Published split branches only include committed history."
    )
    print()
    reply = input("Continue anyway? (y/N): ")
    if reply.strip().lower() not in ("y", "yes"):
        _print_info("Aborted by user")
        return False
    return True


def _maybe_clean_subtree_cache(clean: bool) -> None:
    if clean:
        _print_info("Cleaning git subtree cache...")
        cache_dir = _REPO_ROOT / ".git" / "subtree-cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)


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
    is_auth, version, tag, reason = is_release_authoritative(_REPO_ROOT, runner=runner)
    if is_auth:
        _print_success(f"Source is release-authoritative (VERSION={version}, tag={tag})")
        return

    _print_error("Source is not release-authoritative (F2.9a gate)")
    if reason:
        _print_error(f"  Reason: {reason}")
    _print_info(
        "Mutating publish flows require the source state to match the publish workflow authority:"
    )
    _print_info("  - VERSION file must contain the release version")
    _print_info("  - HEAD must be tagged with that version")
    _print_info("  - The tag must match the VERSION file content")
    _print_info("See .github/workflows/publish.yml for the authority chain.")
    _print_info(
        "Use --status for read-only inspection (does not require release-authoritative state)."
    )
    sys.exit(1)


def _get_local_split_sha(module_path: str, runner: GitRunner) -> str | None:
    """Compute the subtree split SHA for *module_path* without creating a branch."""
    result = runner.run(
        ["subtree", "split", f"--prefix={module_path}", "--ignore-joins"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return sha if sha else None


def _get_published_split_ref(split_branch: str, runner: GitRunner) -> tuple[str, str]:
    """
    Return ``(sha, source)`` for the published split branch.

    *source* is one of ``local-branch``, ``remote-tracking``, or ``none``.
    """
    # Check local branch first
    result = runner.run(
        ["rev-parse", "--verify", split_branch],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sha = result.stdout.strip()
        if sha:
            return sha, "local-branch"

    # Check remote-tracking branch
    result = runner.run(
        ["rev-parse", "--verify", f"origin/{split_branch}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sha = result.stdout.strip()
        if sha:
            return sha, "remote-tracking"

    return "", "none"


def _get_module_publish_state(
    module_name: str,
    runner: GitRunner,
) -> tuple[str, str, str, str]:
    """Return ``(state, local_sha, published_sha, published_source)``."""
    try:
        module_path = resolve_module_path(module_name)
        split_branch = resolve_split_branch(module_name)
    except GitError as e:
        _print_error(str(e))
        sys.exit(1)

    local_sha = _get_local_split_sha(module_path, runner)
    if local_sha is None:
        _print_error(f"Could not compute subtree split for module '{module_name}'")
        sys.exit(1)

    published_sha, published_source = _get_published_split_ref(split_branch, runner)

    if not published_sha:
        return "unpublished", local_sha, "", published_source
    if local_sha == published_sha:
        return "up-to-date", local_sha, published_sha, published_source
    return "outdated", local_sha, published_sha, published_source


def _publish_module(
    module_name: str,
    *,
    expected_remote_sha: str,
    runner: GitRunner,
) -> None:
    """
    Split and push a single module using the provenance-aware helpers.

    *expected_remote_sha* is required (SA117 Phase 4): a 40-character hex
    SHA for force-with-lease pinning, or ``ABSENT`` for first-time publish
    (no known remote SHA).  The legacy bare ``--force`` fallback has been
    removed.
    """
    # Defense-in-depth: validate name shape before any path/branch resolution
    # so callers that bypass main() still get a clean GitError, not a
    # traceback (CR-M5-P1-001).
    try:
        module_path = resolve_module_path(module_name)
        split_branch = resolve_split_branch(module_name)
    except GitError as e:
        _print_error(str(e))
        sys.exit(1)

    _print_info(f"Publishing module: {module_name}")
    _print_info(f"Module path: {module_path}")
    _print_info(f"Split branch: {split_branch}")
    print()

    _print_info("Running git subtree split...")
    try:
        split_sha = run_git_subtree_split(
            prefix=module_path,
            branch=split_branch,
            rejoin=True,
            ignore_joins=True,
            path=_REPO_ROOT,
            runner=runner,
        )
        _print_success(f"Git subtree split completed (SHA: {split_sha[:12]}...)")
    except GitError as e:
        _print_error(f"Git subtree split failed: {e}")
        if "cache for" in str(e) and "already exists" in str(e):
            _print_error("Git subtree split failed due to cache error.")
            _print_info("Try running with --clean to fix this:")
            _print_info(f"  {sys.argv[0]} {module_name} --clean")
        sys.exit(1)

    _print_info("Pushing split branch to origin...")
    try:
        push_split_branch(
            split_branch,
            remote="origin",
            expected_remote_sha=expected_remote_sha,
            path=_REPO_ROOT,
            runner=runner,
        )
        _print_success("Split branch pushed to origin")
    except GitError as e:
        _print_error(f"Failed to push split branch to origin: {e}")
        sys.exit(1)

    print()
    _print_success(f"Module '{module_name}' published successfully!")
    _print_info(f"Split branch: {split_branch}")
    _print_info(f"Users can now embed this module with: quickscale embed --module {module_name}")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


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
    is_auth, version, tag, reason = is_release_authoritative(_REPO_ROOT, runner=runner)
    if is_auth:
        _print_success(f"Release provenance: authoritative (VERSION={version}, tag={tag})")
        return True

    _print_warning(f"Release provenance: NOT authoritative (VERSION={version or 'unknown'})")
    if reason:
        _print_warning(f"  Reason: {reason}")
    _print_info("  Mutating publish flows are blocked until HEAD is tagged to match VERSION.")
    return False


def _show_status(runner: GitRunner) -> None:
    """Show split-branch status and provenance diagnostics for every module (F2.9b)."""
    _warn_uncommitted_changes(runner)
    _print_info("Inspecting module publish status...")
    print()

    # F2.9b: read-only release-provenance diagnostic (never fails closed).
    is_auth = _show_provenance_diagnostics(runner)
    print()

    outdated: list[str] = []
    unpublished: list[str] = []

    for module_name in _list_modules():
        state, local_sha, pub_sha, pub_source = _get_module_publish_state(module_name, runner)
        if state == "up-to-date":
            print(f"  {module_name:<16} up to date ({pub_source}, {local_sha[:12]})")
        elif state == "outdated":
            print(
                f"  {module_name:<16} outdated "
                f"({pub_source}: local {local_sha[:12]} != published {pub_sha[:12]})"
            )
            outdated.append(module_name)
        elif state == "unpublished":
            print(f"  {module_name:<16} unpublished (local {local_sha[:12]}, no split branch)")
            unpublished.append(module_name)

    print()
    if not outdated and not unpublished:
        _print_success("All module split branches are up to date.")
        if not is_auth:
            print()
            _print_info("Next action:")
            _print_info("  Tag HEAD to match VERSION before any mutating publish flow.")
        return

    if outdated:
        _print_warning(f"Outdated split branches: {' '.join(outdated)}")
    if unpublished:
        _print_warning(f"Unpublished split branches: {' '.join(unpublished)}")

    # F2.9b: explicit next-action guidance (read-only; --status never fails closed).
    print()
    _print_info("Next actions:")
    if not is_auth:
        # NOTE: keep --status output free of the lowercase substring
        # "not release-authoritative"; the read-only status test asserts that
        # substring is absent so --status is never mistaken for the F2.9a gate.
        _print_info("  1. Tag HEAD to match VERSION so the source is release-authoritative.")
        _print_info("  2. Re-run single-module publish:")
        _print_info("       make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<40hex|ABSENT>")
    else:
        _print_info("  Publish each outdated module individually:")
        _print_info("    make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<40hex|ABSENT>")


def _publish_outdated(clean: bool, runner: GitRunner) -> None:
    """Publish only modules with missing or outdated split branches."""
    # F2.9a: Gate mutating flows on release-authoritative source state
    # This must fire BEFORE the uncommitted changes prompt so the gate
    # error is clear and does not get masked by interactive prompts.
    _check_release_authoritative(runner)

    if not _confirm_uncommitted_changes(runner):
        return

    _maybe_clean_subtree_cache(clean)

    queue: list[str] = []
    for module_name in _list_modules():
        state, *_ = _get_module_publish_state(module_name, runner)
        if state in ("outdated", "unpublished"):
            queue.append(module_name)

    if not queue:
        _print_success("All module split branches are already up to date.")
        return

    _print_info(f"Publishing outdated modules: {' '.join(queue)}")
    print()

    for module_name in queue:
        _publish_module(module_name, expected_remote_sha="ABSENT", runner=runner)
        print()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish module changes to split branches (F2.8 provenance-aware wrapper)."
    )
    parser.add_argument(
        "module_name",
        nargs="?",
        help="Module name to publish (e.g. auth, billing)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show split-branch status for every module",
    )
    parser.add_argument(
        "--publish-outdated",
        action="store_true",
        help=(
            "[DISABLED in SA117 Phase 4] Previously published modules with "
            "missing or outdated split branches.  Now exits with safety "
            "guidance; use single-module publish instead."
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear git subtree cache before splitting",
    )
    parser.add_argument(
        "--expected-remote-sha",
        help=(
            "Exact 40-char hex SHA expected on remote, or ABSENT for first publish. "
            "Required for single-module publish; rejected with --publish-outdated and --status."
        ),
    )
    parser.add_argument(
        "--git-executable",
        help=(
            "Absolute Git executable for publication, or omit to resolve git "
            "from PATH (QUICKSCALE_GIT_EXECUTABLE is also supported)."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Validate repo root
    if not (_REPO_ROOT / "quickscale_modules").is_dir():
        _print_error(
            "quickscale_modules directory not found. Are you in the QuickScale repository root?"
        )
        sys.exit(1)

    # Bootstrap and validate the publication runner before the first Git
    # process.  In particular, a hostile PATH/config/repository environment
    # must not get an opportunity to influence the bootstrap probe itself.
    try:
        runner = build_publication_git_runner(args.git_executable)
    except GitError as e:
        _print_error(f"Publication Git bootstrap failed: {e}")
        sys.exit(1)

    if not is_git_repo(_REPO_ROOT, runner=runner):
        _print_error("Not a git repository")
        sys.exit(1)

    if args.status and args.clean:
        _print_error("--clean is only supported with publish actions")
        sys.exit(1)

    if args.status:
        if args.expected_remote_sha is not None:
            _print_error("--expected-remote-sha is not supported with --status")
            sys.exit(1)
        _show_status(runner)
    elif args.publish_outdated:
        _print_error("--publish-outdated is disabled in SA117 Phase 4")
        _print_info(
            "Batch --publish-outdated used bare --force, which violates the "
            "force-with-lease safety contract."
        )
        _print_info("Publish each module individually with --expected-remote-sha:")
        for name in _list_modules():
            _print_info(f"  make publish-module MODULE={name} EXPECTED_REMOTE_SHA=<40hex|ABSENT>")
        sys.exit(1)
    elif args.module_name:
        module_name = args.module_name

        # Phase 4: --expected-remote-sha is required for single-module publish
        expected_sha = args.expected_remote_sha
        if not expected_sha:
            _print_error(
                "--expected-remote-sha is required for single-module publish "
                "(use: --expected-remote-sha <40hex|ABSENT>)"
            )
            sys.exit(1)

        # Validate expected SHA format before any git operations
        try:
            validate_expected_sha(expected_sha)
        except GitError as e:
            _print_error(f"Invalid --expected-remote-sha: {e}")
            sys.exit(1)

        # Validate module name shape BEFORE any path resolution or subtree
        # operations so invalid input fails closed with a clean error instead
        # of an uncaught traceback (CR-M5-P1-001).
        try:
            validate_module_name(module_name)
        except GitError as e:
            _print_error(str(e))
            sys.exit(1)

        # Validate module exists
        module_dir = _REPO_ROOT / resolve_module_path(module_name)
        if not module_dir.is_dir():
            _print_error(f"Module '{module_name}' not found in quickscale_modules/")
            print()
            _print_info("Available modules:")
            for name in _list_modules():
                print(f"  - {name}")
            sys.exit(1)

        # First enforce the existing release-authoritative gate so callers get
        # the established diagnostic for an untagged/mismatched source.  The
        # origin check immediately follows and remains before any prompt,
        # subtree split, or other mutation.
        _check_release_authoritative(runner)

        # This is the final pre-mutation source gate.  It checks effective
        # fetch and push identity while allowing unrelated remotes, and fails
        # closed for blank, mixed, or untrusted origin configuration.
        try:
            validate_publication_origin(_REPO_ROOT, runner=runner)
        except GitError as e:
            _print_error(f"Publication origin validation failed: {e}")
            sys.exit(1)

        if not _confirm_uncommitted_changes(runner):
            return

        _maybe_clean_subtree_cache(args.clean)
        _publish_module(
            module_name,
            expected_remote_sha=expected_sha,
            runner=runner,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
