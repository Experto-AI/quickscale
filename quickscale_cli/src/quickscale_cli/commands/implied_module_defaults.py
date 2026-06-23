"""Shim for materializing implicit module configs in CLI flows.

This module is a transitional shim that forwards to the canonical
:func:`quickscale_core.manifest.implications.resolve_module_implications`.
The shim will be removed in T2.4 when all callers have been migrated to
call the core resolver directly.
"""

from collections.abc import Collection
from typing import Any

from quickscale_core.manifest.implications import resolve_module_implications


def get_implied_module_default_configs(
    module_names: Collection[str],
) -> dict[str, dict[str, Any]]:
    """Return module config blocks that should be made explicit automatically.

    Delegates to :func:`quickscale_core.manifest.implications.resolve_module_implications`
    which reads ``implies`` blocks from each ``module.yml`` manifest.

    Args:
        module_names: Collection of module names already selected.

    Returns:
        Dict mapping newly implied module names to their default config dicts.
    """
    return resolve_module_implications(module_names)
