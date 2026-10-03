"""Applied-state snapshots, recovery ledgers, and managed-file hashes.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

import click


from quickscale_cli.commands._module_shared import ModuleEmbedProvenance
from quickscale_core.schema.config_schema import (
    QuickScaleConfig,
)
from quickscale_core.schema.delta import ConfigDelta
from quickscale_core.schema.state_schema import (
    QuickScaleState,
)
from quickscale_core.apply import (
    LedgerManager,
)
from quickscale_core.project_state import (
    VersionDriftWarning,
)

# AF6 Phase 2 — core step bodies
from quickscale_core.apply.steps.types import StepOutcome
from quickscale_cli.commands._types import _APPLY_RECOVERY_FILENAME

import quickscale_core.project_state_manager as _project_state_manager
import quickscale_core.project_state_drift as _project_state_drift
import quickscale_core.apply.steps.types as _types
import quickscale_core.apply.steps as _steps
import quickscale_cli.commands._config as _config
import quickscale_core.apply as _apply
import quickscale_core.project_state_hashes as _project_state_hashes
import quickscale_core.schema.state_schema as _state_schema
import quickscale_core.config as _config_2
import quickscale_core.manifest.loader as _loader
import quickscale_core.contracts.module_options as _module_options
import quickscale_core as _quickscale_core
import quickscale_cli.commands.contract_vintage as _contract_vintage


def _resolve_managed_wiring_paths(
    qs_config: QuickScaleConfig,
) -> list[str]:
    """Return the managed wiring file paths that apply should track.

    Paths are repo-relative (forward slashes) so they match the keys
    written by :func:`compute_file_hashes`. The returned list always
    includes the default managed wiring files; module-specific managed
    files inside ``<package>/quickscale_managed/`` are not enumerated
    here because they are owned by individual modules and may be
    introduced or removed without breaking the drift signal.
    """
    package = qs_config.project.package
    return [
        f"{package}/{relative}"
        for relative in _project_state_hashes.DEFAULT_MANAGED_WIRING_PATHS
    ]


def _warn_version_drift_for_apply(
    project_path: Path,
    qs_config: QuickScaleConfig,
) -> list[VersionDriftWarning]:
    """Surface module version drift between state and legacy config.

    Called near the start of apply so users can see drift before any
    mutation. Drift between state and config is non-fatal: apply
    reconciles the two at finalize time via
    :func:`_sync_legacy_module_config_versions`. The warnings exist so
    that operations and status can surface the gap.
    """
    state_manager = _project_state_manager.ProjectStateManager(project_path)
    try:
        state = state_manager.load_state()
        config = state_manager.load_config()
    except (_state_schema.StateError, _config_2.ConfigError) as error:
        click.secho(
            f"⚠️  Could not read managed state files for drift check: {error}",
            fg="yellow",
        )
        return []

    drift = _project_state_drift.check_version_drift(state, config)
    if not drift:
        return []

    del qs_config
    click.secho(
        "\n⚠️  Module version drift between .quickscale/state.yml and "
        ".quickscale/config.yml:",
        fg="yellow",
        bold=True,
    )
    for warning in drift:
        click.echo(f"  • {warning.message}")
    click.echo(
        "\n💡 Apply will reconcile .quickscale/config.yml to the canonical "
        "state-managed version. The drift is informational and not fatal.",
    )
    return drift


def _capture_managed_file_hashes_after_apply(
    project_path: Path,
    qs_config: QuickScaleConfig,
    state: QuickScaleState,
) -> StepOutcome:
    """Thin wrapper delegating to core step body (AF6 Phase 2).

    Returns the :class:`StepOutcome` from the core step body.
    SA18.9 made this a fail-hard step — `quickscale apply` will abort
    when the outcome carries ``success=False``.
    """

    def _resolve_paths() -> list[str]:
        return _resolve_managed_wiring_paths(qs_config)

    def _compute_hashes(path: Path, paths: list[str]) -> dict[str, str]:
        return _project_state_hashes.compute_file_hashes(path, paths)

    def _record_hash(path_str: str, digest: str) -> None:
        state.managed_files[path_str] = _state_schema.ManagedFileRecord(
            path=path_str, hash=digest
        )

    def _reporter(message: str, *, ok: bool = True) -> None:
        if ok:
            click.echo(message)
        else:
            click.secho(message, fg="yellow")

    step_ctx = _types.StepContext(
        output_path=project_path,
        qs_config=qs_config,
        reporter=_reporter,
    )
    return _steps.step_capture_hashes(
        step_ctx,
        compute_file_hashes_fn=_compute_hashes,
        resolve_managed_wiring_paths_fn=_resolve_paths,
        record_hash_fn=_record_hash,
    )


def _populate_consolidated_tracking_from_legacy(
    project_path: Path,
    state: QuickScaleState,
) -> None:
    """Merge consolidated tracking fields from legacy config.yml into state.

    After ``embed_module`` runs, the legacy ``config.yml`` carries
    ``prefix``, ``branch``, and ``installed_at`` for each embedded module.
    This helper reads those values and populates the corresponding
    :class:`ModuleState` fields so that ``state.yml`` is self-contained
    after apply.  Modules already carrying consolidated tracking are
    left untouched.

    F12.2: fail-closed — ``ConfigError`` / ``OSError`` propagate instead
    of being silently swallowed.  ``load_config`` returns a default empty
    config when the file does not exist, so this is a no-op for
    config-only / non-consolidated projects.
    """
    from quickscale_core.config import load_config as _load_legacy_config

    # load_config returns an empty default ModuleConfig when the file does
    # not exist, so a missing config.yml is a safe no-op.  Malformed or
    # unreadable legacy config propagates as ConfigError / OSError
    # (fail-close per F12.2).
    legacy_config = _load_legacy_config(project_path)

    for module_name, module_info in legacy_config.modules.items():
        module_state = state.modules.get(module_name)
        if module_state is None:
            continue
        if module_state.prefix is None:
            module_state.prefix = module_info.prefix
        if module_state.branch is None:
            module_state.branch = module_info.branch
        if module_state.installed_at is None:
            module_state.installed_at = module_info.installed_at


def _build_project_state_snapshot(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
    *,
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None,
) -> QuickScaleState:
    """Build the state snapshot used for success or retry recovery."""
    timestamp = datetime.now().isoformat()

    if existing_state is None:
        new_state = _state_schema.QuickScaleState(
            version="1",
            project=_state_schema.ProjectState(
                slug=qs_config.project.slug,
                package=qs_config.project.package,
                theme=qs_config.project.theme,
                project_contract=_quickscale_core.__version__,
                # A fresh generation carries the current templates, so it has
                # adopted every declared step (SA207).
                adopted_contract_steps=_contract_vintage.declared_adoption_step_ids(
                    embedded_modules
                ),
                created_at=timestamp,
                last_applied=timestamp,
            ),
            modules={},
        )
    else:
        new_state = copy.deepcopy(existing_state)
        new_state.project.last_applied = timestamp
        # SA10.1: project_contract is generation-vintage evidence.
        # Fresh states set it from the current version (above).
        # Existing states preserve whatever they already have — legacy
        # projects that predate SA10.1 keep None (unknown vintage)
        # so future SA10.2 can distinguish "already on this contract"
        # from "unknown — needs manual adoption review".

    for module_name in embedded_modules:
        if module_name not in qs_config.modules:
            continue

        existing_module_state = new_state.modules.get(module_name)
        # Phase 2: populate commit_sha from the provenance payload when
        # available.  The provenance source_ref is the exact commit SHA
        # resolved once during apply embed (Phase 1 seam).
        provenance = (provenance_payloads or {}).get(module_name)
        commit_sha = (
            provenance.source_ref
            if provenance is not None
            else (existing_module_state.commit_sha if existing_module_state else None)
        )
        new_state.modules[module_name] = _state_schema.ModuleState(
            name=module_name,
            version=existing_module_state.version if existing_module_state else None,
            commit_sha=commit_sha,
            embedded_at=(
                existing_module_state.embedded_at
                if existing_module_state is not None
                else timestamp
            ),
            options=_module_options.sanitize_module_options(
                module_name,
                qs_config.modules[module_name].options,
            ),
        )

    _config._update_module_config_in_state(new_state, qs_config, delta)

    for module_name, module_state in new_state.modules.items():
        manifest = _loader.get_manifest_for_module(output_path, module_name)
        if manifest is None:
            continue

        normalized_version = _config_2.normalize_installed_version(manifest.version)
        if normalized_version is not None:
            module_state.version = normalized_version

    # Populate consolidated module-tracking fields (prefix, branch,
    # installed_at) from the legacy config.yml that embed_module wrote
    # during this apply pass.  This ensures state.yml is self-contained
    # after apply so that fresh push/update/status work from state alone.
    _populate_consolidated_tracking_from_legacy(output_path, new_state)

    return new_state


def _get_apply_recovery_manager(project_path: Path) -> LedgerManager:
    """Return a LedgerManager bound to the recovery ledger file."""
    return _apply.LedgerManager(project_path)


def _load_apply_recovery_state(project_path: Path) -> QuickScaleState | None:
    """Load any pending post-embed recovery snapshot.

    Returns the embedded applied-state (:class:`QuickScaleState`) when the
    recovery ledger file exists and is valid, or ``None`` when the file
    does not exist.  Malformed content raises :class:`LedgerError` which
    propagates as a ``StateError`` to existing callers.
    """
    mgr = _get_apply_recovery_manager(project_path)
    ledger = mgr.load()
    if ledger is None:
        return None
    return ledger.applied_state


def _merge_apply_recovery_state(
    existing_state: QuickScaleState | None,
    recovery_state: QuickScaleState | None,
) -> QuickScaleState | None:
    """Overlay recovery modules onto the authoritative state for retry planning."""
    if recovery_state is None:
        return existing_state

    if existing_state is None:
        return recovery_state

    merged_state = copy.deepcopy(existing_state)
    merged_state.project.last_applied = recovery_state.project.last_applied
    for module_name, module_state in recovery_state.modules.items():
        merged_state.modules[module_name] = copy.deepcopy(module_state)
    return merged_state


def _save_apply_recovery_state(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
    *,
    state_snapshot: QuickScaleState | None = None,
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None,
    checkpoint_tree_id: str,
) -> bool:
    """Persist retry context for failures that happen after embedding succeeded.

    The *checkpoint_tree_id* is the exact git tree id captured at the post-embed
    checkpoint so the recovery ledger records the authoritative index state
    rather than a later tree re-captured at save time.  It is **required** —
    the F12.1e contract fails hard when the checkpoint reference is unavailable.

    AF5 Phase 1: AF6-era (``resume_checkpoint``-absent) ledgers are handled
    conservatively — the new field is preserved if present and silently
    ``None`` if absent.
    """
    try:
        recovery_state = state_snapshot or _build_project_state_snapshot(
            output_path,
            qs_config,
            existing_state,
            embedded_modules,
            delta,
            provenance_payloads=provenance_payloads,
        )
        mgr = _get_apply_recovery_manager(output_path)

        # Carry forward any existing resume_checkpoint from the on-disk
        # ledger so AF5 metadata is preserved across recovery rewrites.
        existing_ledger = mgr.load()
        resume_checkpoint = (
            existing_ledger.resume_checkpoint if existing_ledger is not None else None
        )

        ledger = _apply.RecoveryLedger(
            applied_state=recovery_state,
            resume_checkpoint=resume_checkpoint,
            step_progress=None,
            git_index_checkpoint=checkpoint_tree_id,
        )
        mgr.save(ledger)
        click.secho(
            f"✅ Apply recovery saved to .quickscale/{_APPLY_RECOVERY_FILENAME}",
            fg="green",
        )
        return True
    except (_apply.LedgerError, OSError) as e:
        click.secho(
            f"❌ Failed to save apply recovery state: {e}",
            fg="red",
            err=True,
        )
        return False
    except Exception as e:
        click.secho(
            f"❌ Failed to save apply recovery state: {e}",
            fg="red",
            err=True,
        )
        return False


def _clear_apply_recovery_state(output_path: Path) -> None:
    """Remove any stale post-embed recovery snapshot."""
    mgr = _get_apply_recovery_manager(output_path)
    if not mgr.ledger_file.exists():
        return

    try:
        mgr.ledger_file.unlink()
    except OSError as e:
        click.secho(f"⚠️  Failed to clear apply recovery state: {e}", fg="yellow")


def _save_project_state(
    output_path: Path,
    qs_config: QuickScaleConfig,
    existing_state: QuickScaleState | None,
    embedded_modules: list[str],
    delta: ConfigDelta,
    *,
    state_snapshot: QuickScaleState | None = None,
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None = None,
) -> bool:
    """Save project state to .quickscale/state.yml.

    F12.2: helper-level fail-open (catches all exceptions, returns
    ``False``).  This is a deliberate pattern so that callers can decide
    the correct recovery action.  All direct callers handle the ``False``
    return by persisting recovery state and/or aborting with a clear
    message — the effective behavior is fail-closed.
    """
    try:
        state_manager = _state_schema.StateManager(output_path)
        new_state = state_snapshot or _build_project_state_snapshot(
            output_path,
            qs_config,
            existing_state,
            embedded_modules,
            delta,
            provenance_payloads=provenance_payloads,
        )

        state_manager.save(new_state)
        click.secho("✅ State saved to .quickscale/state.yml", fg="green")
        return True
    except Exception as e:
        click.secho(f"❌ Failed to save state: {e}", fg="red", err=True)
        return False
