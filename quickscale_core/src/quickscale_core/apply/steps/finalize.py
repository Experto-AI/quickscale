"""Step bodies for finalization operations.

Steps 14-16 handle Railway deployment, authoritative state persistence,
and displaying next-step instructions to the operator.
"""

from __future__ import annotations

from typing import Any, Callable

from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Step 14: railway deploy
# ---------------------------------------------------------------------------


def step_railway_deploy(
    ctx: StepContext,
    *,
    is_railway_linked: bool,
    deploy_railway_fn: Callable[..., Any],
    get_service_name_fn: Callable[..., str],
) -> StepOutcome:
    """Step 14: Trigger Railway deployment if the project is Railway-linked.

    Args:
        ctx: Core-safe step context.
        is_railway_linked: Whether the project has a ``.railway``
            directory (indicating a linked Railway project).
        deploy_railway_fn: Callable that deploys the Railway service.
            May raise ``FileNotFoundError`` or ``TimeoutError``.
        get_service_name_fn: Callable that returns the Railway service
            name for the project slug.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"railway deploy"`` on failure.  When not Railway-linked,
        returns ``StepOutcome(success=True)`` with a skip message.
    """
    if not is_railway_linked:
        return StepOutcome(
            success=True, message="Not a Railway-linked project, skipping deploy"
        )

    service_name = get_service_name_fn(ctx.qs_config.project.slug)

    try:
        result = deploy_railway_fn(
            project_path=ctx.output_path,
            service_name=service_name,
        )
    except (FileNotFoundError, TimeoutError) as error:
        return StepOutcome(
            success=False,
            message=f"Railway CLI error: {error}",
            failed_step_label="railway deploy",
        )

    if hasattr(result, "returncode") and result.returncode != 0:
        error_detail = (
            (result.stderr or result.stdout or "").strip()
            if hasattr(result, "stderr")
            else ""
        )
        return StepOutcome(
            success=False,
            message=error_detail
            or "Railway deploy command returned non-zero exit code",
            failed_step_label="railway deploy",
        )

    if ctx.reporter:
        ctx.reporter("Railway deploy triggered", ok=True)

    return StepOutcome(success=True, message="Railway deploy triggered")


# ---------------------------------------------------------------------------
# Step 15: finalize apply state
# ---------------------------------------------------------------------------


def step_finalize_state(
    ctx: StepContext,
    *,
    save_project_state_fn: Callable[..., bool],
    save_recovery_state_fn: Callable[..., bool],
    clear_recovery_state_fn: Callable[..., None],
    checkpoint_tree_id: str,
) -> StepOutcome:
    """Step 15: Persist authoritative state and clean up recovery state.

    Attempts to save the authoritative project state.  If that fails,
    attempts to persist a recovery state so the apply remains rerunnable.
    If both fail, the step returns an unsuccessful outcome.

    Args:
        ctx: Core-safe step context with ``state_snapshot`` populated.
        save_project_state_fn: Callable that saves authoritative state
            to ``.quickscale/state.yml``.  Returns ``True`` on success.
        save_recovery_state_fn: Callable that saves recovery state to
            ``.quickscale/apply-recovery.yml``.  Returns ``True`` on
            success.
        clear_recovery_state_fn: Callable that removes the recovery
            ledger file.
        checkpoint_tree_id: The git tree id captured at the post-embed
            checkpoint.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"authoritative state persistence"`` on failure.
    """
    if save_project_state_fn():
        clear_recovery_state_fn()
        return StepOutcome(success=True, message="Authoritative state saved")

    # Project state save failed — try to persist recovery state.
    recovery_saved = save_recovery_state_fn(
        checkpoint_tree_id=checkpoint_tree_id,
    )

    if recovery_saved:
        return StepOutcome(
            success=False,
            message=(
                "All apply steps completed, but QuickScale could not save "
                ".quickscale/state.yml. Recovery state was saved to "
                ".quickscale/apply-recovery.yml so apply remains rerunnable."
            ),
            failed_step_label="authoritative state persistence",
        )

    return StepOutcome(
        success=False,
        message=(
            "All apply steps completed, but QuickScale could not save "
            ".quickscale/state.yml and could not preserve rerunnable "
            "recovery state in .quickscale/apply-recovery.yml."
        ),
        failed_step_label="authoritative state persistence",
    )


# ---------------------------------------------------------------------------
# Step 16: display next steps
# ---------------------------------------------------------------------------


def step_display_next_steps(
    ctx: StepContext,
    *,
    display_next_steps_fn: Callable[..., None],
    no_docker: bool,
    docker_started: bool | None,
    existing_project: bool,
) -> StepOutcome:
    """Step 16: Display success message and next-step instructions.

    Delegates the actual rendering to *display_next_steps_fn* since the
    display logic is heavily CLI-oriented (click output).

    Args:
        ctx: Core-safe step context.
        display_next_steps_fn: Callable that renders the post-apply
            next-steps output.
        no_docker: Whether ``--no-docker`` was passed.
        docker_started: Whether Docker actually started.
        existing_project: Whether this was an existing project apply.

    Returns:
        Always ``StepOutcome(success=True)`` — this step is informational
        and non-fatal.
    """
    display_next_steps_fn(
        ctx.output_path,
        ctx.qs_config,
        no_docker,
        docker_started,
        existing_project=existing_project,
    )

    return StepOutcome(success=True, message="Apply complete — next steps displayed")


__all__ = [
    "step_display_next_steps",
    "step_finalize_state",
    "step_railway_deploy",
]
