"""New-project planner flow for the plan command.

Implementation detail of :mod:`quickscale_cli.commands.plan_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path
from typing import Any


from quickscale_core.schema.config_schema import QuickScaleConfig

import quickscale_core.utils.file_utils as _file_utils
import quickscale_cli.commands._plan_shared as _plan_shared
import quickscale_core.schema.config_schema as _config_schema
import click
import keyword
import pathlib as _pathlib
import quickscale_core.utils.theme_validation as _theme_validation
import re


def _configure_docker() -> tuple[bool, bool, bool]:
    """Interactive Docker configuration"""
    click.echo("\n🐳 Docker Configuration:")
    start = click.confirm("  Start Docker services after apply?", default=True)
    build = click.confirm("  Build Docker images?", default=True) if start else False
    create_superuser = (
        click.confirm(
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
        click.secho(
            "\n❌ Error: PROJECT_SLUG is required for new projects",
            fg="red",
            err=True,
        )
        click.echo("\n💡 Usage examples:", err=True)
        click.echo(
            "   quickscale plan myapp              # Create new project", err=True
        )
        click.echo(
            "   quickscale plan --add              # Add modules to existing", err=True
        )
        click.echo(
            "   quickscale plan --reconfigure      # Reconfigure existing", err=True
        )
        raise click.Abort()

    is_valid, error_message = _file_utils.validate_project_name(slug)
    if not is_valid:
        click.secho(
            f"\n❌ Error: '{slug}' is not a valid project slug",
            fg="red",
            err=True,
        )
        click.echo(f"   {error_message}", err=True)
        raise click.Abort()

    return slug


def _validate_package_name(package_name: str) -> None:
    """Validate explicit project package value."""
    if not package_name:
        raise ValueError("Package name cannot be empty")
    if not package_name.isidentifier():
        raise ValueError("Package name must be a valid Python identifier")
    if keyword.iskeyword(package_name):
        raise ValueError(f"'{package_name}' is a Python keyword and cannot be used")
    if not re.match(r"^[a-z][a-z0-9_]*$", package_name):
        raise ValueError(
            "Package name must start with a lowercase letter and use only lowercase "
            "letters, numbers, and underscores"
        )


def _resolve_project_package(slug: str, explicit_package: str | None) -> str:
    """Resolve package from option or prompt."""
    default_package = slug.replace("-", "_")
    package_name = explicit_package
    if package_name is None:
        package_name = click.prompt(
            "\nPython package name",
            default=default_package,
            show_default=True,
        )

    try:
        _validate_package_name(package_name)
    except ValueError as e:
        click.secho(f"\n❌ Error: {e}", fg="red", err=True)
        raise click.Abort() from e
    return package_name


def _determine_output_path_for_plan(slug: str, output: str | None) -> Path:
    """Determine output path for configuration file."""
    if output:
        return _pathlib.Path(output)
    return _pathlib.Path.cwd() / slug / "quickscale.yml"


def _check_output_path_exists(output_path: Path) -> None:
    """Check if output path exists and confirm overwrite."""
    if not output_path.exists():
        return

    click.secho(
        f"\n⚠️  Configuration file already exists: {output_path}",
        fg="yellow",
    )
    if not click.confirm("Overwrite?", default=False):
        click.echo("❌ Cancelled")
        raise click.Abort()


def _save_config_with_validation(yaml_content: str, output_path: Path) -> None:
    """Validate and save configuration."""
    try:
        _config_schema.validate_config(yaml_content)
    except Exception as e:
        click.secho(f"\n❌ Configuration validation failed: {e}", fg="red", err=True)
        raise click.Abort()

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
            _plan_shared._configure_selected_modules(
                selected_modules,
                module_options,
                new_modules=set(selected_modules),
            )
        )

    selected_modules, module_options, required_modules = (
        _plan_shared._materialize_required_module_configs(
            selected_modules,
            module_options,
        )
    )
    # Run required modules through registry-backed configurators so that
    # new-project flows invoke configurators for required notifications/orgs
    # in the same planning pass.
    if configure_modules and required_modules:
        module_options.update(
            _plan_shared._configure_selected_modules(
                required_modules,
                module_options,
                new_modules=set(required_modules),
            )
        )

    return _config_schema.QuickScaleConfig(
        version="1",
        project=_config_schema.ProjectConfig(
            slug=validated_slug,
            package=resolved_package,
            theme=theme,
        ),
        modules=_plan_shared._build_module_configs(selected_modules, module_options),
        docker=_config_schema.DockerConfig(
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
    click.echo("\n" + "=" * 50)
    click.echo("📋 Configuration Preview:")
    click.echo("=" * 50)
    click.echo(yaml_content)
    click.echo("=" * 50)

    if not click.confirm("\n💾 Save configuration?", default=True):
        click.echo("❌ Cancelled")
        raise click.Abort()

    # Run read-only theme preflight before saving (checks state/recovery
    # files only — the config file is about to be written/overwritten so
    # any existing config content is irrelevant).
    project_root = output_path.parent
    state_path = project_root / ".quickscale" / "state.yml"
    recovery_path = project_root / ".quickscale" / "apply-recovery.yml"
    if state_path.exists() or recovery_path.exists():
        try:
            _theme_validation.validate_theme_preflight(project_root)
        except _theme_validation.ThemeValidationError as exc:
            click.secho(
                "\n❌ Theme validation failed before saving configuration:",
                fg="red",
                err=True,
                bold=True,
            )
            for line in str(exc).splitlines():
                click.echo(f"  • {line}", err=True)
            raise click.Abort()

    _save_config_with_validation(yaml_content, output_path)

    click.secho(f"\n✅ Configuration saved to {output_path}", fg="green", bold=True)

    click.echo("\n📋 Next steps:")
    if output_path.parent.name == validated_slug:
        click.echo(f"  cd {validated_slug}")
        click.echo("  quickscale apply")
    else:
        click.echo(f"  quickscale apply {output_path}")
