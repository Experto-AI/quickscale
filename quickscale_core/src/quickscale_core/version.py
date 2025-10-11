"""QuickScale Core - Version information for the core package."""

__version__ = "0.52.0"
__author__ = "Experto AI"
__email__ = "victor@experto.ai"

# Version tuple for programmatic access
# Extract numeric parts to handle pre-release versions (e.g., "0.52.0-alpha")
version_parts = __version__.split("-")[0].split(".")
VERSION: tuple[int, int, int] = (
    int(version_parts[0]),
    int(version_parts[1]),
    int(version_parts[2]),
)
