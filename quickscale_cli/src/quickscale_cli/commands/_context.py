"""Apply context preparation, refresh, and provenance repair.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import click


from quickscale_core.schema.delta import ConfigDelta
from quickscale_core.schema.state_schema import (
    QuickScaleState,
)
from quickscale_core.manifest import ModuleManifest

# AF6 Phase 2 — core step bodies
from quickscale_core.apply.steps.types import StepContext
from quickscale_cli.commands._types import ApplyContext, _APPLY_RECOVERY_FILENAME

import quickscale_cli.commands._config as _config
import quickscale_cli.commands._generation as _generation
import quickscale_core.project_state_manager as _project_state_manager
import quickscale_core.schema.state_schema as _state_schema
import quickscale_cli.commands._state as _state
import quickscale_core.schema.delta as _delta
import quickscale_cli.commands._types as _types
import quickscale_core.apply.steps as _steps
import quickscale_core.apply.steps.types as _types_2
import quickscale_cli.commands.apply_support as _apply_support
import quickscale_core.utils.theme_validation as _theme_validation
import quickscale_cli.commands.contract_vintage as _contract_vintage
import quickscale_core.advisory_lock as _advisory_lock
import quickscale_core.manifest.loader_errors as _loader_errors
import quickscale_core.schema.config_schema as _config_schema
import quickscale_core.manifest.required_modules as _required_modules
import quickscale_core.utils.git_repo as _git_repo
import quickscale_core.manifest.loader as _loader
import quickscale_cli.utils.module_wiring_manager as _module_wiring_manager
import quickscale_core.project_state_hashes as _project_state_hashes
import quickscale_core.config as _config_2


def _provenance_repair_might_be_needed(ctx: ApplyContext) -> bool:
    """Check whether any installed module has a missing commit_sha.

    This is a cheap pre-lock probe used to decide whether the no-op gate
    should defer to the locked provenance-repair path instead of aborting
    immediately.  It does NOT perform the repair or write state.
    """
    if ctx.existing_state is None:
        return False
    if ctx.delta.has_changes:
        return False
    return any(
        module_state.commit_sha is None
        for module_state in ctx.existing_state.modules.values()
    )


def _attempt_provenance_repair_if_needed(ctx: ApplyContext) -> None:
    """Phase 3: Attempt bounded provenance repair for no-op scenarios.

    When delta.has_changes is False but some installed modules have missing
    commit_sha, attempt one bounded resolve_remote_ref() using existing
    tracking metadata. If successful, write authoritative state once. If
    resolution fails, warn and preserve no-op behavior.

    .. note::
       This function writes to ``.quickscale/state.yml`` and MUST only be
       called while the advisory lock is held (see :func:`_execute_apply_steps`).
    """
    if ctx.existing_state is None:
        return

    # Only attempt repair when this would otherwise be a no-op
    if ctx.delta.has_changes:
        return

    # Check if any installed modules have missing commit_sha
    modules_needing_repair = [
        module_name
        for module_name, module_state in ctx.existing_state.modules.items()
        if module_state.commit_sha is None
    ]

    if not modules_needing_repair:
        return

    click.echo(
        "\n🔧 Attempting provenance repair for modules with missing commit_sha..."
    )

    repaired_any = False
    repair_timestamp = datetime.now().isoformat()
    for module_name in modules_needing_repair:
        module_state = ctx.existing_state.modules[module_name]
        if module_state.branch is None:
            click.secho(
                f"⚠️  Cannot repair {module_name}: missing tracking branch metadata",
                fg="yellow",
            )
            continue

        # Use the default QuickScale remote URL
        remote = "https://github.com/Experto-AI/quickscale.git"
        branch = module_state.branch

        try:
            resolved_sha = _git_repo.resolve_remote_ref(remote, branch)
            manifest = _loader.get_manifest_for_module(ctx.output_path, module_name)
            repaired_version = module_state.version
            if manifest is not None:
                normalized_version = _config_2.normalize_installed_version(
                    manifest.version
                )
                if normalized_version is not None:
                    repaired_version = normalized_version
            # Commit the complete repair only after every lookup succeeds.
            # An incomplete embedded module must not leave partially repaired
            # state that can later be persisted.
            module_state.commit_sha = resolved_sha
            module_state.embedded_at = repair_timestamp
            module_state.version = repaired_version
            repaired_any = True
            click.secho(f"✅ Repaired {module_name}: {resolved_sha[:8]}", fg="green")
        except Exception as e:
            click.secho(
                f"⚠️  Could not resolve {module_name} from {branch}: {e}",
                fg="yellow",
            )

    if repaired_any:
        # Write authoritative state once with repaired commit_sha
        # Do NOT create recovery file — this is a best-effort repair
        try:
            state_manager = _state_schema.StateManager(ctx.output_path)
            state_manager.save(ctx.existing_state)
            click.secho(
                "✅ Updated .quickscale/state.yml with repaired provenance",
                fg="green",
            )
            # Refresh the delta so the next check sees no changes
            ctx.delta = _delta.compute_delta(
                ctx.qs_config, ctx.existing_state, ctx.manifests
            )
        except Exception as e:
            click.secho(
                f"⚠️  Failed to save repaired state: {e}",
                fg="yellow",
            )
    else:
        click.secho(
            "⚠️  Provenance repair could not resolve any modules. "
            "State remains unchanged.",
            fg="yellow",
        )


def _handle_delta_and_existing_state(
    delta: ConfigDelta,
    existing_state: QuickScaleState | None,
    *,
    has_pending_post_embed_recovery: bool = False,
    has_pending_provenance_repair: bool = False,
) -> None:
    """Handle delta display and abort conditions for existing state."""
    if existing_state is None:
        return

    click.echo("\n📊 Change Detection:")
    click.echo(_delta.format_delta(delta))

    if not delta.has_changes:
        if has_pending_post_embed_recovery:
            click.echo(
                "\n♻️  Pending post-embed apply recovery detected. "
                "Re-running the remaining apply steps."
            )
            return
        if has_pending_provenance_repair:
            click.echo(
                "\n🔧 Provenance repair needed. "
                "Continuing under advisory lock to repair state."
            )
            return
        click.secho(
            "\n✅ Nothing to do. Configuration matches applied state.", fg="green"
        )
        raise click.Abort()

    _config._abort_for_config_driven_module_removals(delta)

    if not _config._check_immutable_config_changes(delta):
        raise click.Abort()

    if delta.theme_changed:
        click.secho(
            "\n⚠️  WARNING: Theme changes are not supported after initial project generation!",
            fg="red",
            bold=True,
        )
        click.echo(
            "   Theme changes require regenerating the entire project from scratch.",
        )
        if not click.confirm("Continue anyway?", default=False):
            raise click.Abort()


def _prepare_apply_context(config_path: Path) -> ApplyContext:
    """Prepare all context needed for apply execution.

    Returns:
        ApplyContext with all loaded and computed data
    """
    # Load and validate configuration
    qs_config = _config._load_and_validate_config(config_path)

    # Determine output path
    output_path = _generation._determine_output_path(
        config_path, qs_config.project.slug
    )

    # Load existing state if project exists.
    # Use ProjectStateManager.load_state() for read-through legacy
    # compatibility so that apply planning sees the same consolidated
    # state as the rest of M2 (CR-001).
    project_state_manager = _project_state_manager.ProjectStateManager(output_path)
    state_manager = _state_schema.StateManager(output_path)
    try:
        authoritative_state = (
            project_state_manager.load_state() if output_path.exists() else None
        )
    except _state_schema.StateError as error:
        click.secho(
            f"\n❌ Failed to load .quickscale/state.yml: {error}",
            fg="red",
            err=True,
        )
        raise click.Abort() from error

    try:
        recovery_state = (
            _state._load_apply_recovery_state(output_path)
            if output_path.exists()
            else None
        )
    except _state_schema.StateError as error:
        click.secho(
            f"\n❌ Failed to load .quickscale/{_APPLY_RECOVERY_FILENAME}: {error}",
            fg="red",
            err=True,
        )
        raise click.Abort() from error

    existing_state = _state._merge_apply_recovery_state(
        authoritative_state, recovery_state
    )

    # Load manifests for modules (needed for config change detection)
    manifests: dict[str, ModuleManifest] = {}
    if existing_state and existing_state.modules:
        _config._abort_for_not_ready_modules(
            list(existing_state.modules.keys()),
            source=".quickscale/state.yml",
        )
        try:
            manifests = _config._load_module_manifests(
                output_path,
                list(existing_state.modules.keys()),
                strict=True,
            )
        except _loader_errors.ManifestError as error:
            _config._abort_for_manifest_error(error, command_name="apply")

    # Compute delta
    delta = _delta.compute_delta(qs_config, existing_state, manifests)

    return _types.ApplyContext(
        config_path=config_path,
        qs_config=qs_config,
        output_path=output_path,
        state_manager=state_manager,
        existing_state=existing_state,
        manifests=manifests,
        delta=delta,
        has_pending_post_embed_recovery=recovery_state is not None,
        had_existing_state=authoritative_state is not None,
    )


def _regenerate_managed_wiring_for_apply(
    ctx: ApplyContext,
    embedded_modules: list[str],
) -> bool:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""

    def _wiring_fn(
        output_path: Path,
        module_names: list[str],
        qs_config: Any,
        existing_state: Any | None,
        delta: Any | None,
    ) -> tuple[bool, str]:
        try:
            del module_names, existing_state, delta
            selected = sorted(qs_config.modules.keys())
            options = {
                module_name: dict(module_config.options or {})
                for module_name, module_config in qs_config.modules.items()
            }
            return _module_wiring_manager.regenerate_managed_wiring(
                output_path,
                module_names=selected,
                option_overrides=options,
                project_package=qs_config.project.package,
            )
        except Exception as exc:
            # Reducing the exception to str(exc) discards the traceback, which
            # is why installed-context failures like the SA112 managed-wiring
            # NameError have stayed undiagnosable across cycles. Surface the
            # full traceback to stderr when QUICKSCALE_DEBUG is set so the
            # actual raising frame can be captured; default behavior (and the
            # returned message) is unchanged.
            if os.environ.get("QUICKSCALE_DEBUG"):
                click.echo(traceback.format_exc(), err=True)
            return False, str(exc)

    step_ctx = _build_step_context(ctx, embedded_modules=embedded_modules)
    outcome = _steps.step_regenerate_wiring(
        step_ctx,
        embedded_modules=embedded_modules,
        regenerate_wiring_fn=_wiring_fn,
    )

    if outcome.success:
        if step_ctx.reporter:
            step_ctx.reporter("Managed module wiring regenerated", ok=True)
        return True

    click.secho(
        f"❌ Managed wiring regeneration failed: {outcome.message}", fg="red", err=True
    )
    return False


def _context_has_pending_post_embed_recovery(ctx: Any) -> bool:
    """Safely read the recovery flag from real contexts and loose test doubles."""
    value = getattr(ctx, "has_pending_post_embed_recovery", False)
    return value if isinstance(value, bool) else False


def _context_had_existing_state(ctx: Any) -> bool:
    """Safely determine whether apply started from authoritative state."""
    value = getattr(ctx, "had_existing_state", False)
    if isinstance(value, bool):
        return value
    return getattr(ctx, "existing_state", None) is not None


def _refresh_context_after_lock(ctx: ApplyContext) -> None:
    """Re-read authoritative state and recompute delta after lock acquisition.

    The pre-lock context loaded in :func:`_prepare_apply_context` may be
    stale if another concurrent apply finished between the initial read
    and lock acquisition.  Re-read state and recompute the delta so that
    the locked planning phase operates on fresh data.

    This is a no-op when the output path does not exist, has no
    authoritative state, or when the refresh would produce an inconsistent
    context (e.g. Mock objects in tests).
    """
    if not ctx.output_path.exists():
        return

    # Use ProjectStateManager.load_state() for read-through legacy
    # compatibility so the post-lock refresh sees the same consolidated
    # state as the rest of M2 (CR-001).
    project_state_manager = _project_state_manager.ProjectStateManager(ctx.output_path)
    try:
        authoritative_state = project_state_manager.load_state()
    except _state_schema.StateError:
        return  # Keep the pre-lock context; the locked path will surface errors.

    # If we could not load authoritative state, keep the pre-lock context.
    # This handles both fresh-project paths and test fixtures that use
    # non-project directories.
    if authoritative_state is None:
        return

    # F12.1d: malformed authoritative recovery ledger must fail hard
    # rather than being silently treated as absent.  LedgerError
    # (subclass of StateError) propagates to the operator.
    recovery_state = _state._load_apply_recovery_state(ctx.output_path)

    merged_state = _state._merge_apply_recovery_state(
        authoritative_state, recovery_state
    )

    # Reload manifests for the refreshed state.
    manifests: dict[str, ModuleManifest] = {}
    if merged_state and merged_state.modules:
        try:
            manifests = _config._load_module_manifests(
                ctx.output_path,
                list(merged_state.modules.keys()),
                strict=True,
            )
        except _loader_errors.ManifestError as error:
            _config._abort_for_manifest_error(error, command_name="apply")

    delta = _delta.compute_delta(ctx.qs_config, merged_state, manifests)

    ctx.existing_state = merged_state
    ctx.manifests = manifests
    ctx.delta = delta
    ctx.has_pending_post_embed_recovery = recovery_state is not None
    ctx.had_existing_state = True


def _build_step_context(
    ctx: ApplyContext,
    *,
    state_snapshot: Any = None,
    embedded_modules: list[str] | None = None,
    no_docker: bool = False,
    verbose_docker: bool = False,
) -> StepContext:
    """Build a core-safe :class:`StepContext` from the CLI-level :class:`ApplyContext`."""
    return _types_2.StepContext(
        output_path=ctx.output_path,
        qs_config=ctx.qs_config,
        existing_state=getattr(ctx, "existing_state", None),
        state_snapshot=state_snapshot,
        manifests=getattr(ctx, "manifests", {}),
        delta=getattr(ctx, "delta", None),
        embedded_modules=embedded_modules or [],
        no_docker=no_docker,
        verbose_docker=verbose_docker,
    )


def _resolve_apply_preflight(config_path: Path) -> Path:
    """Validate themes before apply performs any operational mutation."""
    resolve_root = _apply_support._resolve_apply_raw_root(config_path)
    try:
        _theme_validation.validate_theme_preflight(
            resolve_root,
            config_path=config_path,
            defer_config_errors=True,
        )
    except _theme_validation.ThemeValidationError as exc:
        _apply_support._report_theme_preflight_error(exc)
        raise click.Abort() from exc
    return resolve_root


def _enforce_apply_contract_vintage_preflight(
    config_path: Path,
    output_path: Path,
    *,
    acknowledged: bool,
    confirmed: bool = False,
) -> None:
    """Refuse incompatible existing projects before config normalization writes."""
    if not output_path.exists():
        return

    try:
        authoritative_state = _project_state_manager.ProjectStateManager(
            output_path
        ).load_state()
        recovery_state = _state._load_apply_recovery_state(output_path)
    except _state_schema.StateError as error:
        click.secho(
            f"\n❌ Failed to load existing project state: {error}",
            fg="red",
            err=True,
        )
        raise click.Abort() from error
    existing_state = _state._merge_apply_recovery_state(
        authoritative_state,
        recovery_state,
    )
    if existing_state is None:
        return

    module_names = set(existing_state.modules)
    try:
        preflight_config = _config_schema.validate_config(config_path.read_text())
    except _config_schema.ConfigValidationError, OSError:
        return
    configured_modules = set(preflight_config.modules)
    module_names.update(configured_modules)
    module_names.update(_required_modules.resolve_required_modules(configured_modules))

    _contract_vintage.enforce_shipped_contract_vintage(
        existing_state,
        module_names,
        operation="'quickscale apply'",
        acknowledged=acknowledged or confirmed,
    )


def _record_regenerated_wiring_hashes(ctx: ApplyContext) -> None:
    """Record the regenerated managed wiring's hashes in applied state.

    Loads through :class:`ProjectStateManager` so a pre-consolidation
    project's legacy module tracking and hash records are read-through
    imported and materialized rather than dropped when the consolidated
    sections are first written.  Without the hash records, ``quickscale
    status`` reports the adoption's own regeneration as managed-file drift.
    """
    state_manager = _project_state_manager.ProjectStateManager(ctx.output_path)
    state = state_manager.load_state()
    if state is None:
        return
    managed_paths = _state._resolve_managed_wiring_paths(ctx.qs_config)
    for path_str, digest in _project_state_hashes.compute_file_hashes(
        ctx.output_path, managed_paths
    ).items():
        state.managed_files[path_str] = _state_schema.ManagedFileRecord(
            path=path_str, hash=digest
        )
    state_manager.save_state(state)


def _regenerate_and_record_adoption(ctx: ApplyContext) -> bool:
    """Regenerate managed wiring, then record the confirmed adoption.

    Adopting the current generation contract includes its managed wiring: an
    older ``settings/modules.py`` without the release's schema would leave
    every installed module refusing startup.  The regenerated files' hashes
    are recorded before the adoption so the project does not report
    QuickScale's own regeneration as drift.  Nothing is recorded when the
    regeneration fails, so a project can never acknowledge a contract it did
    not receive.
    """
    embedded_modules = sorted(ctx.existing_state.modules) if ctx.existing_state else []
    if not _regenerate_managed_wiring_for_apply(ctx, embedded_modules):
        click.secho(
            "\n❌ Contract adoption not recorded: managed wiring regeneration failed.",
            fg="red",
            err=True,
        )
        return False
    _record_regenerated_wiring_hashes(ctx)
    current_state = _project_state_manager.ProjectStateManager(
        ctx.output_path
    ).load_state()
    _contract_vintage.record_contract_adoption(current_state, ctx.output_path)
    return True


def _record_confirmed_adoption(ctx: ApplyContext) -> bool | None:
    """Record a confirmed contract adoption under the apply advisory lock.

    The locked section re-reads authoritative state and recomputes the delta
    before acting, so a concurrent apply that landed between the pre-lock
    read and the lock cannot be overwritten by a regeneration built from the
    stale context.  Returns ``None`` when the no-delta premise no longer
    holds; the caller aborts rather than acting on a stale desired snapshot.
    """
    lock = _advisory_lock.AdvisoryLock(ctx.output_path, operation="apply")
    try:
        lock.acquire()
    except _advisory_lock.AdvisoryLockContentionError as error:
        raise click.ClickException(
            "Unable to acquire the project state lock to record the contract "
            f"adoption: {error}"
        ) from error
    try:
        _refresh_context_after_lock(ctx)
        if ctx.delta.has_changes or ctx.has_pending_post_embed_recovery:
            return None
        return _regenerate_and_record_adoption(ctx)
    finally:
        lock.release()
