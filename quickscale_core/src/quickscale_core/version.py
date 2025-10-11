"""QuickScale Core - Version information for the core package."""

from typing import Tuple

__version__ = "0.52.0"
__author__ = "Experto AI"
__email__ = "victor@experto.ai"

# Version tuple for programmatic access
# Extract numeric parts to handle pre-release versions (e.g., "0.52.0-alpha")
version_parts = __version__.split("-")[0].split(".")
VERSION: Tuple[int, int, int] = tuple(map(int, version_parts))
