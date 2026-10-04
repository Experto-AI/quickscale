"""Render the recipient-side beta migration handoff prompt."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .beta_migration import BetaMigrationReport, DiffSummary, PendingManualAction

HANDOFF_PROMPT_FILENAME = "MIGRATION_PROMPT.md"

HARD_CONSTRAINTS: tuple[str, ...] = (
    "Keep the donor project read-only; every change lands in the recipient.",
    "Never copy `.git`, `media/`, `.env`, or `poetry.lock` between the two trees.",
    "Do not hand-patch QuickScale-managed files such as `settings/modules.py`, "
    "`urls_modules.py`, and the generated wiring; regenerate them through the supported "
    "QuickScale workflow.",
    "In-place edits under vendored module source (`modules/<name>/`) are outside the "
    "extension contract: upstream them into the module or re-express them as project-owned "
    "code before the recipient is handed over.",
    "The migration merged the donor's declared frontend dependencies and reported every "
    "version conflict; keep the recipient's declared versions and add no dependency it "
    "does not already declare.",
)

DONE_CRITERIA: tuple[str, ...] = (
    "The recipient's `pytest` suite and frontend `pnpm test` suite pass.",
    "Local smoke checks pass for the home page, Django admin, custom routes, and any "
    "installed public module pages.",
    "Every remaining item above is completed and recorded in the migration ledger.",
    "The verified recipient is committed in the real repository and merged through review, "
    "with the deploy confirming migrations.",
)


def _relative_existing_path(path_value: str, recipient_root: Path) -> str | None:
    """Return the recipient-relative form of a recorded path, or None when it is gone."""
    if not path_value:
        return None
    candidate = Path(path_value)
    try:
        relative = candidate.relative_to(recipient_root)
    except ValueError:
        return None
    if not candidate.exists():
        return None
    return relative.as_posix() or "."


def _write_text_atomically(path: Path, content: str) -> None:
    """Write a recipient file through a fresh temporary file and an atomic replace.

    Exclusive creation and replacement by directory entry mean the write can
    neither follow an existing symlink nor share an inode with a file outside
    the recipient.
    """
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _render_bullet_lines(items: list[str]) -> list[str]:
    """Render one bullet list, marking an empty list explicitly."""
    return [f"- {item}" for item in items] if items else ["- (none)"]


def _render_diff_summary(diff: DiffSummary | None) -> str:
    """Render one donor/recipient diff summary in the report's format."""
    if diff is None:
        return "unavailable"
    return (
        f"donor-only={diff.donor_only or ['(none)']}, "
        f"recipient-only={diff.recipient_only or ['(none)']}"
    )


def _render_remaining_action(action: PendingManualAction) -> list[str]:
    """Render one remaining manual action with its paths and governing rule."""
    paths = (
        ", ".join(f"`{path}`" for path in action.paths) if action.paths else "(none)"
    )
    lines = [f"- [ ] `{action.action}` — {action.detail}", f"      Paths: {paths}"]
    if action.rule:
        lines.append(f"      Rule: {action.rule}")
    return lines


def render_handoff_prompt(report: BetaMigrationReport) -> str:
    """Render the handoff prompt document for a completed fresh-first run."""
    if report.recipient is None:
        raise ValueError(
            "A recipient snapshot is required to render the beta migration handoff prompt."
        )
    recipient_root = report.recipient.path

    lines: list[str] = [
        "# Beta migration handoff prompt",
        "",
        "This recipient was produced by the fresh-first beta migration "
        "(`make beta-migrate-fresh`);",
        "the deterministic file migration and local verification already ran. Complete the "
        "remaining",
        "work below, then hand the recipient back to the maintainer.",
        "",
        f"- Mode: {report.mode}",
        f"- Phase: {report.phase}",
        f"- Donor: {report.donor_path}",
        "- Identity reconciliation: "
        + ("performed" if report.identity_reconciliation_required else "not required"),
    ]

    if report.runtime_provenance is not None:
        provenance = report.runtime_provenance
        lines.append(
            "- Runtime provenance: "
            f"settings/production.py={provenance.settings_production}, "
            f"start.sh={provenance.start_sh}, "
            f"Dockerfile={provenance.dockerfile}"
        )

    passed = sum(result.status == "passed" for result in report.verification_results)
    failed = sum(result.status == "failed" for result in report.verification_results)
    lines.append(f"- Verification: {passed} passed, {failed} failed")

    lines += ["", "## What was migrated", "", "Steps completed:"]
    lines += _render_bullet_lines([step.step for step in report.completed_steps])

    changed_paths = sorted(
        {
            relative
            for relative in (
                _relative_existing_path(path_value, recipient_root)
                for path_value in report.changed_files
            )
            if relative is not None
        }
    )
    lines += ["", f"Recipient paths changed ({len(changed_paths)}):"]
    lines += _render_bullet_lines([f"`{path}`" for path in changed_paths])

    lines += ["", "Diff summary:"]
    lines.append(f"- Module diff: {_render_diff_summary(report.module_diff)}")
    lines.append(
        f"- Path dependency diff: {_render_diff_summary(report.path_dependency_diff)}"
    )
    if report.frontend_dependency_merge is None:
        lines.append("- Frontend dependency merge: unavailable")
    else:
        merge = report.frontend_dependency_merge
        lines.append(
            "- Frontend dependency merge: "
            f"donor-only={merge.donor_only or ['(none)']}, "
            f"version conflicts={merge.conflicts or ['(none)']}"
        )

    if report.verification_results:
        lines += ["", "Verification commands:"]
        lines += _render_bullet_lines(
            [
                f"`{result.command}` — {result.status}"
                for result in report.verification_results
            ]
        )

    lines += ["", "## Remaining work", ""]
    if report.pending_manual_actions:
        for action in report.pending_manual_actions:
            lines += _render_remaining_action(action)
    else:
        lines.append("- (none)")

    lines += ["", "## Hard constraints", ""]
    lines += _render_bullet_lines(list(HARD_CONSTRAINTS))
    lines += ["", "## Done criteria", ""]
    lines += _render_bullet_lines(list(DONE_CRITERIA))

    return "\n".join(lines) + "\n"


def write_handoff_prompt(report: BetaMigrationReport) -> Path:
    """Write the rendered handoff prompt into the recipient and return its path.

    The document deliberately never renders the report's mutable ``status``:
    it attests the deterministic execution and verification that produced the
    recipient, so a later CLI failure can never make an existing prompt claim
    a readiness that no longer holds.
    """
    if report.recipient is None:
        raise ValueError(
            "A recipient snapshot is required to render the beta migration handoff prompt."
        )
    prompt_path = report.recipient.path / HANDOFF_PROMPT_FILENAME
    _write_text_atomically(prompt_path, render_handoff_prompt(report))
    return prompt_path
