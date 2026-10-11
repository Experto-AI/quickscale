"""Module-owned backups manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    ModuleWiringSpec,
    build_generic_manifest_spec,
)


def _backups_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for backups from its manifest contract.

    The manifest declares every option's default, normalization rule, check,
    and projection, so the generic boundary produces the complete spec with
    no post-resolution hook: the module owns no public URL mount, contributes
    no composite setting, and its integer, boolean, and string settings are
    already canonical when the boundary projects them.
    """
    del project_package

    return build_generic_manifest_spec("backups", options)


def get_manifest_adapter() -> Any:
    """Return the backups module's manifest adapter callable."""
    return _backups_manifest_adapter
