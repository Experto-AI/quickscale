"""Beta migration command-line entry points."""

from .execution import run_beta_migration
from .model import (
    BetaMigrationInput,
    _append_blocker,
    _append_check,
    _append_completed_step,
)
from .planning import _build_pending_manual_actions
import argparse
import sys
from ..report_rendering import (
    render_report_json,
    render_report_summary,
    write_report_file,
)
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO


def _add_common_arguments(subparser: argparse.ArgumentParser) -> None:
    """Add the donor/recipient inputs shared by every workflow mode."""
    subparser.add_argument(
        "--donor",
        required=True,
        help="Absolute path to the donor project",
    )
    subparser.add_argument(
        "--recipient",
        required=True,
        help="Absolute path to the recipient project",
    )
    subparser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit the planned actions only without mutating files or running verification",
    )
    subparser.add_argument(
        "--report-path",
        help="Optional path where the JSON report should be written",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the beta migration argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the maintainer-only fresh-first beta-site migration workflow. The "
            "workflow can execute deterministically through local verification."
        )
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    fresh_first = subparsers.add_parser(
        "fresh-first",
        help=(
            "Run the fresh-first workflow: donor is the current beta site and recipient "
            "is a fresh scaffold."
        ),
    )
    _add_common_arguments(fresh_first)

    iterate = subparsers.add_parser(
        "iterate",
        help=(
            "Run one migration iteration: regenerate the throwaway recipient from the "
            "donor's quickscale.yml, then run the fresh-first workflow."
        ),
    )
    _add_common_arguments(iterate)

    return parser


def parse_cli_args(argv: Sequence[str] | None = None) -> BetaMigrationInput:
    """Parse CLI arguments into a normalized input object."""
    parser = build_argument_parser()
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    return BetaMigrationInput(
        mode=parsed.mode,
        donor=Path(parsed.donor),
        recipient=Path(parsed.recipient),
        dry_run=parsed.dry_run,
        report_path=Path(parsed.report_path) if parsed.report_path else None,
    )


def run_beta_migration_cli(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
) -> int:
    """Execute the beta migration CLI."""
    output_stream = stdout if stdout is not None else sys.stdout
    inputs = parse_cli_args(argv)
    report = run_beta_migration(inputs)

    if inputs.report_path is not None:
        try:
            written_path = write_report_file(report, inputs.report_path)
        except OSError as exc:
            detail = f"Failed to write report to {inputs.report_path}: {exc}"
            _append_check(
                report, name="write-report-file", status="failed", detail=detail
            )
            _append_blocker(report, detail)
            report.status = "blocked"
            report.pending_manual_actions = _build_pending_manual_actions(report)
        else:
            _append_completed_step(
                report,
                step="write-report-file",
                detail=f"Wrote JSON report to {written_path}",
            )

    _append_completed_step(
        report,
        step="emit-stdout-report",
        detail="Rendered the readable summary and structured JSON report to stdout.",
    )

    output_stream.write(render_report_summary(report))
    output_stream.write("\n\n")
    output_stream.write(render_report_json(report))
    output_stream.write("\n")

    return 1 if report.status == "blocked" else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the beta migration maintainer workflow as a script entrypoint."""
    return run_beta_migration_cli(argv)
