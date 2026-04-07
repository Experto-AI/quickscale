"""Managed module wiring orchestration for CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from quickscale_cli.commands.module_wiring_specs import build_module_wiring_specs
from quickscale_cli.schema.config_schema import validate_config
from quickscale_cli.schema.state_schema import StateManager
from quickscale_cli.utils.project_identity import (
    ProjectIdentityResolutionError,
    resolve_project_identity,
)
from quickscale_core.module_wiring import write_managed_wiring


class ManagedWiringContextError(ValueError):
    """Raised when managed wiring cannot derive required project context."""


def _discover_embedded_modules(project_path: Path) -> list[str]:
    modules_dir = project_path / "modules"
    if not modules_dir.exists():
        return []

    module_names = [
        path.name
        for path in modules_dir.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    return sorted(module_names)


def _load_options_from_config(project_path: Path) -> dict[str, dict[str, Any]]:
    config_path = project_path / "quickscale.yml"
    if not config_path.exists():
        return {}

    try:
        config = validate_config(config_path.read_text())
    except Exception as error:
        raise ManagedWiringContextError(
            f"Failed to load module options from quickscale.yml: {error}"
        ) from error

    return {
        module_name: (module_config.options or {})
        for module_name, module_config in config.modules.items()
    }


def _load_options_from_state(project_path: Path) -> dict[str, dict[str, Any]]:
    try:
        state = StateManager(project_path).load()
    except Exception as error:
        raise ManagedWiringContextError(
            f"Failed to load module options from .quickscale/state.yml: {error}"
        ) from error

    if state is None:
        return {}

    return {
        module_name: (module_state.options or {})
        for module_name, module_state in state.modules.items()
    }


def _load_module_options(project_path: Path) -> dict[str, dict[str, Any]]:
    options = _load_options_from_state(project_path)
    # Config is source-of-truth for desired options and should override state values.
    options.update(_load_options_from_config(project_path))
    return options


def regenerate_managed_wiring(
    project_path: Path,
    *,
    module_names: list[str] | None = None,
    option_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    project_package: str | None = None,
) -> tuple[bool, str]:
    """Regenerate managed wiring files from module selection + options.

    Returns:
        (success, message)
    """
    package_name = project_package
    if package_name is None:
        try:
            identity = resolve_project_identity(project_path, strict=True)
            package_name = identity.package
        except ProjectIdentityResolutionError as error:
            return False, str(error)
        except Exception as error:
            return False, f"Unable to resolve project identity: {error}"

    if module_names is None:
        selected_modules = _discover_embedded_modules(project_path)
    else:
        selected_modules = sorted(dict.fromkeys(module_names))

    try:
        module_options = _load_module_options(project_path)
    except ManagedWiringContextError as error:
        return False, str(error)

    if option_overrides:
        module_options.update(
            {
                module_name: dict(options)
                for module_name, options in option_overrides.items()
            }
        )

    selected_options = {
        module_name: module_options.get(module_name, {})
        for module_name in selected_modules
    }

    try:
        specs = build_module_wiring_specs(
            selected_options,
            project_package=package_name,
        )
    except ValueError as e:
        return False, f"Unable to build managed wiring specs: {e}"

    package_dir = project_path / package_name
    if not package_dir.exists():
        return (
            False,
            f"Python package directory not found: {package_dir}",
        )

    try:
        write_managed_wiring(package_dir, specs)
    except Exception as error:
        return False, f"Failed to write managed wiring files: {error}"

    return True, "Managed wiring files regenerated"
