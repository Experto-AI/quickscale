"""Shared planner helpers for module selection and configuration assembly.

Implementation detail of :mod:`quickscale_cli.commands.plan_command`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from pathlib import Path
from typing import Any


from quickscale_core.schema.config_schema import ModuleConfig, QuickScaleConfig

import quickscale_core.manifest.required_modules as _required_modules
import quickscale_core.schema.state_schema as _state_schema
import quickscale_core.contracts.module_options as _module_options
import quickscale_core.schema.config_schema as _config_schema
import click
import quickscale_cli.commands.module_config as _module_config


def _copy_module_options(
    options: dict[str, Any] | None,
    *,
    module_name: str | None = None,
) -> dict[str, Any]:
    """Return a shallow copy of module options after pruning legacy keys."""
    copied = dict(options or {})
    if module_name is not None:
        copied = _module_options.sanitize_module_options(module_name, copied)
    return copied


def _merge_module_names(*module_groups: list[str]) -> list[str]:
    """Merge module names while preserving first-seen order."""
    merged: list[str] = []
    for group in module_groups:
        for module_name in group:
            if module_name not in merged:
                merged.append(module_name)
    return merged


def _materialize_required_module_configs(
    module_names: list[str],
    module_options: dict[str, dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, Any]], list[str]]:
    """Add explicit config blocks for modules required by the selection."""
    present_module_names = _merge_module_names(
        module_names, list(module_options.keys())
    )
    required_configs = _required_modules.resolve_required_modules(present_module_names)
    if not required_configs:
        return present_module_names, module_options, []

    merged_module_names = _merge_module_names(
        present_module_names,
        list(required_configs.keys()),
    )
    merged_module_options = dict(module_options)
    for module_name, options in required_configs.items():
        merged_module_options[module_name] = _copy_module_options(
            options,
            module_name=module_name,
        )

    return merged_module_names, merged_module_options, list(required_configs.keys())


def _get_existing_module_options(
    project_path: Path,
    existing_config: QuickScaleConfig | None,
) -> dict[str, dict[str, Any]]:
    """Collect existing module option dictionaries from config and applied state."""
    options: dict[str, dict[str, Any]] = {}

    if existing_config is not None:
        for module_name, module_config in existing_config.modules.items():
            options[module_name] = _copy_module_options(
                module_config.options,
                module_name=module_name,
            )

    state = _state_schema.StateManager(project_path).load()
    if state is not None:
        for module_name, module_state in state.modules.items():
            options.setdefault(
                module_name,
                _copy_module_options(module_state.options, module_name=module_name),
            )

    return options


def _build_module_configs(
    module_names: list[str],
    module_options: dict[str, dict[str, Any]],
) -> dict[str, ModuleConfig]:
    """Build `ModuleConfig` objects while preserving known option dictionaries."""
    return {
        module_name: _config_schema.ModuleConfig(
            name=module_name,
            options=_copy_module_options(
                module_options.get(module_name),
                module_name=module_name,
            ),
        )
        for module_name in module_names
    }


def _configure_selected_modules(
    module_names: list[str],
    existing_options: dict[str, dict[str, Any]],
    *,
    new_modules: set[str] | None = None,
    allow_reconfigure_existing: bool = False,
) -> dict[str, dict[str, Any]]:
    """Interactively configure selected modules that expose configurators."""
    configured: dict[str, dict[str, Any]] = {}
    target_new_modules: set[str] = (
        set(module_names) if new_modules is None else new_modules
    )

    if not module_names:
        return configured

    click.echo("\n⚙️  Interactive module configuration enabled")

    for module_name in module_names:
        current_options = _copy_module_options(
            existing_options.get(module_name),
            module_name=module_name,
        )
        configured[module_name] = current_options

        configurator_entry = _module_config.MODULE_CONFIGURATOR_REGISTRY.get(
            module_name
        )
        if configurator_entry is None:
            continue

        should_configure = module_name in target_new_modules
        if not should_configure and allow_reconfigure_existing:
            should_configure = click.confirm(
                f"Reconfigure {module_name} module options?",
                default=False,
            )

        if not should_configure:
            continue

        configured[module_name] = configurator_entry.configure(
            existing_config=current_options
        )

    return configured


def _get_applied_modules(project_path: Path) -> list[str]:
    """Get list of modules already applied to the project

    Returns:
        List of module names that have been applied

    """
    state_manager = _state_schema.StateManager(project_path)
    state = state_manager.load()

    if state is None:
        return []

    return list(state.modules.keys())


def _collect_existing_modules(
    project_path: Path, existing_config: QuickScaleConfig | None
) -> list[str]:
    """Collect all existing modules from state and config."""
    applied_modules = _get_applied_modules(project_path)
    config_modules = list(existing_config.modules.keys()) if existing_config else []
    return list(set(applied_modules + config_modules))
