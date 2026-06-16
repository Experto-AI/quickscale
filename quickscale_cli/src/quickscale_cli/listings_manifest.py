"""Listings module manifest-driven configuration adapter.

Sources defaults from the listings ``module.yml`` manifest and routes
normalization and resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

Option set mirrors the legacy ``_listings_wiring`` function in
``module_wiring_specs.py``:

* ``listings_per_page`` — integer, default ``12``

ADAPTER/OPTION-RESOLUTION ONLY — wiring migration is deferred to a later
phase.  Do NOT register this adapter in ``MANIFEST_ADAPTER_REGISTRY`` until
the wiring migration is complete.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from quickscale_core.manifest.derivation import (
    ModuleDerivationSchema,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LISTINGS_PER_PAGE = 12

LISTINGS_MODULE_OPTION_KEYS = frozenset(
    {
        "listings_per_page",
    }
)

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LISTINGS_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "listings" / "module.yml"


def _load_listings_manifest() -> Any:
    """Load the listings module manifest from ``module.yml``."""
    return load_manifest_from_path(_LISTINGS_MANIFEST_PATH)


def _build_listings_derivation_schema() -> ModuleDerivationSchema:
    """Build a minimal derivation schema for the listings module.

    Listings has no special normalization beyond the generic resolver's
    integer-type handling — all listings-specific logic (int coercion) is
    applied as an adapter-level post-step in ``resolve_listings_module_options``.
    """
    return ModuleDerivationSchema(
        module_name="listings",
        version="1",
        option_derivations={},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_listings_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for listings.

    Defaults are sourced from the listings ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.
    """
    manifest = _load_listings_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_listings_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return listings options with normalized field values.

    Listings has a single option (``listings_per_page``) which passes through
    as-is from the caller; coercion to ``int`` is deferred to resolution so
    that the normalize path remains lightweight, matching the billing pattern.
    """
    return dict(options or {})


def resolve_listings_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge listings options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction, then
    applies the ``int()`` coercion to ``listings_per_page`` that mirrors the
    legacy ``_listings_wiring``.
    """
    manifest = _load_listings_manifest()
    schema = _build_listings_derivation_schema()

    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Apply listings-specific post-resolution coercion (mirrors _listings_wiring).
    resolved["listings_per_page"] = int(resolved["listings_per_page"])

    return resolved


def validate_listings_module_options(
    options: Mapping[str, Any] | None,
) -> list[str]:
    """Return validation issues for listings module options."""
    resolved = resolve_listings_module_options(options)
    issues: list[str] = []

    per_page = resolved.get("listings_per_page")
    try:
        if int(per_page) <= 0:  # type: ignore[arg-type]
            issues.append(
                "modules.listings.listings_per_page must be a positive integer"
            )
    except (TypeError, ValueError):
        issues.append("modules.listings.listings_per_page must be a positive integer")

    return issues


__all__ = [
    "DEFAULT_LISTINGS_PER_PAGE",
    "LISTINGS_MODULE_OPTION_KEYS",
    "default_listings_module_options",
    "normalize_listings_module_options",
    "resolve_listings_module_options",
    "validate_listings_module_options",
]
