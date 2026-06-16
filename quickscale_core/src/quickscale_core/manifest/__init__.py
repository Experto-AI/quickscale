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
)
from quickscale_core.manifest.entry_point import (
    MANIFEST_ADAPTER_REGISTRY,
    ManifestAdapterNotFound,
    build_manifest_wiring_spec,
)
from quickscale_core.manifest.loader import (
    ManifestError,
    load_manifest,
    load_manifest_from_path,
)
from quickscale_core.manifest.resolver import (
    ResolverResult,
    resolve_module_config,
)
from quickscale_core.manifest.schema import (
    ConfigOption,
    ModuleManifest,
)

__all__ = [
    "ConfigOption",
    "DerivedSetting",
    "LegacyKeyAlias",
    "MANIFEST_ADAPTER_REGISTRY",
    "ManifestAdapterNotFound",
    "ManifestError",
    "ModuleDerivationSchema",
    "ModuleManifest",
    "NormalizationRule",
    "OptionDerivation",
    "PostResolutionHook",
    "ResolverResult",
    "ValidationRule",
    "WiringProjection",
    "assemble_wiring_spec",
    "build_manifest_wiring_spec",
    "load_manifest",
    "load_manifest_from_path",
    "resolve_module_config",
]
