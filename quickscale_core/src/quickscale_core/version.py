"""
QuickScale Core - Version information for the core package.

This module reads the canonical version from the repository-level `VERSION` file
so the release version can be set in a single place and consumed by all packages.
"""

from __future__ import annotations

from pathlib import Path

__author__ = "Experto AI"
__email__ = "victor@experto.ai"

# Try to import an embedded package-level `_version.py` (generated at build time).
try:
    # This import is local to package; it will work in installed wheels if the
    # build step wrote src/quickscale_core/_version.py
    from ._version import __version__  # type: ignore
except Exception:
    # Fallback to reading the repository-level VERSION file (development)
    _root = Path(__file__).resolve().parents[3]
    _version_file = _root / "VERSION"
    if _version_file.exists():
        __version__ = _version_file.read_text(encoding="utf8").strip()
    else:
        __version__ = "0.0.0"

# Version tuple for programmatic access
# Extract numeric parts to handle pre-release versions (e.g., "0.52.0-alpha")
version_core = __version__.split("-")[0].split(".")
VERSION: tuple[int, int, int] = (
    int(version_core[0]) if len(version_core) > 0 else 0,
    int(version_core[1]) if len(version_core) > 1 else 0,
    int(version_core[2]) if len(version_core) > 2 else 0,
)
