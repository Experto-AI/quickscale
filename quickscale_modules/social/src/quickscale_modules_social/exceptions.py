"""Social module exceptions.

Every social exception derives from :class:`SocialError`, so the module's
error surface has one base.  ``contracts.py`` re-exports
``SocialConfigurationError`` for the callers that have always imported it
from there.
"""

from __future__ import annotations

__all__ = [
    "SocialConfigurationError",
    "SocialError",
]


class SocialError(Exception):
    """Base error for social module operations."""


class SocialConfigurationError(SocialError):
    """Raised when the runtime social settings are invalid."""
