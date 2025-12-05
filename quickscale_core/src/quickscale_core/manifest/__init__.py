"""Module manifest handling for QuickScale

This package provides schema definitions and loading utilities
for module manifests (module.yml files).
"""

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
    "ModuleManifest",
    "ManifestError",
    "load_manifest",
    "load_manifest_from_path",
]
