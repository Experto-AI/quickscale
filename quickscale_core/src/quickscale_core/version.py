"""QuickScale Core - Scaffolding and utilities for Django project generation."""

__version__ = "0.52.0"
__author__ = "Experto AI"
__email__ = "victor@experto.ai"

# Version tuple for programmatic access
# Extract only numeric parts to handle pre-release versions (e.g., "0.52.0-alpha")
_version_parts = __version__.split("-")[0].split(".")
VERSION = tuple(map(int, _version_parts))
