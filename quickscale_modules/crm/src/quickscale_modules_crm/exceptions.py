"""CRM module exceptions.

Every CRM exception derives from :class:`CrmError`, so the module's error
surface has one base.
"""

from __future__ import annotations

__all__ = ["CrmError"]


class CrmError(Exception):
    """Base error for CRM module operations."""
