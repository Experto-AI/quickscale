"""Local-edit guard and reporting for the module update flow.

Implementation detail of :mod:`quickscale_cli.commands._module_update`; this
sibling owns the pre-pull comparison report, the operator guidance, and the
``--allow-local-changes`` option that authorizes proceeding past it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

import quickscale_core.apply as _apply
import quickscale_core.schema.config_schema as _config_schema
import quickscale_cli.commands.module_output as _module_output
import quickscale_cli.utils.module_provenance as _module_provenance

allow_local_changes_option = click.option(
    "--allow-local-changes",
    is_flag=True,
    help=(
        "Proceed when embedded module files were edited locally or cannot be "
        "verified; the subtree pull can overwrite them."
    ),
)


def _load_update_recovery_ledger(project_path: Path) -> Any | None:
    """Load the optional apply recovery ledger used by update guardrails.

    Returns the :class:`~quickscale_core.apply.RecoveryLedger` when the file
    exists and is valid, or ``None`` when it does not.  The ledger carries the
    resume pointer only; applied state stays in ``.quickscale/state.yml``.
    Malformed content raises :class:`LedgerError`, surfaced as a
    :class:`RuntimeError`.
    """
    mgr = _apply.LedgerManager(project_path)
    if not mgr.ledger_file.exists():
        return None

    try:
        ledger = mgr.load()
    except _apply.LedgerError as error:
        raise RuntimeError(
            "Failed to load .quickscale/apply-recovery.yml: "
            f"{error}. Fix or clear the recovery snapshot before updating modules."
        ) from error

    return ledger


def _check_local_pre_pull_guard(
    project_path: Path,
    module_name: str,
    module_state: Any,
) -> bool:
    """Block known-local unsafe updates before any subtree pull starts."""
    if module_state is None:
        _module_output._report_local_pre_pull_guard_block(
            module_name,
            [
                "",
                ".quickscale/state.yml does not list this module as installed.",
                "Reconcile local tracking with 'quickscale apply' before updating.",
                "This guard uses only verified local state and does not predict remote compatibility.",
            ],
        )
        return False

    recovery_ledger = _load_update_recovery_ledger(project_path)
    if recovery_ledger is not None:
        _module_output._report_local_pre_pull_guard_block(
            module_name,
            [
                "",
                "Pending .quickscale/apply-recovery.yml records an unfinished apply.",
                "Finish the interrupted apply or clear the local recovery ledger before running 'quickscale update'.",
                "The recovery ledger carries no applied state; .quickscale/state.yml remains authoritative.",
            ],
        )
        return False

    quickscale_config_path = project_path / "quickscale.yml"
    if not quickscale_config_path.exists() or module_state is None:
        return True

    try:
        desired_config = _config_schema.validate_config(
            quickscale_config_path.read_text()
        )
    except Exception as error:
        click.secho(
            "❌ Cannot update: quickscale.yml pre-pull check failed because the local desired state could not be validated.",
            fg="red",
            bold=True,
            err=True,
        )
        click.echo(f"Reason: {error}", err=True)
        click.echo(
            "💡 Fix quickscale.yml or run 'quickscale apply' to reconcile before updating.",
            err=True,
        )
        return False

    desired_module = desired_config.modules.get(module_name)
    if desired_module is None:
        _module_output._report_local_pre_pull_guard_block(
            module_name,
            [
                "",
                "quickscale.yml no longer includes this installed module.",
                f"Run 'quickscale remove {module_name}' or reconcile desired state with 'quickscale apply' before updating.",
                "This guard uses only verified local state and does not predict remote compatibility.",
            ],
        )
        return False

    desired_options = desired_module.options or {}
    applied_options = module_state.options or {}
    if desired_options == applied_options:
        return True

    drift_lines = [
        "",
        "Local desired state differs from applied module options.",
        "Run 'quickscale apply' before updating so local module configuration is reconciled first.",
        "Detected local-only option drift:",
    ]
    for option_name in sorted(set(desired_options) | set(applied_options)):
        old_value = applied_options.get(option_name)
        new_value = desired_options.get(option_name)
        if old_value == new_value:
            continue
        drift_lines.append(
            f"  • {module_name}.{option_name}: applied={old_value!r}, desired={new_value!r}"
        )
    drift_lines.append(
        "This guard uses only verified local state and does not predict remote compatibility."
    )
    _module_output._report_local_pre_pull_guard_block(module_name, drift_lines)
    return False


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
