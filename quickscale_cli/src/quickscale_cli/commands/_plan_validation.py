"""Existing-project validation and detection for the plan command.

Implementation detail of :mod:`quickscale_cli.commands.plan_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path


from quickscale_core.schema.config_schema import QuickScaleConfig
import quickscale_cli.commands.plan_command as _plan_command


def _abort_for_invalid_existing_config(config_path: Path, error: Exception) -> None:
    """Abort planner existing-project flows with actionable config remediation."""
    _plan_command.click.secho(
        "\n❌ Cannot continue because quickscale.yml is invalid.",
        fg="red",
        err=True,
        bold=True,
    )
    _plan_command.click.echo(f"  • {error}", err=True)
    _plan_command.click.echo(
        f"\n💡 Fix {config_path} and re-run this planner command.",
        err=True,
    )

    raise _plan_command.click.Abort()


def _validate_existing_project_notifications_or_abort(
    config: QuickScaleConfig,
) -> None:
    """Abort existing-project planner flows on invalid notifications settings."""
    notifications_config = config.modules.get("notifications")
    if notifications_config is None:
        return

    notifications_options = notifications_config.options or {}
    notification_issues = _plan_command.validate_module_options(
        _plan_command.load_module_manifest_with_fallback("notifications"),
        notifications_options,
    )
    if not notification_issues:
        return

    _plan_command.click.secho(
        "\n❌ Notifications module configuration is incomplete for this planner update:",
        fg="red",
        err=True,
        bold=True,
    )
    for issue in notification_issues:
        _plan_command.click.echo(f"  • {issue}", err=True)

    notifications_adapter = _plan_command.notifications_adapter_module()
    if notifications_adapter is not None and (
        notifications_adapter.notifications_production_targeted(notifications_options)
    ):
        _plan_command.click.echo(
            "\n💡 This configuration targets live Resend delivery, so planner "
            "refuses to rewrite quickscale.yml until the missing notifications "
            "settings are fixed. Re-run 'quickscale plan --reconfigure "
            "--configure-modules' or edit quickscale.yml first.",
            err=True,
        )
    else:
        _plan_command.click.echo(
            "\n💡 Re-run 'quickscale plan --reconfigure --configure-modules' or "
            "edit quickscale.yml to correct the notifications values.",
            err=True,
        )

    raise _plan_command.click.Abort()


def _validate_existing_project_config_or_abort(config: QuickScaleConfig) -> str:
    """Validate an updated existing-project configuration before it is saved.

    Runs the notifications prerequisite check, renders the desired-state YAML,
    and validates it through the same :func:`validate_config` the new-project
    flow uses — including each selected module's manifest-declared option
    checks.  An invalid value fails the planner instead of being written.

    Returns:
        The validated YAML text to preview and save.
    """
    _plan_command._validate_existing_project_notifications_or_abort(config)
    yaml_content = _plan_command.generate_yaml(config)

    try:
        _plan_command.validate_config(yaml_content)
    except Exception as error:
        _plan_command.click.secho(
            "\n❌ Configuration validation failed:", fg="red", err=True, bold=True
        )
        _plan_command.click.echo(f"  • {error}", err=True)
        raise _plan_command.click.Abort()

    return yaml_content


def _detect_existing_project(
    *,
    strict_config_validation: bool = False,
) -> tuple[Path | None, QuickScaleConfig | None]:
    """Detect if we're in an existing QuickScale project

    Returns:
        Tuple of (project_path, existing_config) if project found, (None, None) otherwise

    """
    cwd = _plan_command.Path.cwd()

    # Check for quickscale.yml in current directory
    config_path = cwd / "quickscale.yml"
    state_path = cwd / ".quickscale" / "state.yml"

    if config_path.exists():
        try:
            yaml_content = config_path.read_text()
            config = _plan_command.validate_config(yaml_content)
            return cwd, config
        except Exception:
            # Config exists but is invalid - treat as existing project anyway
            if strict_config_validation:
                raise
            return cwd, None
    elif state_path.exists():
        # State exists but no config - project exists but config is missing
        return cwd, None

    return None, None
