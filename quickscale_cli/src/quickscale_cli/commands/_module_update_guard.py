"""Local-edit guard and reporting for the module update flow.

Implementation detail of :mod:`quickscale_cli.commands._module_update`; this
sibling owns the pre-pull comparison report, the operator guidance, and the
``--allow-local-changes`` option that authorizes proceeding past it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

import quickscale_cli.utils.module_provenance as _module_provenance

allow_local_changes_option = click.option(
    "--allow-local-changes",
    is_flag=True,
    help=(
        "Proceed when embedded module files were edited locally or cannot be "
        "verified; the subtree pull can overwrite them."
    ),
)


def _collect_module_content_drift(
    state: Any,
    project_path: Path,
) -> list[_module_provenance.ModuleContentDrift]:
    """Compare each installed module with the tree at its recorded commit."""
    return [
        _module_provenance.detect_module_content_drift(
            project_path,
            name,
            module_state.commit_sha,
        )
        for name, module_state in sorted(state.modules.items())
    ]


def _report_unverifiable_module_content_drift(
    drifts: list[_module_provenance.ModuleContentDrift],
    *,
    allow_local_changes: bool,
) -> None:
    """Report modules whose recorded tree cannot be read for comparison."""
    unverifiable = [drift for drift in drifts if not drift.verifiable]
    if not unverifiable:
        return

    if allow_local_changes:
        click.secho(
            "\n⚠️  Cannot verify embedded module(s) against their recorded commit; "
            "continuing because --allow-local-changes was passed:",
            fg="yellow",
            err=True,
        )
    else:
        click.secho(
            "\n❌ Cannot verify embedded module(s) against their recorded commit:",
            fg="red",
            bold=True,
            err=True,
        )
    for drift in unverifiable:
        click.echo(f"  • {drift.module}: {drift.unverifiable_reason}", err=True)


def _report_module_content_changes(
    drifts: list[_module_provenance.ModuleContentDrift],
    *,
    allow_local_changes: bool,
) -> None:
    """Print the changed paths, either as a refusal or as an override warning."""
    changed = [drift for drift in drifts if drift.has_changes]
    if not changed:
        return

    if allow_local_changes:
        click.secho(
            "\n⚠️  Embedded module edits may be overwritten because "
            "--allow-local-changes was passed:",
            fg="yellow",
            err=True,
        )
    else:
        click.secho(
            "\n❌ Local changes detected in embedded module(s):",
            fg="red",
            bold=True,
            err=True,
        )
    for drift in changed:
        click.echo(f"  • {drift.module}:", err=True)
        for path in drift.changed_paths:
            click.echo(f"    - {path}", err=True)


def _enforce_no_local_module_changes(
    state: Any,
    project_path: Path,
    *,
    allow_local_changes: bool,
) -> None:
    """Refuse the update when an embedded module differs or cannot be checked.

    A comparison that cannot be established is refused for the same reason as
    a detected edit: the update must not replace a tree whose local content is
    unknown.  ``--allow-local-changes`` is the explicit authorization to
    proceed in either case.
    """
    drifts = _collect_module_content_drift(state, project_path)
    blocked = any(drift.has_changes or not drift.verifiable for drift in drifts)
    if not blocked:
        return

    _report_module_content_changes(drifts, allow_local_changes=allow_local_changes)
    _report_unverifiable_module_content_drift(
        drifts, allow_local_changes=allow_local_changes
    )
    if not allow_local_changes:
        click.echo(
            "💡 Restore the recorded module content (revert the edit) before a "
            "normal update, or pass --allow-local-changes to proceed. A change "
            "you want to keep must be published upstream and brought in by an "
            "allowed update, since upstreaming alone does not move the recorded "
            "baseline.",
            err=True,
        )
        raise click.Abort()
