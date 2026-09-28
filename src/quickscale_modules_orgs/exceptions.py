"""Organizations module exceptions.

Every organizations exception derives from :class:`OrgsError`, so the
module's error surface has one base.  ``current_org.py`` re-exports
``CurrentOrgError`` for the callers that import it from the current-org
contract module.
"""

from __future__ import annotations

__all__ = [
    "CurrentOrgError",
    "OrgsError",
]


class OrgsError(Exception):
    """Base error for organizations module operations."""


class CurrentOrgError(OrgsError):
    """Raised when strict org access is required but no org context is set."""
