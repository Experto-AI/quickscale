"""Module manifest handling for QuickScale

This package provides schema definitions and loading utilities
for module manifests (module.yml files).

The ``derivation`` sub-module supplies companion dataclasses that describe
how manifest options normalise, validate, and project into Django settings.
Those types are additive to the existing :class:`ModuleManifest` /
:class:`ConfigOption` schema and do not alter current loader behaviour.
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
    "ValidationRule",
    "load_manifest",
    "load_manifest_from_path",
]
