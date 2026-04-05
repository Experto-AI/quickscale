"""QuickScale Configuration Schema Module

Provides dataclasses and validation for quickscale.yml configuration files.
"""

from importlib import import_module
from typing import Any

from quickscale_cli.schema.config_schema import (
    ConfigValidationError,
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
    parse_config,
    validate_config,
)

_LAZY_EXPORTS = {
    "ConfigDelta": ("quickscale_cli.schema.delta", "ConfigDelta"),
    "compute_delta": ("quickscale_cli.schema.delta", "compute_delta"),
    "format_delta": ("quickscale_cli.schema.delta", "format_delta"),
    "ModuleState": ("quickscale_cli.schema.state_schema", "ModuleState"),
    "ProjectState": ("quickscale_cli.schema.state_schema", "ProjectState"),
    "QuickScaleState": ("quickscale_cli.schema.state_schema", "QuickScaleState"),
    "StateError": ("quickscale_cli.schema.state_schema", "StateError"),
    "StateManager": ("quickscale_cli.schema.state_schema", "StateManager"),
}


def __getattr__(name: str) -> Any:
    """Resolve heavy schema re-exports lazily."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)


__all__ = [
    "QuickScaleConfig",
    "ProjectConfig",
    "ModuleConfig",
    "DockerConfig",
    "ConfigValidationError",
    "validate_config",
    "parse_config",
    "QuickScaleState",
    "ProjectState",
    "ModuleState",
    "StateManager",
    "StateError",
    "ConfigDelta",
    "compute_delta",
    "format_delta",
]
