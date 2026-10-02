"""Manifest-Driven Module Configuration Resolver

Computes module configuration and wiring inputs from a ``ModuleManifest``
paired with a ``ModuleDerivationSchema`` and optional user-supplied overrides.

This module is the runtime engine that the derivation schema types
(:mod:`quickscale_core.manifest.derivation`) describe but do not execute.
It is the one path every module's declared options flow through; the
per-module contract files it replaced are gone.

The normalization, validation, legacy-alias, derived-setting, and wiring
engines live in the sibling ``resolver_*`` modules; this module owns the
public entry points and re-exports every name that previously lived here, so
all existing ``quickscale_core.manifest.resolver`` imports keep working.

The resolver is intentionally generic — it operates on the declarative
derivation rules rather than module-specific imperative logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Any

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    LegacyKeyAlias,
    ModuleDerivationSchema,
    NormalizationRule,
    ValidationRule,
    WiringProjection,
    build_schema_from_manifest,
)
from quickscale_core.manifest.resolver_derived import (
    _project_all_derived_settings,
    _project_derived_setting,
)
from quickscale_core.manifest.resolver_legacy import (
    _apply_legacy_transform,
    _migrate_legacy_keys,
)
from quickscale_core.manifest.resolver_normalization import (
    _apply_list_rule,
    _apply_normalization_rule,
    _canonical_url,
    _coerce_list_items,
    _is_empty_container,
    _is_supported_list_item,
    _list_chain_declines,
    _normalize_value,
    _slugify,
)
from quickscale_core.manifest.resolver_validation import (
    _check_validation_rule,
    _validate_value,
)
from quickscale_core.manifest.resolver_wiring import (
    _WIRING_ALL_FIELDS,
    _WIRING_LIST_FIELDS,
    _WIRING_URL_FIELDS,
    _coerce_contribution,
    _project_all_wiring,
    _project_wiring_contribution,
)
from quickscale_core.manifest.schema import ManagedFileDeclaration, ModuleManifest


@dataclass(frozen=True)
class ResolverResult:
    """Outcome of resolving a module's configuration through the manifest path.

    Attributes:
        module_name: The module this result is for.
        defaults: Default values for every option declared in the manifest.
        resolved: Merged and normalized option values after applying
            overrides on top of defaults.
        validation_issues: Human-readable descriptions of any validation
            constraints that the resolved values violate.  An empty list
            means all validation rules passed.
        derived_settings: Projected Django settings computed from the
            resolved option values via the derivation schema's
            ``DerivedSetting`` declarations.
        legacy_migrations: Key-value pairs that were migrated from legacy
            alias keys to their current canonical keys during resolution.
        apps: Django app labels contributed by the module's wiring
            projections.  Empty when no ``WiringProjection`` declares an
            ``"apps"`` field.
        middleware: Middleware dotted paths contributed by the module's
            wiring projections.  Empty when no ``WiringProjection`` declares
            a ``"middleware"`` field.
        url_includes: ``(route_prefix, include_path)`` tuples for
            post-home URL includes contributed by wiring projections.
        pre_home_url_includes: ``(route_prefix, include_path)`` tuples for
            pre-home URL includes contributed by wiring projections.
        managed_files: Manifest-declared managed-file declarations threaded
            through from the :class:`ModuleManifest`.  Empty when the
            manifest declares no managed files.  The assembler converts
            these into ``ModuleWiringSpec.managed_files`` entries.
    """

    module_name: str
    defaults: dict[str, Any]
    resolved: dict[str, Any]
    validation_issues: list[str] = field(default_factory=list)
    derived_settings: dict[str, Any] = field(default_factory=dict)
    legacy_migrations: dict[str, Any] = field(default_factory=dict)
    apps: tuple[str, ...] = ()
    middleware: tuple[str, ...] = ()
    url_includes: tuple[tuple[str, str], ...] = ()
    pre_home_url_includes: tuple[tuple[str, str], ...] = ()
    managed_files: tuple[ManagedFileDeclaration, ...] = ()


def normalize_module_option_values(
    manifest: ModuleManifest,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return declared option defaults merged with *overrides*, canonicalized.

    Applies the manifest's per-option normalization rules to every declared
    option, exactly as :func:`resolve_module_config` does, without validating or
    projecting anything.  Callers that need an option's canonical value — the
    option-validation engine, for example — share this one implementation
    instead of re-deriving it.

    Only names the manifest declares are considered; undeclared keys are
    another layer's concern.

    Args:
        manifest: The loaded module manifest.
        overrides: Optional supplied option values.

    Returns:
        A mapping of every declared option name to its canonical value.
    """
    schema = build_schema_from_manifest(
        manifest_name=manifest.name,
        option_derivations=manifest.option_derivations,
    )
    resolved: dict[str, Any] = manifest.get_defaults()
    if overrides:
        for key, value in overrides.items():
            if key in resolved:
                resolved[key] = value
    for option_key in list(resolved.keys()):
        option_derivation = schema.get_option_derivation(option_key)
        resolved[option_key] = _normalize_value(
            resolved[option_key],
            option_key,
            option_derivation,
            schema.shared_normalization_rules,
        )
    return resolved


def _is_url_include_pair(item: Any) -> bool:
    """Return whether *item* is a ``[route, include]`` pair of strings."""
    return (
        isinstance(item, (list, tuple))
        and len(item) == 2
        and all(isinstance(part, str) for part in item)
    )


def _url_projection_items(
    projection: WiringProjection, resolved: dict[str, Any]
) -> tuple[str, list[Any]] | None:
    """Return the option key and runtime items of a direct URL projection.

    Only a direct projection onto a URL field can feed malformed values into
    the wiring result; every other projection is ignored here.
    """
    if (
        projection.wiring_field not in _WIRING_URL_FIELDS
        or projection.derivation_type != "direct"
    ):
        return None
    option_key = projection.expression.get("option")
    if not isinstance(option_key, str) or option_key not in resolved:
        return None
    value = resolved[option_key]
    if value is None:
        return None
    items = list(value) if isinstance(value, (list, tuple)) else [value]
    return option_key, items


def _url_projection_issues(
    derivation_schema: ModuleDerivationSchema, resolved: dict[str, Any]
) -> list[str]:
    """Return issues for direct URL projections whose values are not pairs.

    A direct projection reads an option's runtime value; when that value is a
    non-``None`` item that is not a ``[route, include]`` pair of strings the
    contribution would be silently discarded, so resolution records the issue
    for the boundaries to refuse.
    """
    issues: list[str] = []
    for projection in derivation_schema.get_all_wiring_projections():
        target = _url_projection_items(projection, resolved)
        if target is None:
            continue
        option_key, items = target
        for index, item in enumerate(items):
            if _is_url_include_pair(item):
                continue
            issues.append(
                f"modules.{derivation_schema.module_name}.{option_key} cannot "
                f"feed {projection.wiring_field}: item {index} is not a "
                "[route, include] pair of strings"
            )
    return issues


def resolve_module_config(
    manifest: ModuleManifest,
    derivation_schema: ModuleDerivationSchema,
    overrides: dict[str, Any] | None = None,
) -> ResolverResult:
    """Compute module configuration from manifest + derivation schema + overrides.

    This is the primary entry point for the manifest-driven configuration
    path.  It performs the following steps:

    1. Extract default values from the manifest.
    2. Apply legacy key alias migrations to the overrides.
    3. Merge overrides on top of defaults.
    4. Normalize each resolved value using shared and per-option rules.
    5. Validate each resolved value against shared and per-option rules.
    6. Project derived Django settings from the resolved values.

    The manifest engine is the only path: the per-module contract-file logic
    it replaced is gone.

    Args:
        manifest: The loaded module manifest.
        derivation_schema: The module's derivation schema describing how
            options normalize, validate, and project into settings.
        overrides: Optional user-supplied option overrides (e.g. from
            ``quickscale.yml``).  ``None`` is treated as empty.

    Returns:
        A :class:`ResolverResult` containing defaults, resolved values,
        validation issues, derived settings, and any legacy migrations
        that were applied.
    """
    # Step 1: Extract defaults from the manifest
    defaults = manifest.get_defaults()

    # Step 2: Work on a mutable copy of overrides and apply legacy migrations
    working_overrides = dict(overrides or {})
    legacy_migrations = _migrate_legacy_keys(working_overrides, derivation_schema)

    # Step 3: Merge overrides on top of defaults
    resolved = dict(defaults)
    resolved.update(working_overrides)

    # Step 4: Normalize each resolved value
    for option_key in list(resolved.keys()):
        option_derivation = derivation_schema.get_option_derivation(option_key)
        resolved[option_key] = _normalize_value(
            resolved[option_key],
            option_key,
            option_derivation,
            derivation_schema.shared_normalization_rules,
        )

    # Step 5: Validate each resolved value
    validation_issues: list[str] = []
    for option_key in sorted(resolved.keys()):
        option_derivation = derivation_schema.get_option_derivation(option_key)
        issues = _validate_value(
            resolved[option_key],
            option_key,
            option_derivation,
            derivation_schema.shared_validation_rules,
        )
        validation_issues.extend(issues)

    # Step 6: Project derived Django settings
    derived_settings = _project_all_derived_settings(
        manifest, derivation_schema, resolved
    )

    # Step 7: Project wiring contributions (apps, middleware, url_includes,
    # pre_home_url_includes) from the derivation schema's wiring projections.
    wiring = _project_all_wiring(derivation_schema, resolved)
    validation_issues.extend(_url_projection_issues(derivation_schema, resolved))

    def _to_str_tuple(items: list[Any]) -> tuple[str, ...]:
        return tuple(str(x) for x in items)

    def _to_url_tuple(items: list[Any]) -> tuple[tuple[str, str], ...]:
        return tuple((str(a), str(b)) for a, b in items)

    return ResolverResult(
        module_name=manifest.name,
        defaults=defaults,
        resolved=resolved,
        validation_issues=validation_issues,
        derived_settings=derived_settings,
        legacy_migrations=legacy_migrations,
        apps=_to_str_tuple(wiring["apps"]),
        middleware=_to_str_tuple(wiring["middleware"]),
        url_includes=_to_url_tuple(wiring["url_includes"]),
        pre_home_url_includes=_to_url_tuple(wiring["pre_home_url_includes"]),
        managed_files=tuple(manifest.managed_files.values()),
    )


__all__ = [
    "Any",
    "DerivedSetting",
    "LegacyKeyAlias",
    "ManagedFileDeclaration",
    "Mapping",
    "ModuleDerivationSchema",
    "ModuleManifest",
    "NormalizationRule",
    "ResolverResult",
    "ValidationRule",
    "WiringProjection",
    "_WIRING_ALL_FIELDS",
    "_WIRING_LIST_FIELDS",
    "_WIRING_URL_FIELDS",
    "_apply_legacy_transform",
    "_apply_list_rule",
    "_apply_normalization_rule",
    "_canonical_url",
    "_check_validation_rule",
    "_coerce_contribution",
    "_coerce_list_items",
    "_is_empty_container",
    "_is_supported_list_item",
    "_list_chain_declines",
    "_migrate_legacy_keys",
    "_normalize_value",
    "_project_all_derived_settings",
    "_project_all_wiring",
    "_project_derived_setting",
    "_project_wiring_contribution",
    "_slugify",
    "_url_projection_issues",
    "_validate_value",
    "annotations",
    "build_schema_from_manifest",
    "dataclass",
    "field",
    "normalize_module_option_values",
    "re",
    "resolve_module_config",
]
