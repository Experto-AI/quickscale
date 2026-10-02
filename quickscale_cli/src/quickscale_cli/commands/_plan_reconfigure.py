"""Reconfigure flow for the plan command.

Implementation detail of :mod:`quickscale_cli.commands.plan_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path


from quickscale_core.schema.config_schema import QuickScaleConfig
from quickscale_core.schema.state_schema import QuickScaleState
import quickscale_cli.commands.plan_command as _plan_command


def _get_project_info_for_reconfig(
    state: QuickScaleState | None,
    existing_config: QuickScaleConfig | None,
    project_path: Path,
) -> tuple[str, str, str]:
    """Get project slug, package, and theme for reconfiguration.

    Returns:
        Tuple of (project_slug, package_name, current_theme)
    """
    if state:
        return state.project.slug, state.project.package, state.project.theme
    if existing_config:
        return (
            existing_config.project.slug,
            existing_config.project.package,
            existing_config.project.theme,
        )
    project_slug = project_path.name
    return project_slug, project_slug.replace("-", "_"), "showcase_react"


def _display_reconfig_modules_status(
    all_existing: list[str], applied_modules: list[str]
) -> None:
    """Display currently configured modules."""
    _plan_command.click.echo("\n📦 Module Configuration:")
    if all_existing:
        _plan_command.click.echo("   Currently configured modules:")
        for module in all_existing:
            status = "(applied)" if module in applied_modules else "(pending)"
            _plan_command.click.secho(f"   ✓ {module} {status}", fg="green")


def _handle_reconfigure(
    project_path: Path,
    existing_config: QuickScaleConfig | None,
    *,
    include_experimental: bool = False,
    configure_modules: bool = False,
) -> None:
    """Handle --reconfigure flag: reconfigure existing project

    Args:
        project_path: Path to the project directory
        existing_config: Current configuration if available

    """
    # Run read-only theme preflight before any mutation.
    try:
        _plan_command.validate_theme_preflight(project_path)
    except _plan_command.ThemeValidationError as exc:
        _plan_command.click.secho(
            "\n❌ Theme validation failed before reconfigure:",
            fg="red",
            err=True,
            bold=True,
        )
        for line in str(exc).splitlines():
            _plan_command.click.echo(f"  • {line}", err=True)
        _plan_command.click.echo(
            "\n💡 Only 'showcase_react' is supported. "
            "Update project.theme in quickscale.yml to 'showcase_react'.",
            err=True,
        )
        raise _plan_command.click.Abort()

    _plan_command.click.echo("\n🔧 Reconfiguring existing project")
    _plan_command.click.echo(f"   Project: {project_path}")

    # Load state for project info
    state_manager = _plan_command.StateManager(project_path)
    state = state_manager.load()

    if state is None and existing_config is None:
        _plan_command.click.secho(
            "\n❌ Cannot reconfigure: No configuration or state found",
            fg="red",
            err=True,
        )
        raise _plan_command.click.Abort()

    # Get current project info
    project_slug, project_package, current_theme = (
        _plan_command._get_project_info_for_reconfig(
            state, existing_config, project_path
        )
    )

    _plan_command.click.echo(f"\n📁 Project: {project_slug}")
    _plan_command.click.echo(f"   Package: {project_package}")
    _plan_command.click.secho(
        f"   Theme: {current_theme} (locked after creation)", fg="cyan"
    )

    # Get applied modules
    applied_modules = _plan_command._get_applied_modules(project_path)
    all_existing = _plan_command._collect_existing_modules(
        project_path, existing_config
    )
    _plan_command._display_reconfig_modules_status(all_existing, applied_modules)

    # Ask if user wants to add more modules
    if _plan_command.click.confirm("\n   Add more modules?", default=False):
        new_modules = _plan_command._select_modules_to_add(
            all_existing,
            include_experimental=include_experimental,
        )
        all_modules = _plan_command._merge_module_names(all_existing, new_modules)
    else:
        new_modules = []
        all_modules = all_existing

    module_options = _plan_command._get_existing_module_options(
        project_path, existing_config
    )
    if configure_modules:
        module_options.update(
            _plan_command._configure_selected_modules(
                all_modules,
                module_options,
                new_modules=set(new_modules),
                allow_reconfigure_existing=True,
            )
        )

    all_modules, module_options, required_modules = (
        _plan_command._materialize_required_module_configs(
            all_modules,
            module_options,
        )
    )
    # Run required modules through registry-backed configurators so that
    # reconfigure flows invoke configurators for required notifications/orgs
    # in the same planning pass.
    if configure_modules and required_modules:
        module_options.update(
            _plan_command._configure_selected_modules(
                required_modules,
                module_options,
                new_modules=set(required_modules),
            )
        )

    # Configure Docker
    docker_start, docker_build, docker_create_superuser = (
        _plan_command._configure_docker()
    )

    # Build configuration
    modules = _plan_command._build_module_configs(all_modules, module_options)

    config = _plan_command.QuickScaleConfig(
        version="1",
        project=_plan_command.ProjectConfig(
            slug=project_slug,
            package=project_package,
            theme=current_theme,
        ),
        modules=modules,
        docker=_plan_command.DockerConfig(
            start=docker_start,
            build=docker_build,
            create_superuser=docker_create_superuser,
        ),
    )

    # Validate the assembled configuration and generate YAML
    yaml_content = _plan_command._validate_existing_project_config_or_abort(config)

    # Preview configuration
    _plan_command.click.echo("\n" + "=" * 50)
    _plan_command.click.echo("📋 Updated Configuration:")
    _plan_command.click.echo("=" * 50)
    _plan_command.click.echo(yaml_content)
    _plan_command.click.echo("=" * 50)

    # Confirm save
    if not _plan_command.click.confirm("\n💾 Save configuration?", default=True):
        _plan_command.click.echo("❌ Cancelled")
        raise _plan_command.click.Abort()

    # Save configuration
    config_path = project_path / "quickscale.yml"
    with open(config_path, "w") as f:
        f.write(yaml_content)

    _plan_command.click.secho(
        f"\n✅ Configuration saved: {config_path}", fg="green", bold=True
    )

    # Next steps
    _plan_command.click.echo("\n📋 Next steps:")
    _plan_command.click.echo("  quickscale apply     # Apply configuration changes")


def _handle_existing_project_mode(
    add_modules: bool,
    reconfigure: bool,
    *,
    include_experimental: bool = False,
    configure_modules: bool = False,
) -> bool:
    """Handle --add and --reconfigure flags for existing projects.

    Returns:
        True if handled (should return from plan), False to continue with new project
    """
    if not add_modules and not reconfigure:
        return False

    try:
        project_path, existing_config = _plan_command._detect_existing_project(
            strict_config_validation=True,
        )
    except _plan_command.ConfigValidationError as error:
        _plan_command._abort_for_invalid_existing_config(
            _plan_command.Path.cwd() / "quickscale.yml", error
        )
    except Exception as error:
        _plan_command._abort_for_invalid_existing_config(
            _plan_command.Path.cwd() / "quickscale.yml", error
        )

    if project_path is None:
        _plan_command.click.secho(
            "\n❌ Not in a QuickScale project directory",
            fg="red",
            err=True,
        )
        _plan_command.click.echo(
            "   Run this command from a directory with quickscale.yml or .quickscale/state.yml",
            err=True,
        )
        raise _plan_command.click.Abort()

    if add_modules:
        _plan_command._handle_add_modules(
            project_path,
            existing_config,
            include_experimental=include_experimental,
            configure_modules=configure_modules,
        )
    else:
        _plan_command._handle_reconfigure(
            project_path,
            existing_config,
            include_experimental=include_experimental,
            configure_modules=configure_modules,
        )

    return True
