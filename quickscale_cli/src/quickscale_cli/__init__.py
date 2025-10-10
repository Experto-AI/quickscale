"""
QuickScale CLI Package

Command-line interface for QuickScale Django project generator.
Provides simple, focused commands for project creation and management.

MVP Features:
- `quickscale init <project>` - Generate new Django project

Post-MVP Expansion:
- Git subtree workflow helpers
- Module and theme management
- Configuration validation
"""

__version__ = "0.52.0"
__author__ = "Experto AI"
__email__ = "victor@experto.ai"

# Version tuple for programmatic access
# Extract only numeric parts to handle pre-release versions (e.g., "0.52.0-alpha")
_version_parts = __version__.split("-")[0].split(".")
VERSION = tuple(map(int, _version_parts))

__all__ = ["__version__", "VERSION"]
