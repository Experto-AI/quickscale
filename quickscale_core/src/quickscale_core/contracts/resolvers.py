"""Shared manifest resolution surface for QuickScale module options.

Owns the manifest loader every option consumer shares
(``load_module_manifest_with_fallback``) and the one generic resolver
non-adapter callers use (``resolve_manifest_module_options``).  A module's
option defaults, normalization, and validation live in its ``module.yml``;
adapter code resolves through the manifest engine via
``quickscale_core.runtime.build_generic_manifest_spec``.  SA217 removed the last
per-module option functions from this surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quickscale_core.manifest.derivation import build_schema_from_manifest
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

from quickscale_core.contracts.module_discovery import (
    resolve_manifest_base_path,
)


def load_module_manifest_with_fallback(module_name: str) -> Any:
    """Load a shipped module's ``module.yml``, source tree first.

    Follows the AF7 discovery contract established by SA109/SA113/SA111a: read
    from the maintainer monorepo's ``quickscale_modules/`` workspace when it is
    present, and fall back to the bundled manifest snapshots shipped inside the
    ``quickscale_core`` wheel when it is not (installed-wheel context).

    Fail-hard is preserved: when neither source resolves, the underlying
    ``ImproperlyConfigured``/load error propagates rather than yielding a
    silently empty or defaulted manifest.
    """
    return load_manifest_from_path(
        resolve_manifest_base_path() / module_name / "module.yml"
    )


def resolve_manifest_module_options(
    module_name: str,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one module's declared option values through the manifest engine.

    The manifest owns the defaults, normalization rules, and validation; this
    is the one path non-adapter callers use to read resolved values (module
    adapters use ``quickscale_core.runtime.build_generic_manifest_spec``).
    Declared normalization rules are applied, so the returned mapping carries
    the manifest's canonical forms.
    """
    manifest = load_module_manifest_with_fallback(module_name)
    schema = build_schema_from_manifest(
        manifest_name=module_name,
        wiring_projections=manifest.wiring_projections,
        derived_settings=manifest.derived_settings,
        option_derivations=manifest.option_derivations,
        version="1",
    )
    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    return dict(result.resolved)


__all__ = [
    "load_module_manifest_with_fallback",
    "resolve_manifest_module_options",
]
