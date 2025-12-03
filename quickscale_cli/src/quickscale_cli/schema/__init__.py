"""QuickScale Configuration Schema Module

Provides dataclasses and validation for quickscale.yml configuration files.
"""

from quickscale_cli.schema.config_schema import (
    ConfigValidationError,
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
    parse_config,
    validate_config,
)
from quickscale_cli.schema.delta import ConfigDelta, compute_delta, format_delta
from quickscale_cli.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)

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
