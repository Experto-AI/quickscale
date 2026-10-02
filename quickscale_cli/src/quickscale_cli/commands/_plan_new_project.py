"""New-project planner flow for the plan command.

Implementation detail of :mod:`quickscale_cli.commands.plan_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path
from typing import Any


from quickscale_core.schema.config_schema import QuickScaleConfig
import quickscale_cli.commands.plan_command as _plan_command


def _configure_docker() -> tuple[bool, bool, bool]:
    """Interactive Docker configuration"""
    _plan_command.click.echo("\n🐳 Docker Configuration:")
    start = _plan_command.click.confirm(
        "  Start Docker services after apply?", default=True
    )
    build = (
        _plan_command.click.confirm("  Build Docker images?", default=True)
        if start
        else False
    )
    create_superuser = (
        _plan_command.click.confirm(
            "  Create Django superuser on first startup?",
            default=False,
        )
        if start
        else False
    )
    return start, build, create_superuser


def _validate_new_project_slug(slug: str | None) -> str:
    """Validate project slug for new projects.

    Returns:
        Validated project slug

    Raises:
        _plan_command.click.Abort: If name is invalid
    """
    if not slug:
        _plan_command.click.secho(
            "\n❌ Error: PROJECT_SLUG is required for new projects",
            fg="red",
            err=True,
        )
        _plan_command.click.echo("\n💡 Usage examples:", err=True)
        _plan_command.click.echo(
            "   quickscale plan myapp              # Create new project", err=True
        )
        _plan_command.click.echo(
            "   quickscale plan --add              # Add modules to existing", err=True
        )
        _plan_command.click.echo(
            "   quickscale plan --reconfigure      # Reconfigure existing", err=True
        )
        raise _plan_command.click.Abort()

    is_valid, error_message = _plan_command.validate_project_name(slug)
    if not is_valid:
        _plan_command.click.secho(
            f"\n❌ Error: '{slug}' is not a valid project slug",
            fg="red",
            err=True,
        )
        _plan_command.click.echo(f"   {error_message}", err=True)
        raise _plan_command.click.Abort()

    return slug


def _validate_package_name(package_name: str) -> None:
    """Validate explicit project package value."""
    if not package_name:
        raise ValueError("Package name cannot be empty")
    if not package_name.isidentifier():
        raise ValueError("Package name must be a valid Python identifier")
    if _plan_command.keyword.iskeyword(package_name):
        raise ValueError(f"'{package_name}' is a Python keyword and cannot be used")
    if not _plan_command.re.match(r"^[a-z][a-z0-9_]*$", package_name):
        raise ValueError(
            "Package name must start with a lowercase letter and use only lowercase "
            "letters, numbers, and underscores"
        )


def _resolve_project_package(slug: str, explicit_package: str | None) -> str:
    """Resolve package from option or prompt."""
    default_package = slug.replace("-", "_")
    package_name = explicit_package
    if package_name is None:
        package_name = _plan_command.click.prompt(
            "\nPython package name",
            default=default_package,
            show_default=True,
        )

    try:
        _plan_command._validate_package_name(package_name)
    except ValueError as e:
        _plan_command.click.secho(f"\n❌ Error: {e}", fg="red", err=True)
        raise _plan_command.click.Abort() from e
    return package_name


def _determine_output_path_for_plan(slug: str, output: str | None) -> Path:
    """Determine output path for configuration file."""
    if output:
        return _plan_command.Path(output)
    return _plan_command.Path.cwd() / slug / "quickscale.yml"


def _check_output_path_exists(output_path: Path) -> None:
    """Check if output path exists and confirm overwrite."""
    if not output_path.exists():
        return

    _plan_command.click.secho(
        f"\n⚠️  Configuration file already exists: {output_path}",
        fg="yellow",
    )
    if not _plan_command.click.confirm("Overwrite?", default=False):
        _plan_command.click.echo("❌ Cancelled")
        raise _plan_command.click.Abort()


def _save_config_with_validation(yaml_content: str, output_path: Path) -> None:
    """Validate and save configuration."""
    try:
        _plan_command.validate_config(yaml_content)
    except Exception as e:
        _plan_command.click.secho(
            f"\n❌ Configuration validation failed: {e}", fg="red", err=True
        )
        raise _plan_command.click.Abort()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(yaml_content)


def _build_new_project_config(
    validated_slug: str,
    resolved_package: str,
    theme: str,
    selected_modules: list[str],
    docker_start: bool,
    docker_build: bool,
    docker_create_superuser: bool,
    *,
    configure_modules: bool,
) -> QuickScaleConfig:
    """Assemble a new-project configuration after interactive selection."""
    module_options: dict[str, dict[str, Any]] = {
        module_name: {} for module_name in selected_modules
    }
    if configure_modules:
        module_options.update(
            _plan_command._configure_selected_modules(
                selected_modules,
                module_options,
                new_modules=set(selected_modules),
            )
        )

    selected_modules, module_options, required_modules = (
        _plan_command._materialize_required_module_configs(
            selected_modules,
            module_options,
        )
    )
    # Run required modules through registry-backed configurators so that
    # new-project flows invoke configurators for required notifications/orgs
    # in the same planning pass.
    if configure_modules and required_modules:
        module_options.update(
            _plan_command._configure_selected_modules(
                required_modules,
                module_options,
                new_modules=set(required_modules),
            )
        )

    return _plan_command.QuickScaleConfig(
        version="1",
        project=_plan_command.ProjectConfig(
            slug=validated_slug,
            package=resolved_package,
            theme=theme,
        ),
        modules=_plan_command._build_module_configs(selected_modules, module_options),
        docker=_plan_command.DockerConfig(
            start=docker_start,
            build=docker_build,
            create_superuser=docker_create_superuser,
        ),
    )


def _preview_and_save_new_config(
    output_path: Path,
    validated_slug: str,
    yaml_content: str,
) -> None:
    """Preview, preflight, and save a new-project configuration."""
    _plan_command.click.echo("\n" + "=" * 50)
    _plan_command.click.echo("📋 Configuration Preview:")
    _plan_command.click.echo("=" * 50)
    _plan_command.click.echo(yaml_content)
    _plan_command.click.echo("=" * 50)

    if not _plan_command.click.confirm("\n💾 Save configuration?", default=True):
        _plan_command.click.echo("❌ Cancelled")
        raise _plan_command.click.Abort()

    # Run read-only theme preflight before saving (checks state/recovery
    # files only — the config file is about to be written/overwritten so
    # any existing config content is irrelevant).
    project_root = output_path.parent
    state_path = project_root / ".quickscale" / "state.yml"
    recovery_path = project_root / ".quickscale" / "apply-recovery.yml"
    if state_path.exists() or recovery_path.exists():
        try:
            _plan_command.validate_theme_preflight(project_root)
        except _plan_command.ThemeValidationError as exc:
            _plan_command.click.secho(
                "\n❌ Theme validation failed before saving configuration:",
                fg="red",
                err=True,
                bold=True,
            )
            for line in str(exc).splitlines():
                _plan_command.click.echo(f"  • {line}", err=True)
            raise _plan_command.click.Abort()

    _plan_command._save_config_with_validation(yaml_content, output_path)

    _plan_command.click.secho(
        f"\n✅ Configuration saved to {output_path}", fg="green", bold=True
    )

    _plan_command.click.echo("\n📋 Next steps:")
    if output_path.parent.name == validated_slug:
        _plan_command.click.echo(f"  cd {validated_slug}")
        _plan_command.click.echo("  quickscale apply")
    else:
        _plan_command.click.echo(f"  quickscale apply {output_path}")
