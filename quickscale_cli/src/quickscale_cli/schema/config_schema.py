"""Backward-compatible shim for ``quickscale_cli.schema.config_schema``.

The canonical implementation now lives at
:mod:`quickscale_core.schema.config_schema`. This module re-exports the
same public surface (``ConfigValidationError``, ``DockerConfig``,
``ModuleConfig``, ``ProjectConfig``, ``QuickScaleConfig``,
``generate_yaml``, ``parse_config``, ``validate_config``) so that
existing ``from quickscale_cli.schema.config_schema import ...`` calls
keep working without modification.
"""

from quickscale_core.schema.config_schema import (
    AVAILABLE_MODULES,
    ConfigValidationError,
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
    READY_MODULES,
    VALID_DOCKER_KEYS,
    VALID_PROJECT_KEYS,
    VALID_THEMES,
    VALID_TOP_LEVEL_KEYS,
    generate_yaml,
    parse_config,
    validate_config,
)

__all__ = [
    "AVAILABLE_MODULES",
    "ConfigValidationError",
    "DockerConfig",
    "ModuleConfig",
    "ProjectConfig",
    "QuickScaleConfig",
    "READY_MODULES",
    "VALID_DOCKER_KEYS",
    "VALID_PROJECT_KEYS",
    "VALID_THEMES",
    "VALID_TOP_LEVEL_KEYS",
    "generate_yaml",
    "parse_config",
    "validate_config",
]
