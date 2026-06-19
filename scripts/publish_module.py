#!/usr/bin/env python3
"""
Provenance-aware split-publish wrapper for QuickScale modules (F2.8, F2.9a).

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

Usage:
    poetry run python scripts/publish_module.py <module_name> [--clean]
    poetry run python scripts/publish_module.py --status
    poetry run python scripts/publish_module.py --publish-outdated [--clean]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
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
    is_git_repo,
    is_release_authoritative,
    push_split_branch,
    resolve_module_path,
    resolve_split_branch,
    run_git_subtree_split,
    validate_module_name,
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
    """Return sorted module names from quickscale_modules/."""
    modules_dir = _REPO_ROOT / "quickscale_modules"
    if not modules_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in modules_dir.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )


def _has_uncommitted_changes() -> bool:
    """Return True if the working directory has uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _warn_uncommitted_changes() -> None:
    if _has_uncommitted_changes():
        _print_warning(
            "You have uncommitted changes. "
            "Split status and published branches only include committed history."
        )


def _confirm_uncommitted_changes() -> bool:
    """
    Prompt the user when uncommitted changes are present.

    Returns True if the user wants to continue, False to abort.
    """
    if not _has_uncommitted_changes():
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


def _check_release_authoritative() -> None:
    """
    Gate: refuse mutating publish flows unless source is release-authoritative (F2.9a).

    Release-authoritative means the VERSION file matches a git tag pointing at
    HEAD, aligned with the publish workflow authority in
    .github/workflows/publish.yml.

    Raises SystemExit with a clear operator-facing message when the source is
    not release-authoritative.  This gate applies to mutating flows only
    (single-module publish and --publish-outdated); --status remains read-only
    and must not fail closed just because HEAD is untagged.
    """
    is_auth, version, tag, reason = is_release_authoritative(_REPO_ROOT)
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


def _get_local_split_sha(module_path: str) -> str | None:
    """Compute the subtree split SHA for *module_path* without creating a branch."""
    result = subprocess.run(
        ["git", "subtree", "split", f"--prefix={module_path}", "--ignore-joins"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    return sha if sha else None


def _get_published_split_ref(split_branch: str) -> tuple[str, str]:
    """
    Return ``(sha, source)`` for the published split branch.

    *source* is one of ``local-branch``, ``remote-tracking``, or ``none``.
    """
    # Check local branch first
    result = subprocess.run(
        ["git", "rev-parse", "--verify", split_branch],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sha = result.stdout.strip()
        if sha:
            return sha, "local-branch"

    # Check remote-tracking branch
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{split_branch}"],
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
) -> tuple[str, str, str, str]:
    """Return ``(state, local_sha, published_sha, published_source)``."""
    try:
        module_path = resolve_module_path(module_name)
        split_branch = resolve_split_branch(module_name)
    except GitError as e:
        _print_error(str(e))
        sys.exit(1)

    local_sha = _get_local_split_sha(module_path)
    if local_sha is None:
        _print_error(f"Could not compute subtree split for module '{module_name}'")
        sys.exit(1)

    published_sha, published_source = _get_published_split_ref(split_branch)

    if not published_sha:
        return "unpublished", local_sha, "", published_source
    if local_sha == published_sha:
        return "up-to-date", local_sha, published_sha, published_source
    return "outdated", local_sha, published_sha, published_source


def _publish_module(module_name: str) -> None:
    """Split and push a single module using the provenance-aware helpers."""
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
        push_split_branch(split_branch, remote="origin", force=True, path=_REPO_ROOT)
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


def _show_status() -> None:
    """Show split-branch status for every module."""
    _warn_uncommitted_changes()
    _print_info("Inspecting module publish status...")
    print()

    outdated: list[str] = []
    unpublished: list[str] = []

    for module_name in _list_modules():
        state, _local_sha, _pub_sha, pub_source = _get_module_publish_state(module_name)
        if state == "up-to-date":
            print(f"  {module_name:<16} up to date ({pub_source})")
        elif state == "outdated":
            print(f"  {module_name:<16} outdated ({pub_source})")
            outdated.append(module_name)
        elif state == "unpublished":
            print(f"  {module_name:<16} unpublished")
            unpublished.append(module_name)

    print()
    if not outdated and not unpublished:
        _print_success("All module split branches are up to date.")
        return

    if outdated:
        _print_warning(f"Outdated modules: {' '.join(outdated)}")
    if unpublished:
        _print_warning(f"Unpublished modules: {' '.join(unpublished)}")


def _publish_outdated(clean: bool) -> None:
    """Publish only modules with missing or outdated split branches."""
    # F2.9a: Gate mutating flows on release-authoritative source state
    # This must fire BEFORE the uncommitted changes prompt so the gate
    # error is clear and does not get masked by interactive prompts.
    _check_release_authoritative()

    if not _confirm_uncommitted_changes():
        return

    _maybe_clean_subtree_cache(clean)

    queue: list[str] = []
    for module_name in _list_modules():
        state, *_ = _get_module_publish_state(module_name)
        if state in ("outdated", "unpublished"):
            queue.append(module_name)

    if not queue:
        _print_success("All module split branches are already up to date.")
        return

    _print_info(f"Publishing outdated modules: {' '.join(queue)}")
    print()

    for module_name in queue:
        _publish_module(module_name)
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
        help="Publish only modules with missing or outdated split branches",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear git subtree cache before splitting",
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

    if not is_git_repo(_REPO_ROOT):
        _print_error("Not a git repository")
        sys.exit(1)

    if args.status and args.clean:
        _print_error("--clean is only supported with publish actions")
        sys.exit(1)

    if args.status:
        _show_status()
    elif args.publish_outdated:
        _publish_outdated(clean=args.clean)
    elif args.module_name:
        module_name = args.module_name
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

        # F2.9a: Gate mutating flows on release-authoritative source state
        # This must fire BEFORE the uncommitted changes prompt so the gate
        # error is clear and does not get masked by interactive prompts.
        _check_release_authoritative()

        if not _confirm_uncommitted_changes():
            return

        _maybe_clean_subtree_cache(args.clean)
        _publish_module(module_name)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
