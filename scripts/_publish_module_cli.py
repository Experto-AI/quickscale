"""
CLI parsing and validation for the ``publish_module`` facade.

The action/option matrix is validated before repository-root checks, inventory
enumeration, or Git-runner bootstrap, so invalid combinations never reach a
mutating path.  The private siblings resolve output and git collaborators
through their defining modules at call time (decisions.md, Split-Facade
Seams).
"""

from __future__ import annotations

import argparse
import sys

import _publish_module_core as _core
import _publish_module_git as _git
from _publish_module_git import GitError


def _report_publish_outdated_disabled() -> None:
    """Emit the stable Phase 4 diagnostic without bootstrapping Git."""
    _core._print_error("--publish-outdated is disabled in SA117 Phase 4")
    _core._print_info(
        "Batch --publish-outdated used bare --force, which violates the "
        "force-with-lease safety contract."
    )
    _core._print_info("Run --status to distinguish outdated branches from blocked branches.")
    _core._print_info("Publish an outdated branch with its observed --expected-remote-sha.")
    _core._print_info("Restore a confirmed absent branch through maintainer recovery.")
    sys.exit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish module changes to split branches (F2.8 provenance-aware wrapper)."
    )
    parser.add_argument(
        "module_name",
        nargs="?",
        help="Module name to publish (e.g. auth, billing)",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--status",
        action="store_true",
        help="Show split-branch and seal status for every module",
    )
    actions.add_argument(
        "--seal",
        action="store_true",
        help="Seal one module's split branch at VERSION",
    )
    actions.add_argument(
        "--seal-all",
        action="store_true",
        help="Seal every authoritative module serially at VERSION",
    )
    actions.add_argument(
        "--publish-all",
        action="store_true",
        help=(
            "Publish every outdated module serially, each against its own "
            "freshly observed remote SHA (force-with-lease)"
        ),
    )
    parser.add_argument(
        "--publish-outdated",
        action="store_true",
        help=(
            "[DISABLED in SA117 Phase 4] Previously targeted missing or outdated "
            "split branches. Now exits with safety guidance: publish only an "
            "outdated observed branch; recover an absent branch."
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear git subtree cache before splitting (publish only)",
    )
    parser.add_argument(
        "--version",
        metavar="VERSION",
        help="Release version for seal actions, or an explicit status version",
    )
    parser.add_argument(
        "--previous-version",
        metavar="VERSION",
        help="Optional prior release version for seal actions",
    )
    parser.add_argument(
        "--expected-remote-sha",
        help=(
            "Freshly observed exact 40-hex SHA expected on remote. "
            "Required for single-module publish; rejected with --status."
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


def _validate_status_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.module_name is not None:
        parser.error("--status does not accept a module name")
    if args.clean:
        parser.error("--clean is only supported with publish actions")
    if args.expected_remote_sha is not None:
        parser.error("--expected-remote-sha is not supported with --status")
    if args.previous_version is not None:
        parser.error("--previous-version is only supported with --seal or --seal-all")


def _validate_seal_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.module_name is None:
        parser.error("--seal requires a module name")
    if args.version is None:
        parser.error("--seal requires --version VERSION")
    if args.clean:
        parser.error("--clean is only supported with publish actions")
    if args.expected_remote_sha is not None:
        parser.error("--expected-remote-sha is not supported with --seal")


def _validate_seal_all_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.module_name is not None:
        parser.error("--seal-all does not accept a module name")
    if args.version is None:
        parser.error("--seal-all requires --version VERSION")
    if args.clean:
        parser.error("--clean is only supported with publish actions")
    if args.expected_remote_sha is not None:
        parser.error("--expected-remote-sha is not supported with --seal-all")


def _validate_publish_all_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.module_name is not None:
        parser.error("--publish-all does not accept a module name")
    if args.expected_remote_sha is not None:
        parser.error("--expected-remote-sha is not supported with --publish-all")
    if args.version is not None:
        parser.error("--version is not supported with --publish-all")
    if args.previous_version is not None:
        parser.error("--previous-version is only supported with --seal or --seal-all")


def _validate_single_publish_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    if args.module_name is None and (args.clean or args.expected_remote_sha is not None):
        parser.error("publish options require a module name")
    if args.previous_version is not None:
        parser.error("--previous-version is only supported with --seal or --seal-all")
    if args.version is not None:
        parser.error("--version is only supported with --seal, --seal-all, or --status")

    if args.module_name is None:
        return
    if args.expected_remote_sha is None:
        _core._print_error(
            "--expected-remote-sha is required for single-module publish "
            "(use a freshly observed exact 40-hex remote SHA)"
        )
        sys.exit(1)
    try:
        _git.validate_expected_sha(args.expected_remote_sha)
    except GitError as exc:
        _core._print_error(f"Invalid --expected-remote-sha: {exc}")
        sys.exit(1)


def _validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Reject action/argument combinations before Git bootstrap or mutation."""
    # Keep this precedence ahead of every other action/option check.  The
    # disabled action is intentionally parseable with otherwise conflicting
    # options so operators always receive the Phase 4 safety contract before
    # repository, inventory, or Git-runner bootstrap work begins.
    if args.publish_outdated:
        return

    if args.status:
        _validate_status_args(parser, args)
        return

    if args.seal:
        _validate_seal_args(parser, args)
        return

    if args.seal_all:
        _validate_seal_all_args(parser, args)
        return

    if args.publish_all:
        _validate_publish_all_args(parser, args)
        return

    _validate_single_publish_args(parser, args)
