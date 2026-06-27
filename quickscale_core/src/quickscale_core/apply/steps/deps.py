"""Step bodies for module dependency sync and post-generation setup.

Step 9 (module dependency sync) and step 10 (post-generation dependency
and migration setup) handle Poetry dependency management and local
migration execution.
"""

from __future__ import annotations

from typing import Callable

from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Step 9: module dependency sync
# ---------------------------------------------------------------------------


def step_sync_dependencies(
    ctx: StepContext,
    *,
    sync_project_deps_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 9: Sync embedded-module Poetry dependency entries.

    Delegates to *sync_project_deps_fn* which should return ``True`` on
    success.

    Args:
        ctx: Core-safe step context.
        sync_project_deps_fn: Callable that syncs module dependencies in
            the generated project's ``pyproject.toml`` and returns
            ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"module dependency sync"`` on failure.
    """
    if not sync_project_deps_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to reconcile embedded-module Poetry dependency entries",
            failed_step_label="module dependency sync",
        )

    return StepOutcome(success=True, message="Module dependencies synced")


# ---------------------------------------------------------------------------
# Step 10: post-generation dependency and migration setup
# ---------------------------------------------------------------------------


def step_post_generation_setup(
    ctx: StepContext,
    *,
    should_auto_start_docker: bool,
    should_run_local_migrations: bool,
    run_post_gen_steps_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 10: Refresh lockfile, install dependencies, run local migrations.

    The *should_run_local_migrations* flag controls whether local migrations
    are executed.  For Docker-first projects, migrations run inside the
    container (step 13) instead.

    Args:
        ctx: Core-safe step context.
        should_auto_start_docker: Whether Docker auto-start is configured.
        should_run_local_migrations: Whether to run local migrations.
        run_post_gen_steps_fn: Callable that runs the post-generation steps
            (poetry lock, install, optional migrations).  Returns ``True``
            on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"post-generation dependency and migration setup"`` on failure.
    """
    if not run_post_gen_steps_fn(
        ctx.output_path,
        run_migrations=should_run_local_migrations,
    ):
        return StepOutcome(
            success=False,
            message=(
                "Poetry lock refresh, dependency installation, or local "
                "migrations failed after module dependency sync"
            ),
            failed_step_label="post-generation dependency and migration setup",
        )

    return StepOutcome(
        success=True,
        message="Post-generation dependencies and migrations completed",
    )


__all__ = [
    "step_post_generation_setup",
    "step_sync_dependencies",
]
