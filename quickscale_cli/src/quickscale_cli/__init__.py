"""
QuickScale CLI package.

Reads the canonical version from the repository-level `VERSION` file so the CLI
stays in sync with other packages when the release is bumped in one place.
"""

from __future__ import annotations

import logging
from pathlib import Path

__author__ = "Experto AI"
__email__ = "victor@experto.ai"

logger = logging.getLogger(__name__)

# Prefer an embedded package-level `_version.py` if it exists (build step).
try:
    from ._version import __version__
except Exception as exc:
    logger.warning(
        "Failed to import embedded CLI version; falling back to VERSION file or 0.0.0: %s",
        exc,
    )
    _root = Path(__file__).resolve().parents[3]
    _version_file = _root / "VERSION"
    if _version_file.exists():
        __version__ = _version_file.read_text(encoding="utf8").strip()
    else:
        __version__ = "0.0.0"

# Version tuple for programmatic access
parts = __version__.split("-")[0].split(".")
VERSION: tuple[int, int, int] = (
    int(parts[0]) if len(parts) > 0 else 0,
    int(parts[1]) if len(parts) > 1 else 0,
    int(parts[2]) if len(parts) > 2 else 0,
)

__all__ = ["__version__", "VERSION"]
