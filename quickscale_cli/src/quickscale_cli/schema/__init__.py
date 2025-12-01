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

__all__ = [
    "QuickScaleConfig",
    "ProjectConfig",
    "ModuleConfig",
    "DockerConfig",
    "ConfigValidationError",
    "validate_config",
    "parse_config",
]
