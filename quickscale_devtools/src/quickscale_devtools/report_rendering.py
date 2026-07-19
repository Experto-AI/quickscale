"""Human-readable beta migration report rendering."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .beta_migration import (
        BetaMigrationReport,
        DiffSummary,
        PendingManualAction,
        VerificationCommandResult,
    )


def _json_ready(value: object) -> object:
    """Convert nested dataclasses and paths into JSON-ready primitives."""
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {
            field.name: _json_ready(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _render_diff_summary(diff: DiffSummary | None) -> str:
    """Render one ordered donor/recipient diff summary."""
    if diff is None:
        return "unavailable"
    return (
        f"donor-only={diff.donor_only or ['(none)']}, "
        f"recipient-only={diff.recipient_only or ['(none)']}"
    )


def _verification_counts(
    results: list[VerificationCommandResult],
) -> tuple[int, int]:
    """Count passed and failed verification results."""
    return (
        sum(result.status == "passed" for result in results),
        sum(result.status == "failed" for result in results),
    )


def _append_report_detail_lines(
    lines: list[str],
    *,
    blockers: list[str],
    verification_results: list[VerificationCommandResult],
    pending_actions: list[PendingManualAction],
    changed_files: list[str],
) -> None:
    """Append the detail sections in their established output order."""
    if blockers:
        lines.extend(f"Blocker: {blocker}" for blocker in blockers)

    for result in verification_results:
        if result.status == "failed":
            lines.append(
                f"Verification failure: {result.command} (cwd={result.cwd}, return_code={result.return_code})"
            )

    if pending_actions:
        for action in pending_actions:
            lines.append(f"Pending: {action.action} — {action.detail}")

    if changed_files:
        lines.append(
            f"Mutation summary: Updated {len(changed_files)} recipient paths during this run."
        )
    else:
        lines.append(
            "Mutation summary: No donor or recipient project files were modified."
        )


def render_report_summary(report: BetaMigrationReport) -> str:
    """Render the stable readable summary for stdout."""
    verification_passed, verification_failed = _verification_counts(
        report.verification_results
    )

    lines = [
        "Beta migration summary",
        f"Mode: {report.mode}",
        f"Status: {report.status}",
        f"Phase: {report.phase}",
        f"Dry run: {'yes' if report.dry_run else 'no'}",
        f"Donor: {report.donor_path}",
        f"Recipient: {report.recipient_path}",
        f"Identity reconciliation: {'required' if report.identity_reconciliation_required else 'not required'}",
        f"Module diff: {_render_diff_summary(report.module_diff)}",
        f"Path dependency diff: {_render_diff_summary(report.path_dependency_diff)}",
        f"Planned actions: {len(report.planned_actions)}",
        f"Changed files: {len(report.changed_files)}",
        f"Verification results: {verification_passed} passed, {verification_failed} failed",
        f"Pending manual actions: {len(report.pending_manual_actions)}",
        f"Blockers: {len(report.blockers)}",
    ]

    if report.written_report_path:
        lines.append(f"Report file: {report.written_report_path}")

    _append_report_detail_lines(
        lines,
        blockers=report.blockers,
        verification_results=report.verification_results,
        pending_actions=report.pending_manual_actions,
        changed_files=report.changed_files,
    )
    return "\n".join(lines)


def render_report_json(report: BetaMigrationReport) -> str:
    """Render a JSON report for stdout or file output."""
    return json.dumps(_json_ready(report), indent=2)


def write_report_file(report: BetaMigrationReport, report_path: Path) -> Path:
    """Write a JSON report to disk and return the resolved path."""
    resolved_path = (
        report_path.resolve()
        if report_path.is_absolute()
        else (Path.cwd() / report_path).resolve()
    )
    report.written_report_path = str(resolved_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(render_report_json(report) + "\n")
    return resolved_path
