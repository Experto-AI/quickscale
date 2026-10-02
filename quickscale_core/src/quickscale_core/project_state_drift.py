"""Module-version drift detection between state and config.

``check_version_drift`` compares the module versions recorded in
``state.yml`` with the installed versions tracked in ``config.yml``. It was
previously defined in ``project_state.py``; the unified owner stays
importable from ``quickscale_core.project_state``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quickscale_core.config.module_config import normalize_installed_version
from quickscale_core.project_state_records import VersionDriftWarning

if TYPE_CHECKING:
    from quickscale_core.config.module_config import ModuleConfig
    from quickscale_core.schema.state_schema import QuickScaleState


def check_version_drift(
    state: QuickScaleState | None,
    config: ModuleConfig | None,
) -> list[VersionDriftWarning]:
    """Return a list of module-version disagreements between state and config.

    Only modules present in both sources produce a warning; modules that
    exist in only one source are intentionally ignored here because that
    situation is already reported through ``StateManager.verify_filesystem``
    and the existing delta computations. Both ``state`` and ``config`` may
    be ``None`` to indicate missing files; in that case the result is empty.

    Args:
        state: Loaded :class:`QuickScaleState` (or ``None`` if no state file).
        config: Loaded :class:`ModuleConfig` (or ``None`` if no config file).

    Returns:
        List of :class:`VersionDriftWarning` entries for modules whose
        normalized version disagrees between the two sources.

    """
    if state is None or config is None:
        return []

    warnings: list[VersionDriftWarning] = []
    state_modules = state.modules or {}
    config_modules = config.modules or {}

    common = sorted(set(state_modules) & set(config_modules))
    for module_name in common:
        state_version = normalize_installed_version(state_modules[module_name].version)
        config_info = config_modules[module_name]
        config_version = normalize_installed_version(config_info.installed_version)

        if state_version == config_version:
            continue

        warnings.append(
            VersionDriftWarning(
                module=module_name,
                state_version=state_version,
                config_version=config_version,
            )
        )

    return warnings
