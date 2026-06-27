"""Step bodies for infrastructure operations.

Steps 11-13 handle mutable config application, Docker startup, and
database migration execution — the operational steps that run after
module embedding and code generation are complete.
"""

from __future__ import annotations

from typing import Callable

from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Step 11: apply mutable config
# ---------------------------------------------------------------------------


def step_apply_mutable_config(ctx: StepContext) -> StepOutcome:
    """Step 11: Apply mutable configuration changes.

    This is an informational step.  The actual mutable config changes are
    materialised during managed wiring regeneration (step 3); this step
    exists to surface the confirmation message in the operator output.

    Args:
        ctx: Core-safe step context.  ``ctx.delta`` is checked for
            mutable config changes.

    Returns:
        Always ``StepOutcome(success=True)`` — this step is informational.
    """
    if ctx.delta is not None and hasattr(ctx.delta, "has_mutable_config_changes"):
        if ctx.delta.has_mutable_config_changes and ctx.reporter:
            ctx.reporter(
                "Mutable configuration changes applied via managed wiring", ok=True
            )

    return StepOutcome(success=True, message="Mutable config check complete")


# ---------------------------------------------------------------------------
# Step 12: docker startup
# ---------------------------------------------------------------------------


def step_start_docker(
    ctx: StepContext,
    *,
    should_auto_start_docker: bool,
    start_docker_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 12: Start Docker services if configured.

    Args:
        ctx: Core-safe step context.
        should_auto_start_docker: Whether Docker should be started.
        start_docker_fn: Callable that starts Docker services and
            returns ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"docker startup"`` on failure.  When Docker is not configured,
        returns ``StepOutcome(success=True)`` with a skip message.
    """
    if not should_auto_start_docker:
        return StepOutcome(
            success=True, message="Docker auto-start not configured, skipping"
        )

    docker_started = start_docker_fn(ctx.output_path, ctx.qs_config)
    if not docker_started:
        return StepOutcome(
            success=False,
            message="Docker auto-start failed",
            failed_step_label="docker startup",
        )

    return StepOutcome(success=True, message="Docker services started")


# ---------------------------------------------------------------------------
# Step 13: database migrations
# ---------------------------------------------------------------------------


def step_run_migrations(
    ctx: StepContext,
    *,
    should_auto_start_docker: bool,
    docker_started: bool | None,
    run_migrations_in_docker_fn: Callable[..., bool],
    should_run_local_migrations: bool = False,
    run_local_migrations_fn: Callable[..., bool] | None = None,
) -> StepOutcome:
    """Step 13: Run database migrations.

    AF5 Phase 4: This step handles **all** migration paths — Docker,
    existing-project local, and ``--no-docker`` — in a single late
    confirmable phase.

    For Docker-first projects, migrations run inside the backend container.
    For non-Docker projects (existing-project without Docker or with
    ``--no-docker``), local migrations run directly with ``manage.py
    migrate``.  When neither path applies, the step is skipped.

    Args:
        ctx: Core-safe step context.
        should_auto_start_docker: Whether Docker auto-start is configured.
        docker_started: Whether Docker actually started (``True``,
            ``False``, or ``None`` if not attempted).
        run_migrations_in_docker_fn: Callable that runs migrations inside
            the Docker container and returns ``True`` on success.
        should_run_local_migrations: Whether to run local migrations
            (existing-project or ``--no-docker`` path).
        run_local_migrations_fn: Callable that runs local migrations and
            returns ``True`` on success.  Required when
            *should_run_local_migrations* is ``True``.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"database migrations"`` on failure.
    """
    if should_auto_start_docker and docker_started:
        if not run_migrations_in_docker_fn(ctx.output_path):
            return StepOutcome(
                success=False,
                message="Migrations failed inside Docker backend container",
                failed_step_label="database migrations",
            )
        return StepOutcome(
            success=True, message="Database migrations completed in Docker"
        )

    if should_run_local_migrations:
        if run_local_migrations_fn is None:
            return StepOutcome(
                success=False,
                message="Local migrations requested but no callback provided",
                failed_step_label="database migrations",
            )
        if not run_local_migrations_fn(ctx.output_path):
            return StepOutcome(
                success=False,
                message="Local database migrations failed",
                failed_step_label="database migrations",
            )
        return StepOutcome(
            success=True, message="Database migrations completed (local)"
        )

    return StepOutcome(
        success=True, message="Migrations step skipped (no migration path configured)"
    )


__all__ = [
    "step_apply_mutable_config",
    "step_run_migrations",
    "step_start_docker",
]
