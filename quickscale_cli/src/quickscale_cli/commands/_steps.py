"""Top-level apply step execution and recovery checkpointing.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import click


from quickscale_core.schema.state_schema import (
    QuickScaleState,
)
from quickscale_core.apply import (
    ApplyStep,
)

# AF6 Phase 2 — core step bodies
from quickscale_cli.commands._types import ApplyContext, _FAILED_STEP

import quickscale_cli.commands._context as _context
import quickscale_cli.commands._state as _state
import quickscale_core.advisory_lock as _advisory_lock
import quickscale_core.apply as _apply
import quickscale_cli.commands._finalize as _finalize
import quickscale_cli.commands._generation as _generation
import quickscale_cli.commands._git_ops as _git_ops
import quickscale_cli.commands._split_refs as _split_refs
import quickscale_cli.commands._embedding as _embedding
import quickscale_cli.commands.contract_vintage as _contract_vintage
import quickscale_cli.commands._runtime as _runtime
import quickscale_core.project_state_manager as _project_state_manager


def _execute_apply_steps(
    ctx: ApplyContext,
    force: bool,
    no_docker: bool,
    no_modules: bool,
    verbose_docker: bool = False,
    split_ref_overrides: Mapping[str, str] | None = None,
    *,
    split_refs_from_branches: bool = False,
) -> None:
    """Execute the apply steps after confirmation."""
    click.echo("\n" + "=" * 50)
    click.echo("🔧 Starting apply process...")
    click.echo("=" * 50)

    has_pending_post_embed_recovery = _context._context_has_pending_post_embed_recovery(
        ctx
    )

    # Surface module version drift between state and legacy config early.
    # Drift is non-fatal: apply reconciles the two at finalize time.
    _state._warn_version_drift_for_apply(ctx.output_path, ctx.qs_config)

    # Generate project (only for new projects)
    project_generated = False
    if ctx.existing_state is None:
        _generation._generate_new_project(ctx.qs_config, ctx.output_path, force)
        project_generated = True
    else:
        click.echo("⏭️  Skipping project generation (project already exists)")

    # Initialize git (only for new projects)
    if project_generated:
        _git_ops._init_git_with_config(ctx.output_path)

    # Acquire advisory lock after project directory exists but before any
    # state mutation. For new projects, the directory was just created by
    # project generation. For existing projects, it already exists.
    lock = _advisory_lock.AdvisoryLock(ctx.output_path, operation="apply")
    try:
        lock.acquire()
    except _advisory_lock.AdvisoryLockContentionError as error:
        click.secho(f"❌ {error}", fg="red", err=True)
        raise click.Abort() from error

    try:
        # Re-read authoritative state and recompute delta after acquiring
        # the lock so that planning uses fresh state, not a stale snapshot
        # taken before the lock was held.
        _context._refresh_context_after_lock(ctx)
        # The embed set can change under the lock, so a set derived before it
        # would no longer cover exactly the modules being embedded.  Re-derive
        # rather than re-validating a stale map.
        if split_refs_from_branches:
            split_ref_overrides = _split_refs._expand_split_refs_from_branches(ctx)
        _split_refs._validate_split_ref_override_coverage(
            ctx,
            split_ref_overrides,
            no_modules=no_modules,
        )

        # Phase 3: Attempt bounded provenance repair before no-op detection
        _context._attempt_provenance_repair_if_needed(ctx)

        # A confirmed adoption on a project with nothing else to apply is
        # recorded here, under the lock, after any provenance repair, so the
        # no-op gate below cannot discard the confirmation (SA207).  The
        # managed wiring is regenerated first so the adoption carries the
        # release's settings schema; a failed regeneration records nothing.
        if (
            ctx.confirm_contract_adoption
            and not ctx.delta.has_changes
            and not ctx.has_pending_post_embed_recovery
        ):
            if not _context._regenerate_and_record_adoption(ctx):
                raise click.Abort()
            click.secho(
                "\n✅ Nothing else to do. Configuration matches applied state.",
                fg="green",
            )
            return

        # Re-run top-level gate decisions with the refreshed state so that
        # stale pre-lock no-op / immutable-change / config-removal decisions
        # cannot continue mutating under the lock if another apply won the
        # race between the initial read and lock acquisition (CR-002).
        _context._handle_delta_and_existing_state(
            ctx.delta,
            ctx.existing_state,
            has_pending_post_embed_recovery=ctx.has_pending_post_embed_recovery,
        )

        _execute_apply_steps_locked(
            ctx,
            force,
            no_docker,
            no_modules,
            verbose_docker,
            project_generated=project_generated,
            has_pending_post_embed_recovery=has_pending_post_embed_recovery,
            split_ref_overrides=split_ref_overrides,
        )

        # Record the confirmed adoption after apply's own final state write,
        # still under the lock, so the outer command never re-acquires it
        # (SA207).
        if ctx.confirm_contract_adoption:
            current_state = _project_state_manager.ProjectStateManager(
                ctx.output_path
            ).load_state()
            _contract_vintage.record_contract_adoption(current_state, ctx.output_path)
    finally:
        lock.release()


def _resume_first_unsatisfied_step(
    executor: _apply.ApplyExecutor,
) -> ApplyStep | None:
    """Return the recovery checkpoint's first unsatisfied step, if readable."""
    try:
        checkpoint = executor.get_checkpoint()
        return executor.find_first_unsatisfied_step(checkpoint)
    except _apply.LedgerError:
        # Malformed checkpoint — fall back to running from step 1.
        click.secho(
            "⚠️  Could not read apply recovery checkpoint. Re-running from step 1.",
            fg="yellow",
        )
        return None


def _embed_modules_for_apply(
    ctx: ApplyContext,
    *,
    no_modules: bool,
    split_ref_overrides: Mapping[str, str] | None,
) -> Any:
    """Run step 1 and fail closed with the partial-embed summary on error."""
    modules_to_embed = (
        ctx.delta.modules_to_add
        if ctx.existing_state
        else list(ctx.qs_config.modules.keys())
    )

    # For existing projects, commit any pending QuickScale config changes
    # (e.g. quickscale.yml updated by `quickscale plan`) before embedding
    # modules, so git subtree has a clean working directory to operate on.
    if ctx.existing_state is not None and modules_to_embed:
        _git_ops._commit_pending_config_changes(ctx.output_path)

    if split_ref_overrides:
        embed_result = _embedding._embed_modules_step(
            ctx.output_path,
            modules_to_embed,
            no_modules,
            ctx.existing_state,
            split_ref_overrides,
        )
    else:
        embed_result = _embedding._embed_modules_step(
            ctx.output_path,
            modules_to_embed,
            no_modules,
            ctx.existing_state,
        )

    if embed_result.success:
        return embed_result

    # Persist successful partial embeds (explicit no-rollback contract).
    if not _state._save_project_state(
        ctx.output_path,
        ctx.qs_config,
        ctx.existing_state,
        embed_result.embedded_modules,
        ctx.delta,
        provenance_payloads=embed_result.provenance_payloads,
    ):
        _finalize._print_apply_failure_summary(
            failed_step=_FAILED_STEP["authoritative state persistence"],
            reason=(
                f"required module '{embed_result.failed_module}' failed to embed, "
                "and QuickScale could not save partial authoritative state to "
                ".quickscale/state.yml."
            ),
        )
        raise click.Abort()
    _state._clear_apply_recovery_state(ctx.output_path)
    _finalize._print_apply_failure_summary(
        failed_step=_FAILED_STEP["module embedding"],
        reason=f"required module '{embed_result.failed_module}' failed to embed",
    )
    raise click.Abort()


def _resume_post_embed_state(
    ctx: ApplyContext,
    executor: _apply.ApplyExecutor,
    embed_result: Any,
    *,
    should_run: bool,
) -> tuple[Any, Any]:
    """Return the post-embed state snapshot and its checkpoint tree id.

    When recovering past step 1, use the recovery ledger's applied_state as
    the post-embed state and its git_index_checkpoint as the tree id.
    """
    if should_run:
        return _finalize._exec_step_post_embed_snapshot(
            ctx,
            embed_result.embedded_modules,
            embed_result.provenance_payloads,
        )
    recovery_ledger = executor.load_ledger()
    if recovery_ledger is not None:
        return recovery_ledger.applied_state, recovery_ledger.git_index_checkpoint
    # Fallback — should not happen in recovery mode.
    return _finalize._exec_step_post_embed_snapshot(
        ctx,
        embed_result.embedded_modules,
        embed_result.provenance_payloads,
    )


def _checkpoint_post_embed_steps(
    embed_result: Any,
    *,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    should_run: bool,
    checkpoint_step: Callable[..., None],
) -> None:
    """Write the step 1 and step 2 recovery checkpoints after the snapshot.

    Seed both checkpoints with the real post-embed snapshot and
    checkpoint_tree_id so the recovery ledger is self-describing and does not
    carry placeholder state (AF5-CR-002).
    """
    if should_run and _embedding._embed_modules_ran_successfully(embed_result):
        checkpoint_step(
            _apply.APPLY_STEPS[0],
            checkpoint_tree_id=checkpoint_tree_id,
            state_snapshot=post_embed_state,
        )  # step 1 — embed modules
    if should_run and embed_result.embedded_modules:
        checkpoint_step(
            _apply.APPLY_STEPS[1],
            checkpoint_tree_id=checkpoint_tree_id,
            state_snapshot=post_embed_state,
        )  # step 2 — post-embed snapshot


def _run_managed_artifact_steps(
    ctx: ApplyContext,
    *,
    embedded_modules: Any,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> None:
    """Run steps 3 and 4: managed wiring and managed-file hash capture."""
    if should_run(3):
        if not _context._regenerate_managed_wiring_for_apply(ctx, embedded_modules):
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["managed module wiring generation"],
                reason="unable to render managed settings, URL, and integration files",
            )
        checkpoint_step(_apply.APPLY_STEPS[2])  # step 3

    if should_run(4):
        step4_outcome = _state._capture_managed_file_hashes_after_apply(
            ctx.output_path, ctx.qs_config, post_embed_state
        )
        if not step4_outcome.success:
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["capture managed file hashes"],
                reason=str(step4_outcome.message),
            )
        checkpoint_step(_apply.APPLY_STEPS[3])  # step 4


def _run_env_example_sync_steps(
    ctx: ApplyContext,
    *,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> None:
    """Run steps 5-7: gitignore hardening and env-example synchronization."""
    if should_run(5):
        if not _runtime._ensure_backups_gitignore_rules(ctx.output_path, ctx.qs_config):
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["backups gitignore hardening"],
                reason="Unable to update .gitignore with the configured private backups directory.",
            )
        checkpoint_step(_apply.APPLY_STEPS[4])  # step 5

    if should_run(6):
        if not _runtime._sync_notifications_env_example(ctx.output_path, ctx.qs_config):
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["notifications env example sync"],
                reason="Unable to update .env.example with the configured notifications env-var names.",
            )
        checkpoint_step(_apply.APPLY_STEPS[5])  # step 6

    if should_run(7):
        if not _runtime._sync_analytics_env_example(ctx.output_path, ctx.qs_config):
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["analytics env example sync"],
                reason="Unable to update .env.example with the configured analytics env-var names.",
            )
        checkpoint_step(_apply.APPLY_STEPS[6])  # step 7


def _run_module_dependency_steps(
    ctx: ApplyContext,
    *,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> None:
    """Run steps 8 and 9: billing env example and module dependency sync."""
    if should_run(8):
        if not _runtime._sync_billing_env_example(ctx.output_path, ctx.qs_config):
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["billing env example sync"],
                reason="Unable to update .env.example with the configured billing env-var names.",
            )
        checkpoint_step(_apply.APPLY_STEPS[7])  # step 8

    if should_run(9):
        if not _runtime._sync_project_module_dependencies_for_apply(
            ctx.output_path,
            ctx.qs_config,
        ):
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP["module dependency sync"],
                reason="Unable to reconcile embedded-module Poetry dependency entries in pyproject.toml.",
            )
        checkpoint_step(_apply.APPLY_STEPS[8])  # step 9


def _dependency_setup_flags(ctx: ApplyContext, *, no_docker: bool) -> tuple[bool, bool]:
    """Return the destructive-phase docker/migration flags for steps 10-13."""
    should_auto_start_docker = not no_docker and ctx.qs_config.docker.start
    should_run_local_migrations = (ctx.existing_state is not None) and (
        not ctx.qs_config.docker.start or no_docker
    )
    return should_auto_start_docker, should_run_local_migrations


def _run_dependency_setup_step(
    ctx: ApplyContext,
    *,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> None:
    """Run step 10: poetry lock and dependency installation (no migrations)."""
    if should_run(10):
        if not _runtime._run_post_generation_steps(
            ctx.output_path,
        ):
            _finalize._abort_after_post_embed_failure(
                ctx,
                post_embed_state,
                checkpoint_tree_id=checkpoint_tree_id,
                failed_step=_FAILED_STEP[
                    "post-generation dependency and migration setup"
                ],
                reason="Poetry lock refresh or dependency installation failed after module dependency sync.",
            )
        checkpoint_step(_apply.APPLY_STEPS[9])  # step 10


def _run_mutable_config_step(
    ctx: ApplyContext,
    *,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> None:
    """Run step 11: apply the mutable project configuration."""
    if should_run(11):
        _finalize._exec_step_apply_mutable_config(ctx)
        checkpoint_step(_apply.APPLY_STEPS[10])  # step 11


def _run_docker_startup_step(
    ctx: ApplyContext,
    *,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    should_auto_start_docker: bool,
    verbose_docker: bool,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> bool | None:
    """Run step 12: optional Docker startup; return whether Docker started."""
    docker_started: bool | None = None
    if should_run(12):
        if should_auto_start_docker:
            if _runtime._should_check_stale_volumes(
                ctx
            ) and not _runtime._preflight_stale_docker_volumes(ctx.output_path):
                _finalize._abort_after_post_embed_failure(
                    ctx,
                    post_embed_state,
                    checkpoint_tree_id=checkpoint_tree_id,
                    failed_step=_FAILED_STEP["docker startup"],
                    reason=(
                        "Leftover Docker volumes from an earlier project of the "
                        "same name would corrupt this project's migration history."
                    ),
                )
            docker_started = _runtime._start_docker(
                ctx.output_path, ctx.qs_config.docker.build, verbose_docker
            )
            if not docker_started:
                _finalize._abort_after_post_embed_failure(
                    ctx,
                    post_embed_state,
                    checkpoint_tree_id=checkpoint_tree_id,
                    failed_step=_FAILED_STEP["docker startup"],
                    reason="Docker auto-start failed. Run 'quickscale logs' to inspect the failing service.",
                )
        checkpoint_step(_apply.APPLY_STEPS[11])  # step 12
    return docker_started


def _run_migration_step(
    ctx: ApplyContext,
    *,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    should_auto_start_docker: bool,
    docker_started: bool | None,
    should_run_local_migrations: bool,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> None:
    """Run step 13: database migrations in Docker or locally."""
    if should_run(13):
        if should_auto_start_docker and docker_started:
            if not _runtime._run_migrations_in_docker(ctx.output_path):
                _finalize._abort_after_post_embed_failure(
                    ctx,
                    post_embed_state,
                    checkpoint_tree_id=checkpoint_tree_id,
                    failed_step=_FAILED_STEP["database migrations"],
                    reason="Migrations failed inside Docker backend container. Run 'quickscale logs backend' for details.",
                )
        elif should_run_local_migrations:
            if not _runtime._run_local_migrations(ctx.output_path):
                _finalize._abort_after_post_embed_failure(
                    ctx,
                    post_embed_state,
                    checkpoint_tree_id=checkpoint_tree_id,
                    failed_step=_FAILED_STEP["database migrations"],
                    reason="Local database migrations failed. Run 'poetry run python manage.py migrate' manually for details.",
                )
        checkpoint_step(_apply.APPLY_STEPS[12])  # step 13


def _run_final_apply_steps(
    ctx: ApplyContext,
    *,
    post_embed_state: Any,
    checkpoint_tree_id: Any,
    no_docker: bool,
    docker_started: bool | None,
    should_run: Callable[[int], bool],
    checkpoint_step: Callable[..., None],
) -> None:
    """Run steps 14-16: Railway deploy, finalize, and next-steps display.

    No checkpoint follows finalize or display: those steps clear the recovery
    ledger, and writing another would recreate a stale one (AF5-CR-001).
    """
    if should_run(14):
        _finalize._exec_step_railway_deploy(
            ctx,
            post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
        )
        checkpoint_step(_apply.APPLY_STEPS[13])  # step 14

    if should_run(15):
        _finalize._finalize_apply_state(
            ctx,
            post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
        )

    if should_run(16):
        _finalize._display_next_steps(
            ctx.output_path,
            ctx.qs_config,
            no_docker,
            docker_started,
            existing_project=ctx.existing_state is not None,
        )


def _execute_apply_steps_locked(
    ctx: ApplyContext,
    force: bool,
    no_docker: bool,
    no_modules: bool,
    verbose_docker: bool = False,
    *,
    project_generated: bool = False,
    has_pending_post_embed_recovery: bool = False,
    split_ref_overrides: Mapping[str, str] | None = None,
) -> None:
    """Execute the apply steps while holding the advisory lock.

    AF5 Phase 2: When *has_pending_post_embed_recovery* is ``True``, the
    function uses :class:`ApplyExecutor` to determine the first unsatisfied
    step from the recovery ledger's ``resume_checkpoint`` and skips
    already-completed non-destructive steps.  After each step executes, a
    checkpoint is written to the recovery ledger.
    """
    executor = _apply.ApplyExecutor(ctx.output_path)
    first_step: ApplyStep | None = None
    if has_pending_post_embed_recovery:
        first_step = _resume_first_unsatisfied_step(executor)

    def _should_run(step_order: int) -> bool:
        """Return ``True`` when the step at *step_order* should execute
        (not be skipped by the recovery checkpoint)."""
        if first_step is None:
            return True
        return step_order >= first_step.order

    def _checkpoint_step(
        step: ApplyStep,
        *,
        checkpoint_tree_id: str | None = None,
        state_snapshot: QuickScaleState | None = None,
    ) -> None:
        """Write checkpoint progress for a completed step.

        Args:
            step: The step that just completed.
            checkpoint_tree_id: Optional git tree id to seed the
                recovery ledger with the real post-embed checkpoint
                instead of a placeholder (AF5-CR-002).
            state_snapshot: Optional ``QuickScaleState`` snapshot to
                use as the recovery ledger's applied_state (seeds
                real project metadata instead of fallback placeholders).
        """
        try:
            executor.checkpoint_step(
                step,
                checkpoint_tree_id=checkpoint_tree_id,
                state_snapshot=state_snapshot,
            )
        except _apply.LedgerError:
            click.secho(
                f"⚠️  Could not write apply checkpoint for step "
                f"'{step.step_id}'. Continuing anyway.",
                fg="yellow",
            )

    embed_result = _embed_modules_for_apply(
        ctx, no_modules=no_modules, split_ref_overrides=split_ref_overrides
    )
    embedded_modules = embed_result.embedded_modules

    post_embed_state, checkpoint_tree_id = _resume_post_embed_state(
        ctx, executor, embed_result, should_run=_should_run(2)
    )

    # Narrow the optional types: the adapter raises click.Abort on failure,
    # so these are always populated past this point.
    assert post_embed_state is not None  # noqa: S101 - internal invariant guaranteed by the caller
    assert checkpoint_tree_id is not None  # noqa: S101 - internal invariant guaranteed by the caller

    _checkpoint_post_embed_steps(
        embed_result,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        should_run=_should_run(2),
        checkpoint_step=_checkpoint_step,
    )
    _run_managed_artifact_steps(
        ctx,
        embedded_modules=embedded_modules,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        should_run=_should_run,
        checkpoint_step=_checkpoint_step,
    )
    _run_env_example_sync_steps(
        ctx,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        should_run=_should_run,
        checkpoint_step=_checkpoint_step,
    )
    _run_module_dependency_steps(
        ctx,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        should_run=_should_run,
        checkpoint_step=_checkpoint_step,
    )
    _run_dependency_setup_step(
        ctx,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        should_run=_should_run,
        checkpoint_step=_checkpoint_step,
    )

    # ------------------------------------------------------------------
    # Late confirmation gate — destructive/remote phase (steps 11-16)
    # ------------------------------------------------------------------
    # AF5 Phase 4: All destructive and remote operations — Docker startup,
    # database migrations (local and Docker), Railway deploy — are grouped
    # into this separately-confirmable phase so the operator can inspect
    # the non-destructive results of steps 1-10 before committing to
    # operations that touch the database, Docker, or external services.
    #
    # When ``_AF5_DESTRUCTIVE_CONFIRM_BYPASS`` is ``True`` (test mode),
    # the gate is silently skipped without printing or prompting.
    should_auto_start_docker, should_run_local_migrations = _dependency_setup_flags(
        ctx, no_docker=no_docker
    )
    _finalize._confirm_destructive_remote_phase(
        should_auto_start_docker=should_auto_start_docker,
        should_run_local_migrations=should_run_local_migrations,
    )

    _run_mutable_config_step(
        ctx, should_run=_should_run, checkpoint_step=_checkpoint_step
    )
    docker_started = _run_docker_startup_step(
        ctx,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        should_auto_start_docker=should_auto_start_docker,
        verbose_docker=verbose_docker,
        should_run=_should_run,
        checkpoint_step=_checkpoint_step,
    )
    _run_migration_step(
        ctx,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        should_auto_start_docker=should_auto_start_docker,
        docker_started=docker_started,
        should_run_local_migrations=should_run_local_migrations,
        should_run=_should_run,
        checkpoint_step=_checkpoint_step,
    )
    _run_final_apply_steps(
        ctx,
        post_embed_state=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
        no_docker=no_docker,
        docker_started=docker_started,
        should_run=_should_run,
        checkpoint_step=_checkpoint_step,
    )
