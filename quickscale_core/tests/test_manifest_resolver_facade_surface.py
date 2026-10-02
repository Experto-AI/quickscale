"""Conformance gate: the split manifest resolver keeps its import surface.

SA231 moved the resolver implementation into sibling ``resolver_*`` modules.
Every name the former ``manifest/resolver.py`` module exposed at import time
must remain importable from the same module path; ``EXPECTED_MODULE_SURFACE``
records that inventory.
"""

import quickscale_core.manifest.resolver as resolver
from quickscale_core.manifest import (
    derivation,
    resolver_derived,
    resolver_legacy,
    resolver_normalization,
    resolver_validation,
    resolver_wiring,
    schema,
)

EXPECTED_MODULE_SURFACE = frozenset(
    {
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
    }
)


def test_facade_preserves_former_module_surface() -> None:
    """Every name the former module exposed stays importable from resolver."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(dir(resolver)))
    assert not missing, f"facade dropped former module names: {missing}"


def test_facade_exports_match_the_former_module_surface() -> None:
    """``__all__`` advertises the full former module surface, not a subset."""
    assert set(resolver.__all__) == EXPECTED_MODULE_SURFACE


def test_facade_reexports_the_original_objects() -> None:
    """Re-exported names stay identical to their defining objects."""
    assert resolver.ModuleManifest is schema.ModuleManifest
    assert resolver.build_schema_from_manifest is derivation.build_schema_from_manifest
    assert (
        resolver._apply_normalization_rule
        is resolver_normalization._apply_normalization_rule
    )
    assert resolver._check_validation_rule is resolver_validation._check_validation_rule
    assert resolver._apply_legacy_transform is resolver_legacy._apply_legacy_transform
    assert (
        resolver._project_derived_setting is resolver_derived._project_derived_setting
    )
    assert (
        resolver._project_wiring_contribution
        is resolver_wiring._project_wiring_contribution
    )
