"""Plan command for interactive project configuration

Implements `quickscale plan <name>` - interactive wizard that creates quickscale.yml
Also supports `--add` and `--reconfigure` flags for existing projects.

The implementation lives in private sibling modules grouped by concern
(``_plan_shared``, ``_plan_validation``, ``_plan_new_project``, ``_plan_add``,
``_plan_reconfigure``); this module owns the public command surface and
re-exports every name that previously lived here (Module Conventions rule 28),
so existing ``quickscale_cli.commands.plan_command`` imports and test patch
targets keep working unchanged.
"""

import keyword as keyword
import re as re
from pathlib import Path as Path
from typing import Any as Any

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
    _format_module_choice as _format_module_choice,
    _get_module_choices as _get_module_choices,
    _get_theme_by_index as _get_theme_by_index,
    _get_theme_by_name as _get_theme_by_name,
    _parse_module_choice as _parse_module_choice,
    _parse_module_selection as _parse_module_selection,
    _select_modules as _select_modules,
    _select_theme as _select_theme,
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
from quickscale_cli.commands._plan_shared import (
    _build_module_configs as _build_module_configs,
    _collect_existing_modules as _collect_existing_modules,
    _configure_selected_modules as _configure_selected_modules,
    _copy_module_options as _copy_module_options,
    _get_applied_modules as _get_applied_modules,
    _get_existing_module_options as _get_existing_module_options,
    _materialize_required_module_configs as _materialize_required_module_configs,
    _merge_module_names as _merge_module_names,
)
from quickscale_cli.commands._plan_validation import (
    _abort_for_invalid_existing_config as _abort_for_invalid_existing_config,
    _detect_existing_project as _detect_existing_project,
    _validate_existing_project_config_or_abort as _validate_existing_project_config_or_abort,
    _validate_existing_project_notifications_or_abort as _validate_existing_project_notifications_or_abort,
)
from quickscale_cli.commands._plan_new_project import (
    _build_new_project_config as _build_new_project_config,
    _check_output_path_exists as _check_output_path_exists,
    _configure_docker as _configure_docker,
    _determine_output_path_for_plan as _determine_output_path_for_plan,
    _preview_and_save_new_config as _preview_and_save_new_config,
    _resolve_project_package as _resolve_project_package,
    _save_config_with_validation as _save_config_with_validation,
    _validate_new_project_slug as _validate_new_project_slug,
    _validate_package_name as _validate_package_name,
)
from quickscale_cli.commands._plan_add import (
    _build_add_config as _build_add_config,
    _display_available_modules as _display_available_modules,
    _display_current_modules as _display_current_modules,
    _get_available_modules as _get_available_modules,
    _get_module_by_index_from_available as _get_module_by_index_from_available,
    _get_module_by_name_from_available as _get_module_by_name_from_available,
    _handle_add_modules as _handle_add_modules,
    _parse_add_module_selection as _parse_add_module_selection,
    _prepare_added_module_data as _prepare_added_module_data,
    _preview_and_save_added_config as _preview_and_save_added_config,
    _select_modules_to_add as _select_modules_to_add,
)
from quickscale_cli.commands._plan_reconfigure import (
    _display_reconfig_modules_status as _display_reconfig_modules_status,
    _get_project_info_for_reconfig as _get_project_info_for_reconfig,
    _handle_existing_project_mode as _handle_existing_project_mode,
    _handle_reconfigure as _handle_reconfigure,
)


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
    if _handle_existing_project_mode(
        add_modules,
        reconfigure,
        include_experimental=include_experimental,
        configure_modules=configure_modules,
    ):
        return

    # Validate and prepare for new project
    validated_slug = _validate_new_project_slug(slug)
    resolved_package = _resolve_project_package(validated_slug, package)

    click.echo("\n🚀 QuickScale Project Planner")
    click.echo(f"   Creating configuration for: {validated_slug}")
    click.echo(f"   Package: {resolved_package}")

    output_path = _determine_output_path_for_plan(validated_slug, output)
    _check_output_path_exists(output_path)

    # Interactive wizard
    theme = _select_theme()
    selected_modules = _select_modules(include_experimental=include_experimental)
    docker_start, docker_build, docker_create_superuser = _configure_docker()

    config = _build_new_project_config(
        validated_slug,
        resolved_package,
        theme,
        selected_modules,
        docker_start,
        docker_build,
        docker_create_superuser,
        configure_modules=configure_modules,
    )

    yaml_content = generate_yaml(config)
    _preview_and_save_new_config(output_path, validated_slug, yaml_content)
