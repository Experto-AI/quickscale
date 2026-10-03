"""Plan command for interactive project configuration

Implements `quickscale plan <name>` - interactive wizard that creates quickscale.yml
Also supports `--add` and `--reconfigure` flags for existing projects.

The implementation lives in private sibling modules grouped by concern
(``_plan_shared``, ``_plan_validation``, ``_plan_new_project``, ``_plan_add``,
``_plan_reconfigure``); this module owns the public command surface, re-exports public names for
unchanged import paths, and resolves collaborators through the sibling modules
that define them (decisions.md, Split-Facade Seams).
"""

import click as click

from quickscale_core.contracts.module_options import (
    sanitize_module_options as sanitize_module_options,
)
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback as load_module_manifest_with_fallback,
)
from quickscale_core.manifest.option_validation import (
    validate_module_options as validate_module_options,
)
from quickscale_cli.commands.apply_support import (
    notifications_adapter_module as notifications_adapter_module,
)
from quickscale_cli.commands.module_config import (
    MODULE_CONFIGURATOR_REGISTRY as MODULE_CONFIGURATOR_REGISTRY,
)
from quickscale_cli.commands.plan_selection import (
    AVAILABLE_THEMES as AVAILABLE_THEMES,
)
from quickscale_core.contracts.module_catalog import (
    ModuleCatalogEntry as ModuleCatalogEntry,
    get_module_readiness_reason as get_module_readiness_reason,
)
from quickscale_core.manifest.required_modules import (
    resolve_required_modules as resolve_required_modules,
)
from quickscale_core.schema.config_schema import (
    ConfigValidationError as ConfigValidationError,
    DockerConfig as DockerConfig,
    ModuleConfig as ModuleConfig,
    ProjectConfig as ProjectConfig,
    QuickScaleConfig as QuickScaleConfig,
    generate_yaml as generate_yaml,
    validate_config as validate_config,
)
from quickscale_core.schema.state_schema import (
    QuickScaleState as QuickScaleState,
    StateManager as StateManager,
)
from quickscale_core.utils.file_utils import (
    validate_project_name as validate_project_name,
)
from quickscale_core.utils.theme_validation import (
    ThemeValidationError as ThemeValidationError,
    validate_theme_preflight as validate_theme_preflight,
)
import quickscale_cli.commands.plan_selection as _plan_selection
import quickscale_core.schema.config_schema as _config_schema
import quickscale_cli.commands._plan_new_project as _plan_new_project
import quickscale_cli.commands._plan_reconfigure as _plan_reconfigure


@click.command()
@click.argument("slug", required=False, metavar="PROJECT_SLUG")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for quickscale.yml (default: <slug>/quickscale.yml)",
)
@click.option(
    "--package",
    type=str,
    help="Explicit Python package name (default: slug with '-' replaced by '_')",
)
@click.option(
    "--add",
    "add_modules",
    is_flag=True,
    help="Add modules to existing project",
)
@click.option(
    "--reconfigure",
    is_flag=True,
    help="Reconfigure existing project options",
)
@click.option(
    "--include-experimental",
    is_flag=True,
    help="Show non-public module inventory entries in the picker",
)
@click.option(
    "--configure-modules",
    is_flag=True,
    help="Interactively configure supported module options during planning",
)
def plan(
    slug: str | None,
    output: str | None,
    package: str | None,
    add_modules: bool,
    reconfigure: bool,
    include_experimental: bool,
    configure_modules: bool,
) -> None:
    """
    Create or update a project configuration via interactive wizard.

    Creates a quickscale.yml file with your project configuration.
    Run 'quickscale apply' afterwards to generate or update the project.

    \b
    Examples:
      quickscale plan my-app                # Create new project config
      quickscale plan my-app --package my_app
      quickscale plan my-app -o ./config.yml  # Custom output path
      quickscale plan --add                # Add modules to existing project
      quickscale plan --reconfigure        # Reconfigure existing project

    \b
    New project wizard:
    - Theme selection (showcase_react)
      - Module selection (auth, blog, listings, etc.)
            - Docker configuration (start, build, create superuser)

    \b
    Existing project modes:
      --add          Add new modules to existing configuration
      --reconfigure  Modify Docker options and add modules
    """
    # Handle --add or --reconfigure flags
    if _plan_reconfigure._handle_existing_project_mode(
        add_modules,
        reconfigure,
        include_experimental=include_experimental,
        configure_modules=configure_modules,
    ):
        return

    # Validate and prepare for new project
    validated_slug = _plan_new_project._validate_new_project_slug(slug)
    resolved_package = _plan_new_project._resolve_project_package(
        validated_slug, package
    )

    click.echo("\n🚀 QuickScale Project Planner")
    click.echo(f"   Creating configuration for: {validated_slug}")
    click.echo(f"   Package: {resolved_package}")

    output_path = _plan_new_project._determine_output_path_for_plan(
        validated_slug, output
    )
    _plan_new_project._check_output_path_exists(output_path)

    # Interactive wizard
    theme = _plan_selection._select_theme()
    selected_modules = _plan_selection._select_modules(
        include_experimental=include_experimental
    )
    docker_start, docker_build, docker_create_superuser = (
        _plan_new_project._configure_docker()
    )

    config = _plan_new_project._build_new_project_config(
        validated_slug,
        resolved_package,
        theme,
        selected_modules,
        docker_start,
        docker_build,
        docker_create_superuser,
        configure_modules=configure_modules,
    )

    yaml_content = _config_schema.generate_yaml(config)
    _plan_new_project._preview_and_save_new_config(
        output_path, validated_slug, yaml_content
    )
