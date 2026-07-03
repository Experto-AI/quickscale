"""Module manifest handling for QuickScale

This package provides schema definitions and loading utilities
for module manifests (module.yml files).

The ``derivation`` sub-module supplies companion dataclasses that describe
how manifest options normalise, validate, and project into Django settings
and module wiring.  Those types are additive to the existing
:class:`ModuleManifest` / :class:`ConfigOption` schema and do not alter
current loader behaviour.

The ``resolver`` sub-module provides the runtime engine that executes
derivation rules: computing defaults, normalizing overrides, validating
resolved values, projecting derived Django settings, and projecting wiring
contributions (apps, middleware, URL includes).  It is additive to the
existing loader and does not replace the legacy contract-file path.

The ``assembler`` sub-module turns a :class:`ResolverResult` into a
:class:`~quickscale_core.module_wiring.ModuleWiringSpec`, with an optional
per-adapter post-resolution hook seam for gnarly cases.

The ``entry_point`` sub-module exposes :func:`build_manifest_wiring_spec`
as the additive public entry point for the manifest-driven path.
"""

from quickscale_core.manifest.assembler import (
    PostResolutionHook,
    assemble_wiring_spec,
)
from quickscale_core.manifest.derivation import (
    DerivedSetting,
    LegacyKeyAlias,
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
    WiringProjection,
    build_schema_from_manifest,
)
from quickscale_core.manifest.entry_point import (
    MANIFEST_ADAPTER_REGISTRY,
    MANAGED_ADAPTER_ORIGINS,
    ManifestAdapterNotFound,
    build_generic_manifest_spec,
    build_manifest_wiring_spec,
    load_module_manifest,
    refresh_managed_adapters,
)
from quickscale_core.manifest.implications import (
    resolve_module_implications,
)
from quickscale_core.manifest.loader import (
    ManifestError,
    load_manifest,
    load_manifest_from_path,
)
from quickscale_core.manifest.required_modules import (
    check_required_module_versions,
    parse_required_module_entry,
)
from quickscale_core.manifest.resolver import (
    ResolverResult,
    resolve_module_config,
)
from quickscale_core.manifest.social_manifest import (  # noqa: F401
    DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST,
    DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
    SOCIAL_LAYOUT_VARIANTS,
    SOCIAL_PAYLOAD_HTTP_STATUS,
    SOCIAL_PAYLOAD_STATUSES,
    SOCIAL_PROVIDER_CATALOG,
    SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_ERROR,
    ResolvedSocialTarget,
    SocialProviderMetadata,
    detect_social_provider,
    get_social_provider_metadata,
    load_social_manifest,
    normalize_social_provider,
    normalize_social_url,
    render_social_managed_init_module,
    render_social_managed_urls_module,
    render_social_managed_views_module,
    resolve_social_target,
    social_payload_status_code,
    social_provider_supports_embeds,
)
from quickscale_core.manifest.schema import (
    MANAGED_FILE_ROOT_PREFIX,
    ConfigOption,
    ContractVintage,
    ImpliesEntry,
    ManagedFileDeclaration,
    ModuleManifest,
    parse_version_tuple,
)

__all__ = [
    "check_required_module_versions",
    "ConfigOption",
    "ContractVintage",
    "DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST",
    "DEFAULT_SOCIAL_PROVIDER_ALLOWLIST",
    "DerivedSetting",
    "ImpliesEntry",
    "LegacyKeyAlias",
    "MANIFEST_ADAPTER_REGISTRY",
    "MANAGED_ADAPTER_ORIGINS",
    "MANAGED_FILE_ROOT_PREFIX",
    "ManagedFileDeclaration",
    "ManifestAdapterNotFound",
    "ManifestError",
    "ModuleDerivationSchema",
    "ModuleManifest",
    "NormalizationRule",
    "OptionDerivation",
    "parse_required_module_entry",
    "parse_version_tuple",
    "PostResolutionHook",
    "ResolvedSocialTarget",
    "ResolverResult",
    "SOCIAL_LAYOUT_VARIANTS",
    "SOCIAL_PAYLOAD_HTTP_STATUS",
    "SOCIAL_PAYLOAD_STATUSES",
    "SOCIAL_PROVIDER_CATALOG",
    "SOCIAL_STATUS_DISABLED",
    "SOCIAL_STATUS_EMPTY",
    "SOCIAL_STATUS_ENABLED",
    "SOCIAL_STATUS_ERROR",
    "SocialProviderMetadata",
    "ValidationRule",
    "WiringProjection",
    "assemble_wiring_spec",
    "build_generic_manifest_spec",
    "build_manifest_wiring_spec",
    "build_schema_from_manifest",
    "detect_social_provider",
    "get_social_provider_metadata",
    "load_manifest",
    "load_manifest_from_path",
    "load_module_manifest",
    "load_social_manifest",
    "normalize_social_provider",
    "normalize_social_url",
    "render_social_managed_init_module",
    "render_social_managed_urls_module",
    "render_social_managed_views_module",
    "refresh_managed_adapters",
    "resolve_module_config",
    "resolve_module_implications",
    "resolve_social_target",
    "social_payload_status_code",
    "social_provider_supports_embeds",
]
