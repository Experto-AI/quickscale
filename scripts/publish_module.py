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

The implementation lives in private ``_publish_module_*`` siblings (SA267):
``_publish_module_core`` (root, output, inventory, version checks),
``_publish_module_git`` (runner bindings, seal SHA/ref helpers, working-tree
checks), ``_publish_module_seal`` (the seal state machine),
``_publish_module_publish`` (publish and release-gate flows),
``_publish_module_status`` (read-only status diagnostics), and
``_publish_module_cli`` (parser and argument validation).  This module owns
the CLI dispatch and re-exports the pre-split surface for unchanged import
paths, so a test's seam is the sibling that defines the name
(decisions.md, Split-Facade Seams).

    Usage:
        poetry run python scripts/publish_module.py \\
            <module_name> --expected-remote-sha <40-hex-remote-sha> [--clean]
        poetry run python scripts/publish_module.py --seal <module_name> \
            --version <version> [--previous-version <version>]
        poetry run python scripts/publish_module.py --seal-all \
            --version <version> [--previous-version <version>]
        poetry run python scripts/publish_module.py --publish-all [--clean]
        poetry run python scripts/publish_module.py --status [--version <version>]
        poetry run python scripts/publish_module.py --publish-outdated [--clean]

    Phase 4 (SA117): All mutating single-module publish calls require
    ``--expected-remote-sha``.  The value must be a freshly observed
    exact 40-hex SHA.  ``--status`` rejects the flag; the disabled
    ``--publish-outdated`` action accepts it only long enough to emit its
    Phase 4 safety guidance.

    Phase 4 also disables ``--publish-outdated`` entirely: it used bare
    ``--force`` internally, which violates the force-with-lease safety
    contract.  For an existing branch, use ``--publish-all`` (fresh per-module
    lease) or single-module publish with ``--expected-remote-sha``.  A confirmed
    absent branch requires maintainer recovery instead of publication.
"""

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import argparse as argparse
import inspect as inspect
import re as re
import shutil as shutil
import sys
from dataclasses import dataclass as dataclass
from pathlib import Path

# Ensure the private siblings and quickscale_core are importable whether this
# file is executed directly (``sys.path[0]`` is ``scripts/``) or imported with
# only the repository root on ``sys.path`` (``scripts.publish_module`` and the
# E2E lanes).
_SCRIPTS_DIR = Path(__file__).resolve().parent
_CORE_SRC = _SCRIPTS_DIR.parent / "quickscale_core" / "src"
for _import_root in (_CORE_SRC, _SCRIPTS_DIR):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))
del _import_root

import _publish_module_core as _core
from _publish_module_cli import (
    _build_parser,
    _report_publish_outdated_disabled,
    _validate_cli_args,
)
from _publish_module_core import (
    _REPO_ROOT,
    BLUE,
    GREEN,
    NC,
    RED,
    YELLOW,
    _list_modules,
    _print_error,
    _print_info,
    _print_success,
    _print_warning,
    _read_repository_version,
    _require_authoritative_module,
    _validate_seal_version,
)
from _publish_module_git import (
    _SEAL_SHA_RE,
    GitError,
    GitRunner,
    RemoteBranchAbsentError,
    SealError,
    _confirm_uncommitted_changes,
    _get_local_split_sha,
    _has_uncommitted_changes,
    _maybe_clean_subtree_cache,
    _observe_remote_branch_sha,
    _parse_remote_records,
    _seal_error,
    _seal_sha,
    _warn_uncommitted_changes,
    build_publication_git_runner,
    create_annotated_tag,
    delete_local_tag,
    get_local_tag_commit,
    get_tree_sha,
    is_git_repo,
    push_tag,
    resolve_remote_ref,
    validate_module_name,
)
from _publish_module_git import is_release_authoritative as is_release_authoritative
from _publish_module_git import is_working_directory_clean as is_working_directory_clean
from _publish_module_git import push_split_branch as push_split_branch
from _publish_module_git import resolve_module_path as resolve_module_path
from _publish_module_git import resolve_split_branch as resolve_split_branch
from _publish_module_git import resolve_split_tag as resolve_split_tag
from _publish_module_git import run_git_subtree_split as run_git_subtree_split
from _publish_module_git import validate_expected_sha as validate_expected_sha
from _publish_module_git import (
    validate_publication_local_config as validate_publication_local_config,
)
from _publish_module_git import validate_publication_origin as validate_publication_origin
from _publish_module_git import validate_tag_name as validate_tag_name
from _publish_module_publish import (
    _check_release_authoritative,
    _head_tree,
    _publish_all,
    _publish_module,
    _require_fast_forward,
    _run_release_gates,
)
from _publish_module_seal import (
    SealBatchOutcome,
    SealOutcome,
    SealResult,
    _cleanup_created_tag,
    _invoke_seal_module,
    _print_seal_batch_summary,
    _seal_all,
    _seal_module,
)
from _publish_module_status import (
    _get_module_publish_state,
    _get_module_seal_state,
    _show_provenance_diagnostics,
    _show_status,
)

#: Every name the facade re-exports.  Per decisions.md § Split-Facade Seams a
#: facade re-exports public names only: incidental imported bindings
#: (``argparse``, ``Path``, ``GitError``, ...) stay module attributes but are
#: deliberately not part of the wildcard surface.
__all__ = [
    "BLUE",
    "GREEN",
    "NC",
    "RED",
    "YELLOW",
    "RemoteBranchAbsentError",
    "SealBatchOutcome",
    "SealError",
    "SealOutcome",
    "SealResult",
    "_CORE_SRC",
    "_REPO_ROOT",
    "_SEAL_SHA_RE",
    "_build_parser",
    "_check_release_authoritative",
    "_cleanup_created_tag",
    "_confirm_uncommitted_changes",
    "_get_local_split_sha",
    "_get_module_publish_state",
    "_get_module_seal_state",
    "_has_uncommitted_changes",
    "_head_tree",
    "_invoke_seal_module",
    "_list_modules",
    "_maybe_clean_subtree_cache",
    "_observe_remote_branch_sha",
    "_parse_remote_records",
    "_print_error",
    "_print_info",
    "_print_seal_batch_summary",
    "_print_success",
    "_print_warning",
    "_publish_all",
    "_publish_module",
    "_read_repository_version",
    "_report_publish_outdated_disabled",
    "_require_authoritative_module",
    "_require_fast_forward",
    "_run_release_gates",
    "_seal_all",
    "_seal_error",
    "_seal_module",
    "_seal_sha",
    "_show_provenance_diagnostics",
    "_show_status",
    "_validate_cli_args",
    "_validate_seal_version",
    "_warn_uncommitted_changes",
    "create_annotated_tag",
    "delete_local_tag",
    "get_local_tag_commit",
    "get_tree_sha",
    "main",
    "push_tag",
    "resolve_remote_ref",
]

# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _bootstrap_runner(args: argparse.Namespace) -> GitRunner:
    """
    Bootstrap and validate the publication runner before the first Git process.

    In particular, a hostile PATH/config/repository environment must not get
    an opportunity to influence the bootstrap probe itself.
    """
    try:
        runner = build_publication_git_runner(args.git_executable)
    except GitError as e:
        _print_error(f"Publication Git bootstrap failed: {e}")
        sys.exit(1)

    if not is_git_repo(_core._REPO_ROOT, runner=runner):
        _print_error("Not a git repository")
        sys.exit(1)
    return runner


def _run_status_action(runner: GitRunner, args: argparse.Namespace) -> None:
    _show_status(runner, version=args.version)


def _run_seal_action(runner: GitRunner, args: argparse.Namespace) -> None:
    module_name = args.module_name
    assert module_name is not None
    assert args.version is not None
    _validate_seal_version(args.version)
    try:
        validate_module_name(module_name)
    except GitError as exc:
        _print_error(str(exc))
        sys.exit(1)
    _require_authoritative_module(module_name)
    _run_release_gates(runner)
    if not _confirm_uncommitted_changes(runner):
        return
    try:
        _invoke_seal_module(
            module_name,
            args.version,
            previous_version=args.previous_version,
            runner=runner,
        )
    except GitError as exc:
        _print_error(f"Failed to seal module '{module_name}': {exc}")
        sys.exit(1)
    _print_success(f"Module '{module_name}' sealed at {args.version}")


def _run_seal_all_action(runner: GitRunner, args: argparse.Namespace) -> None:
    assert args.version is not None
    _validate_seal_version(args.version)
    # Freeze the authoritative inventory before any gate, prompt, or seal
    # operation.  The same set is used by the final read-only proof.
    frozen_modules = list(_list_modules())
    _run_release_gates(runner)
    if not _confirm_uncommitted_changes(runner):
        return
    try:
        _seal_all(
            args.version,
            previous_version=args.previous_version,
            runner=runner,
            modules=frozen_modules,
        )
    except (GitError, SystemExit) as exc:
        if isinstance(exc, SystemExit):
            raise
        _print_error(str(exc))
        sys.exit(1)
    if not _show_status(runner, version=args.version, modules=frozen_modules):
        _print_error("Seal-all verification did not produce a sealed status for every module")
        sys.exit(1)


def _run_publish_all_action(runner: GitRunner, args: argparse.Namespace) -> None:
    frozen_modules = list(_list_modules())
    _run_release_gates(runner)
    if not _confirm_uncommitted_changes(runner):
        return
    _maybe_clean_subtree_cache(args.clean)
    _publish_all(runner, modules=frozen_modules)
    print()
    _show_status(runner, modules=frozen_modules)


def _run_single_publish_action(runner: GitRunner, args: argparse.Namespace) -> None:
    module_name = args.module_name
    assert module_name is not None

    # Phase 4: --expected-remote-sha was validated before runner bootstrap.
    expected_sha = args.expected_remote_sha
    assert expected_sha is not None

    # Validate module name shape BEFORE any path resolution or subtree
    # operations so invalid input fails closed with a clean error instead
    # of an uncaught traceback (CR-M5-P1-001).
    try:
        validate_module_name(module_name)
    except GitError as e:
        _print_error(str(e))
        sys.exit(1)

    # F-002: reject any direct selection absent from the authoritative
    # shipped-module inventory before the release-authority gate, origin
    # validation, prompts, subtree split, or push.  An unapproved
    # inventory addition (count drift) fails closed here, before any
    # outward or mutating path.  This supersedes the previous on-disk
    # directory-existence check: the authoritative inventory is the
    # single source of truth for what a direct selector may publish.
    _require_authoritative_module(module_name)

    # Release authority, effective origin identity, and repository-local
    # publication credentials/identity are all required before the prompt,
    # subtree split, or any other mutation.
    _run_release_gates(runner)

    if not _confirm_uncommitted_changes(runner):
        return

    _maybe_clean_subtree_cache(args.clean)
    _publish_module(
        module_name,
        expected_remote_sha=expected_sha,
        runner=runner,
    )


def _dispatch_action(
    parser: argparse.ArgumentParser,
    runner: GitRunner,
    args: argparse.Namespace,
) -> None:
    if args.status:
        _run_status_action(runner, args)
    elif args.seal:
        _run_seal_action(runner, args)
    elif args.seal_all:
        _run_seal_all_action(runner, args)
    elif args.publish_all:
        _run_publish_all_action(runner, args)
    elif args.module_name:
        _run_single_publish_action(runner, args)
    else:
        parser.print_help()
        sys.exit(1)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _validate_cli_args(parser, args)

    # This branch is deliberately before repository-root checks, inventory
    # enumeration, and publication-runner bootstrap.  _validate_cli_args()
    # gives it precedence over every option that can be paired with the
    # disabled action.
    if args.publish_outdated:
        _report_publish_outdated_disabled()

    # Validate repo root
    if not (_core._REPO_ROOT / "quickscale_modules").is_dir():
        _print_error(
            "quickscale_modules directory not found. Are you in the QuickScale repository root?"
        )
        sys.exit(1)

    runner = _bootstrap_runner(args)
    _dispatch_action(parser, runner, args)


if __name__ == "__main__":
    main()
