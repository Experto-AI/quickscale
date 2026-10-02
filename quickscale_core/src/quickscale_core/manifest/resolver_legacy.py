"""Legacy key alias migration for the manifest-driven module resolver.

Split out of :mod:`quickscale_core.manifest.resolver`; the resolver facade
re-exports these helpers so existing imports keep working.  This module owns
the migration of retired option keys onto their current spellings.
"""

from __future__ import annotations

from typing import Any

from quickscale_core.manifest.derivation import (
    LegacyKeyAlias,
    ModuleDerivationSchema,
)


def _apply_legacy_transform(value: Any, alias: LegacyKeyAlias) -> Any:
    """Apply the value transform declared on a legacy alias.

    Args:
        value: The raw value from the legacy key.
        alias: The legacy alias declaration.

    Returns:
        The transformed value suitable for the current key.
    """
    transform = alias.transform

    if transform == "identity":
        return value

    if transform == "split_comma_list":
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    if transform == "rename_value":
        str_value = str(value).strip()
        return alias.transform_params.get(str_value, value)

    if transform == "negate_boolean":
        if isinstance(value, bool):
            return not value
        return value

    # Unknown transform: pass through
    return value


def _migrate_legacy_keys(
    overrides: dict[str, Any],
    derivation_schema: ModuleDerivationSchema,
) -> dict[str, Any]:
    """Apply legacy key alias migrations to the overrides dict.

    For each legacy alias declared in the derivation schema, if the
    overrides contain the legacy key, the value is transformed and
    moved to the current key.  The legacy key is removed from the
    overrides.

    Args:
        overrides: Mutable copy of user-supplied overrides.
        derivation_schema: The module's derivation schema.

    Returns:
        A dict of legacy-key -> migrated-value pairs that were applied.
    """
    migrations: dict[str, Any] = {}
    all_aliases = derivation_schema.get_all_legacy_aliases()

    for alias in all_aliases:
        if alias.legacy_key in overrides:
            raw_value = overrides.pop(alias.legacy_key)
            migrated_value = _apply_legacy_transform(raw_value, alias)
            # Only set the current key if it wasn't already provided
            # explicitly (explicit current key wins over legacy alias).
            if alias.current_key not in overrides:
                overrides[alias.current_key] = migrated_value
            migrations[alias.legacy_key] = migrated_value

    return migrations
