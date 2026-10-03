"""Failure reporting, state finalization, and step adapters.

Implementation detail of :mod:`quickscale_cli.commands.apply_command`;
collaborators are resolved through the sibling modules that define
them (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import click


from quickscale_cli.commands._module_shared import ModuleEmbedProvenance
from quickscale_core.schema.config_schema import (
    QuickScaleConfig,
)
from quickscale_core.schema.state_schema import (
    QuickScaleState,
)

# AF6 Phase 2 — core step bodies
from quickscale_core.apply.steps import (
    GitIndexSnapshot,
)
from quickscale_cli.commands._types import (
    ApplyContext,
    _APPLY_RECOVERY_FILENAME,
    _FAILED_STEP,
)

import quickscale_cli.commands._types as _types
import quickscale_core.apply.steps.types as _types_2
import quickscale_core.apply.steps as _steps
import quickscale_cli.commands._state as _state
import quickscale_cli.commands._context as _context
import quickscale_core.schema.state_schema as _state_schema
import quickscale_cli.commands._config as _config
import quickscale_cli.commands.apply_support as _apply_support
import quickscale_cli.commands._git_ops as _git_ops
import quickscale_cli.utils._railway_cli as _railway_cli
import quickscale_cli.utils._railway_project as _railway_project
import quickscale_core.contracts.module_options as _module_options


def _display_next_steps_impl(
    output_path: Path,
    qs_config: QuickScaleConfig,
    no_docker: bool,
    docker_started: bool | None = None,
    existing_project: bool = False,
) -> None:
    """Display success message and next steps."""
    click.echo("\n" + "=" * 50)
    click.secho("🎉 Apply complete!", fg="green", bold=True)
    click.echo("=" * 50)

    click.echo("\n📋 Next steps:")
    if output_path != Path.cwd():
        click.echo(f"  cd {qs_config.project.slug}")

    if qs_config.docker.start and not no_docker:
        if docker_started is False:
            click.echo("  # Docker auto-start failed during apply")
            click.echo("  quickscale up --build  # Retry Docker startup")
            click.echo("  quickscale logs        # View failure details")
        else:
            click.echo("  # Docker services should be running")
            click.echo("  quickscale logs backend  # View logs")
            click.echo("  quickscale ps        # Check status")
    else:
        click.echo("  quickscale up        # Start Docker services")
        click.echo("  quickscale manage migrate  # Run migrations after services start")
        click.echo("  # Or run without Docker:")
        click.echo("  poetry run python manage.py migrate")
        click.echo("  poetry run python manage.py runserver")

    modules = qs_config.modules if isinstance(qs_config.modules, Mapping) else {}
    if "backups" in modules:
        backups_options = _config._resolved_module_options(
            "backups", modules["backups"].options or {}
        )
        click.echo("\n  # Backups operations")
        click.echo("  poetry run python manage.py quickscale_backups_create")
        click.echo(
            "  poetry run python manage.py quickscale_backups_restore <id> --confirm BACKUP_FILENAME.dump --dry-run"
        )
        click.echo(
            "  poetry run python manage.py quickscale_backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump --dry-run"
        )
        click.echo(
            "  export QUICKSCALE_BACKUPS_ALLOW_RESTORE=true  # Required for destructive restores outside local DEBUG"
        )
        click.echo(
            "  JSON artifacts are export-only; generated PostgreSQL projects restore only PostgreSQL 18 custom dumps."
        )
        click.echo("  Admin download and validate stay local-file-only in v1.")
        if existing_project:
            click.echo(
                "  quickscale apply does not rewrite user-owned Docker/CI/E2E files; manually adopt the PostgreSQL 18 tooling updates if this project predates the backups follow-up."
            )
        else:
            click.echo(
                "  Freshly generated Docker and GitHub CI files already install PostgreSQL 18 client tooling."
            )
        if backups_options.get("target_mode") == "private_remote":
            access_key_env_var = str(
                backups_options.get(
                    _module_options.BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION
                )
                or ""
            )
            secret_key_env_var = str(
                backups_options.get(
                    _module_options.BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION
                )
                or ""
            )
            click.echo(
                "  Configure runtime credentials via env vars "
                f"`{access_key_env_var}` and `{secret_key_env_var}` before relying "
                "on scheduled or production restore workflows."
            )

    if "notifications" in modules:
        notifications_options = _config._resolved_module_options(
            "notifications", modules["notifications"].options or {}
        )
        resend_api_key_env_var = str(
            notifications_options.get(
                _module_options.NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION
            )
            or ""
        )
        webhook_secret_env_var = str(
            notifications_options.get(
                _module_options.NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION
            )
            or ""
        )
        click.echo("\n  # Notifications setup")
        notifications_adapter = _apply_support.notifications_adapter_module()
        if bool(notifications_options.get("enabled", True)):
            if notifications_adapter is not None and (
                notifications_adapter.notifications_live_delivery_configured(
                    notifications_options
                )
            ):
                resend_domain = str(
                    notifications_options.get("resend_domain", "")
                ).strip()
                click.echo(
                    "  Verify SPF/DKIM in Resend for "
                    + (resend_domain or "your sending domain")
                    + "."
                )
                click.echo(
                    f"  Set `{resend_api_key_env_var}` before relying on live email delivery."
                )
            else:
                click.echo(
                    "  Local development remains on the console email backend until "
                    "you configure a verified Resend domain."
                )
                click.echo(
                    f"  When ready, set `{resend_api_key_env_var}` and re-run `quickscale apply`."
                )
            click.echo(
                f"  Set `{webhook_secret_env_var}` before enabling signed delivery webhooks."
            )
        else:
            click.echo(
                "  Notifications is embedded but disabled. Re-enable it in quickscale.yml "
                "when you are ready to own email delivery through the module."
            )

    if "analytics" in modules:
        analytics_options = _config._resolved_module_options(
            "analytics", modules["analytics"].options or {}
        )
        click.echo("\n  # Analytics setup")
        if bool(analytics_options.get("enabled", True)):
            posthog_api_key_env_var = str(
                analytics_options.get("posthog_api_key_env_var") or ""
            )
            posthog_host_env_var = str(
                analytics_options.get("posthog_host_env_var") or ""
            )
            posthog_host = str(
                analytics_options.get("posthog_host")
                or _module_options.ANALYTICS_POSTHOG_DEFAULT_HOST
            )
            click.echo("  PostHog dashboard: https://app.posthog.com")
            click.echo(
                "  Live events: https://app.posthog.com/project/<project-id>/activity/explore"
            )
            click.echo(
                "  Set runtime Railway service variables: "
                f"`{posthog_api_key_env_var}` and optionally `{posthog_host_env_var}`."
            )
            click.echo(
                f"  Leave `{posthog_host_env_var}` blank to fall back to {posthog_host}."
            )
            click.echo(
                "  Set build-time `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` only for "
                "fresh `showcase_react` generations or manual frontend adoption."
            )
            click.echo(
                "  Existing React and HTML theme files remain user-owned; quickscale apply "
                "does not rewrite them for analytics."
            )
            click.echo(
                "  If you enforce CSP or referrer-policy restrictions, allow outbound "
                "requests to your configured PostHog API host."
            )
        else:
            click.echo(
                "  Analytics is embedded but disabled. Re-enable it in quickscale.yml "
                "when you are ready to capture events."
            )

    if "social" in modules:
        click.echo("\n  # Social integration")
        click.echo(
            "  Managed backend transport: "
            + f"{_module_options.SOCIAL_INTEGRATION_BASE_PATH} and {_module_options.SOCIAL_INTEGRATION_EMBEDS_PATH}"
        )
        click.echo(
            "  Fresh showcase_react generations keep Django-owned public pages at "
            + f"{_module_options.SOCIAL_LINK_TREE_PATH} and {_module_options.SOCIAL_EMBEDS_PATH}"
        )
        click.echo(
            "  showcase_react and existing generated projects only receive the managed "
            "backend transport automatically; use manual theme adoption if you want "
            "those public pages."
        )

    if "billing" in modules:
        billing_options = _config._resolved_module_options(
            "billing", modules["billing"].options or {}
        )
        webhook_secret_env_var = str(
            billing_options.get("webhook_secret_env_var") or ""
        )
        click.echo("\n  # Billing setup")
        click.echo(
            "  Create the Stripe webhook endpoint at API version 2026-06-24.dahlia, "
            "pointed at /billing/webhooks/stripe/."
        )
        click.echo(
            f"  Set `{webhook_secret_env_var}` to the endpoint's signing secret before "
            "enabling billing traffic."
        )
        click.echo(
            "  An endpoint on an older API version stops processing billing webhooks "
            "until it is recreated."
        )

    click.echo("\n  Visit: http://localhost:8000")


def _display_next_steps(
    output_path: Path,
    qs_config: QuickScaleConfig,
    no_docker: bool,
    docker_started: bool | None = None,
    *,
    existing_project: bool = False,
) -> None:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""
    step_ctx = _types_2.StepContext(output_path=output_path, qs_config=qs_config)
    _steps.step_display_next_steps(
        step_ctx,
        display_next_steps_fn=_display_next_steps_impl,
        no_docker=no_docker,
        docker_started=docker_started,
        existing_project=existing_project,
    )


def _print_apply_failure_summary(failed_step: str, reason: str) -> None:
    """Print explicit failure summary and skipped steps."""
    click.echo("\n" + "=" * 50)
    click.secho("❌ Apply failed", fg="red", bold=True)
    click.echo("=" * 50)
    click.echo(f"\nFailed step: {failed_step}")
    click.echo(f"Reason: {reason}")
    click.echo("\nSkipped downstream steps:")
    click.echo("  • poetry install")
    click.echo("  • docker start")
    click.echo("  • database migrations")
    click.echo("  • railway deploy")
    click.echo("  • success completion output")


def _abort_after_post_embed_failure(
    ctx: ApplyContext,
    post_embed_state: QuickScaleState,
    *,
    checkpoint_tree_id: str,
    failed_step: str,
    reason: str,
) -> None:
    """Persist rerunnable recovery state before aborting post-embed failures."""
    if _state._save_apply_recovery_state(
        ctx.output_path,
        ctx.qs_config,
        ctx.existing_state,
        list(post_embed_state.modules.keys()),
        ctx.delta,
        state_snapshot=post_embed_state,
        checkpoint_tree_id=checkpoint_tree_id,
    ):
        _print_apply_failure_summary(failed_step=failed_step, reason=reason)
        raise click.Abort()

    _print_apply_failure_summary(
        failed_step="apply recovery state persistence",
        reason=(
            f"{failed_step} failed and QuickScale could not save "
            f".quickscale/{_APPLY_RECOVERY_FILENAME} for rerun recovery."
        ),
    )
    raise click.Abort()


def _finalize_apply_state(
    ctx: ApplyContext,
    post_embed_state: QuickScaleState,
    *,
    checkpoint_tree_id: str,
) -> None:
    """Thin wrapper delegating to core step body (AF6 Phase 2)."""

    def _save_state() -> bool:
        return _state._save_project_state(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            list(post_embed_state.modules.keys()),
            ctx.delta,
            state_snapshot=post_embed_state,
        )

    def _save_recovery(*, checkpoint_tree_id: str) -> bool:
        return _state._save_apply_recovery_state(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            list(post_embed_state.modules.keys()),
            ctx.delta,
            state_snapshot=post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
        )

    def _clear_recovery() -> None:
        _state._clear_apply_recovery_state(ctx.output_path)

    step_ctx = _context._build_step_context(ctx, state_snapshot=post_embed_state)
    outcome = _steps.step_finalize_state(
        step_ctx,
        save_project_state_fn=_save_state,
        save_recovery_state_fn=_save_recovery,
        clear_recovery_state_fn=_clear_recovery,
        checkpoint_tree_id=checkpoint_tree_id,
    )

    if outcome.success:
        return

    _print_apply_failure_summary(
        failed_step=_FAILED_STEP.get(
            "authoritative state persistence", "authoritative state persistence"
        ),
        reason=str(outcome.message),
    )
    raise click.Abort()


def _exec_step_post_embed_snapshot(
    ctx: ApplyContext,
    embedded_modules: list[str],
    provenance_payloads: dict[str, ModuleEmbedProvenance] | None,
) -> tuple[QuickScaleState | None, str | None]:
    """Adapter for step 2 (post-embed state snapshot + git index capture).

    Returns ``(post_embed_state, checkpoint_tree_id)`` on success, or
    ``(None, None)`` and raises ``click.Abort`` on failure.
    """
    step_ctx = _context._build_step_context(ctx, embedded_modules=embedded_modules)

    def _build_snapshot() -> QuickScaleState | None:
        return _state._build_project_state_snapshot(
            ctx.output_path,
            ctx.qs_config,
            ctx.existing_state,
            embedded_modules,
            ctx.delta,
            provenance_payloads=provenance_payloads,
        )

    def _capture_index() -> GitIndexSnapshot | None:
        snapshot = _git_ops._capture_git_index_snapshot(ctx.output_path)
        if snapshot is None:
            return None
        return _steps.GitIndexSnapshot(tree_id=snapshot.tree_id)

    outcome = _steps.step_post_embed_snapshot(
        step_ctx,
        build_state_snapshot=_build_snapshot,
        capture_git_index=_capture_index,
    )

    if not outcome.success:
        _print_apply_failure_summary(
            failed_step="post-embed state snapshot",
            reason=str(outcome.message),
        )
        raise click.Abort()

    post_embed_state = cast(_state_schema.QuickScaleState, step_ctx.state_snapshot)
    return post_embed_state, step_ctx.checkpoint_tree_id or ""


def _exec_step_apply_mutable_config(ctx: ApplyContext) -> None:
    """Adapter for step 11 (apply mutable config).

    Informational step — never fails.
    """
    step_ctx = _context._build_step_context(ctx)
    _steps.step_apply_mutable_config(step_ctx)


def _exec_step_railway_deploy(
    ctx: ApplyContext,
    post_embed_state: QuickScaleState,
    *,
    checkpoint_tree_id: str,
) -> None:
    """Adapter for step 14 (Railway deploy).

    Raises ``click.Abort`` on failure via ``_abort_after_post_embed_failure``.
    """
    is_railway_linked = (ctx.output_path / ".railway").is_dir()

    def _deploy_fn(
        project_path: Path,
        service_name: str,
    ) -> Any:
        return _railway_cli.deploy_railway_service(
            project_path=project_path,
            service_name=service_name,
        )

    step_ctx = _context._build_step_context(ctx, state_snapshot=post_embed_state)

    outcome = _steps.step_railway_deploy(
        step_ctx,
        is_railway_linked=is_railway_linked,
        deploy_railway_fn=_deploy_fn,
        get_service_name_fn=_railway_project.get_app_service_name,
    )

    if not outcome.success:
        _abort_after_post_embed_failure(
            ctx,
            post_embed_state,
            checkpoint_tree_id=checkpoint_tree_id,
            failed_step="railway deploy",
            reason=str(outcome.message),
        )


def _confirm_destructive_remote_phase(
    *,
    should_auto_start_docker: bool,
    should_run_local_migrations: bool,
) -> None:
    """Display the destructive/remote banner and confirm before steps 11-16.

    Silently returns when ``_AF5_DESTRUCTIVE_CONFIRM_BYPASS`` is set (test
    mode).  Raises ``click.Abort`` when the operator declines.
    """
    if _types._AF5_DESTRUCTIVE_CONFIRM_BYPASS:
        return

    click.echo("\n" + "=" * 50)
    click.secho("⚠️  DESTRUCTIVE / REMOTE OPERATIONS AHEAD", fg="red", bold=True)
    click.echo("=" * 50)
    click.echo(
        "\nThe following steps will modify your database and/or external services:"
    )
    click.echo("  • Apply mutable configuration changes")
    if should_auto_start_docker:
        click.echo("  • Start Docker services")
        click.echo("  • Run database migrations (inside Docker backend container)")
    elif should_run_local_migrations:
        click.echo("  • Run database migrations (local)")
    else:
        click.echo("  • Database migrations step (no migration path configured)")
    click.echo("  • Trigger Railway deployment (if Railway-linked)")
    click.echo("  • Finalize authoritative apply state")
    click.echo("  • Display next steps\n")
    if not click.confirm("Proceed with destructive/remote operations?", default=True):
        click.secho(
            "\n❌ Destructive/remote phase cancelled. Steps 1-10 completed successfully.",
            fg="yellow",
        )
        raise click.Abort()
