"""QuickScale Schema Package

Dataclasses, validation, state management, and delta computation for
quickscale.yml and .quickscale/state.yml.

This package is the canonical home for the schema layer. The CLI package
preserves a backward-compatible shim at ``quickscale_cli.schema`` that
re-exports the same names through the same lazy-export pattern.

The unified project state owner lives at :mod:`quickscale_core.project_state`
and re-exports the same names plus :class:`ProjectStateManager` for callers
that want a single entry point over both ``.quickscale/state.yml`` and
``.quickscale/config.yml``.
"""

from typing import Any

from quickscale_core._lazy_exports import PROJECT_STATE_EXPORTS, resolve_lazy_export
from quickscale_core.schema.config_schema import (
    ConfigValidationError,
    DockerConfig,
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
    parse_config,
    validate_config,
)

_LAZY_EXPORTS = {
    "ConfigDelta": ("quickscale_core.schema.delta", "ConfigDelta"),
    "compute_delta": ("quickscale_core.schema.delta", "compute_delta"),
    "format_delta": ("quickscale_core.schema.delta", "format_delta"),
    "ModuleState": ("quickscale_core.schema.state_schema", "ModuleState"),
    "ProjectState": ("quickscale_core.schema.state_schema", "ProjectState"),
    "QuickScaleState": ("quickscale_core.schema.state_schema", "QuickScaleState"),
    "StateError": ("quickscale_core.schema.state_schema", "StateError"),
    "StateManager": ("quickscale_core.schema.state_schema", "StateManager"),
    **PROJECT_STATE_EXPORTS,
}


def __getattr__(name: str) -> Any:
    """Resolve heavy schema re-exports lazily."""
    return resolve_lazy_export(_LAZY_EXPORTS, __name__, name)


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
    "ManagedFileRecord",
    "ConfigDelta",
    "compute_delta",
    "format_delta",
    "ProjectStateManager",
    "ManagedFileHash",
    "VersionDriftWarning",
    "check_version_drift",
    "compute_file_hashes",
    "DEFAULT_MANAGED_WIRING_PATHS",
    "FILE_HASHES_FILENAME",
]
