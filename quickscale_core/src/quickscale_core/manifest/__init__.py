"""Module manifest handling for QuickScale

This package provides schema definitions and loading utilities
for module manifests (module.yml files).

The ``derivation`` sub-module supplies companion dataclasses that describe
how manifest options normalise, validate, and project into Django settings.
Those types are additive to the existing :class:`ModuleManifest` /
:class:`ConfigOption` schema and do not alter current loader behaviour.

The ``resolver`` sub-module provides the runtime engine that executes
derivation rules: computing defaults, normalizing overrides, validating
resolved values, and projecting derived Django settings.  It is additive
to the existing loader and does not replace the legacy contract-file path.
"""

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    LegacyKeyAlias,
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
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
    "ManifestError",
    "ModuleDerivationSchema",
    "ModuleManifest",
    "NormalizationRule",
    "OptionDerivation",
    "ResolverResult",
    "ValidationRule",
    "load_manifest",
    "load_manifest_from_path",
    "resolve_module_config",
]
