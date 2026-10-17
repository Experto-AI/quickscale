"""Existing-project validation and detection for the plan command.

Implementation detail of :mod:`quickscale_cli.commands.plan_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path


from quickscale_core.schema.config_schema import QuickScaleConfig

import quickscale_cli.commands.apply_support as _apply_support
import quickscale_core.schema.config_schema as _config_schema
import click
import pathlib as _pathlib


def _abort_for_invalid_existing_config(config_path: Path, error: Exception) -> None:
    """Abort planner existing-project flows with actionable config remediation."""
    click.secho(
        "\n❌ Cannot continue because quickscale.yml is invalid.",
        fg="red",
        err=True,
        bold=True,
    )
    click.echo(f"  • {error}", err=True)
    click.echo(
        f"\n💡 Fix {config_path} and re-run this planner command.",
        err=True,
    )

    raise click.Abort()


def _validate_existing_project_module_options_or_abort(
    config: QuickScaleConfig,
) -> None:
    """Abort existing-project planner flows on invalid module option values.

    Every configured module's values are judged by its manifest-declared
    checks, and a module whose adapter supplies operator guidance through the
    generic hook carries its own remediation text; the planner refuses to
    rewrite ``quickscale.yml`` until the refusal is fixed.
    """
    for module_name in sorted(config.modules):
        options = config.modules[module_name].options or {}
        issues = _apply_support.module_option_issues(module_name, options)
        if not issues:
            continue

        click.secho(
            f"\n❌ {module_name.capitalize()} module configuration is "
            "incomplete for this planner update:",
            fg="red",
            err=True,
            bold=True,
        )
        for issue in issues:
            click.echo(f"  • {issue}", err=True)

        _apply_support.echo_module_option_abort_hint(module_name, options)
        raise click.Abort()


def _validate_existing_project_config_or_abort(config: QuickScaleConfig) -> str:
    """Validate an updated existing-project configuration before it is saved.

    Runs the module option prerequisite check, renders the desired-state YAML,
    and validates it through the same :func:`validate_config` the new-project
    flow uses — including each selected module's manifest-declared option
    checks.  An invalid value fails the planner instead of being written.

    Returns:
        The validated YAML text to preview and save.
    """
    _validate_existing_project_module_options_or_abort(config)
    yaml_content = _config_schema.generate_yaml(config)

    try:
        _config_schema.validate_config(yaml_content)
    except Exception as error:
        click.secho(
            "\n❌ Configuration validation failed:", fg="red", err=True, bold=True
        )
        click.echo(f"  • {error}", err=True)
        raise click.Abort()

    return yaml_content


def _detect_existing_project(
    *,
    strict_config_validation: bool = False,
) -> tuple[Path | None, QuickScaleConfig | None]:
    """Detect if we're in an existing QuickScale project

    Returns:
        Tuple of (project_path, existing_config) if project found, (None, None) otherwise

    """
    cwd = _pathlib.Path.cwd()

    # Check for quickscale.yml in current directory
    config_path = cwd / "quickscale.yml"
    state_path = cwd / ".quickscale" / "state.yml"

    if config_path.exists():
        try:
            yaml_content = config_path.read_text()
            config = _config_schema.validate_config(yaml_content)
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
