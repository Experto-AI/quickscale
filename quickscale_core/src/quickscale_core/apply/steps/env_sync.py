"""Step bodies for backups gitignore hardening and env-example syncs.

Steps 5-8 handle post-embed file maintenance that keeps the generated
project's supporting files aligned with module configuration:

- Step 5: Backups gitignore hardening
- Step 6: Notifications env-example sync
- Step 7: Analytics env-example sync
- Step 8: Billing env-example sync
"""

from __future__ import annotations

from typing import Callable

from quickscale_core.apply.steps.types import StepContext, StepOutcome


# ---------------------------------------------------------------------------
# Step 5: backups gitignore hardening
# ---------------------------------------------------------------------------


def step_backups_gitignore(
    ctx: StepContext,
    *,
    ensure_backups_ignore_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 5: Ensure custom backups directories are safely gitignored.

    Delegates to *ensure_backups_ignore_fn* which returns ``True`` on
    success.  On failure the step returns an unsuccessful outcome with
    the appropriate ``failed_step_label``.

    Args:
        ctx: Core-safe step context.
        ensure_backups_ignore_fn: Callable that reads ``qs_config`` and
            updates ``.gitignore`` with the backups ignore rule.  Returns
            ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"backups gitignore hardening"`` on failure.
    """
    if not ensure_backups_ignore_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .gitignore with configured backups directory",
            failed_step_label="backups gitignore hardening",
        )

    return StepOutcome(success=True, message="Backups gitignore rules applied")


# ---------------------------------------------------------------------------
# Step 6: notifications env-example sync
# ---------------------------------------------------------------------------


def step_notifications_env_sync(
    ctx: StepContext,
    *,
    sync_notifications_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 6: Keep ``.env.example`` aligned with notifications env-var names.

    Args:
        ctx: Core-safe step context.
        sync_notifications_fn: Callable returning ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"notifications env example sync"`` on failure.
    """
    if not sync_notifications_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .env.example with notifications env vars",
            failed_step_label="notifications env example sync",
        )

    return StepOutcome(
        success=True, message="Notifications env vars synced to .env.example"
    )


# ---------------------------------------------------------------------------
# Step 7: analytics env-example sync
# ---------------------------------------------------------------------------


def step_analytics_env_sync(
    ctx: StepContext,
    *,
    sync_analytics_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 7: Keep ``.env.example`` aligned with analytics env-var names.

    Args:
        ctx: Core-safe step context.
        sync_analytics_fn: Callable returning ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"analytics env example sync"`` on failure.
    """
    if not sync_analytics_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .env.example with analytics env vars",
            failed_step_label="analytics env example sync",
        )

    return StepOutcome(
        success=True, message="Analytics env vars synced to .env.example"
    )


# ---------------------------------------------------------------------------
# Step 8: billing env-example sync
# ---------------------------------------------------------------------------


def step_billing_env_sync(
    ctx: StepContext,
    *,
    sync_billing_fn: Callable[..., bool],
) -> StepOutcome:
    """Step 8: Keep ``.env.example`` aligned with billing env-var names.

    Args:
        ctx: Core-safe step context.
        sync_billing_fn: Callable returning ``True`` on success.

    Returns:
        :class:`StepOutcome` with ``failed_step_label`` set to
        ``"billing env example sync"`` on failure.
    """
    if not sync_billing_fn(ctx.output_path, ctx.qs_config):
        return StepOutcome(
            success=False,
            message="Unable to update .env.example with billing env vars",
            failed_step_label="billing env example sync",
        )

    return StepOutcome(success=True, message="Billing env vars synced to .env.example")


__all__ = [
    "step_analytics_env_sync",
    "step_backups_gitignore",
    "step_billing_env_sync",
    "step_notifications_env_sync",
]
