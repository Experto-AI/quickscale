"""Listings module exceptions.

Every listings exception derives from :class:`ListingsError`, so the
module's error surface has one base.  The publish API's validation error
carries the field errors it was raised with.
"""

from __future__ import annotations

__all__ = [
    "ListingPublishConflictError",
    "ListingPublishValidationError",
    "ListingsError",
]


class ListingsError(Exception):
    """Base error for listings module operations."""


class ListingPublishValidationError(ListingsError):
    """Validation error for listing publish API payload"""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid payload")
        self.errors = errors


class ListingPublishConflictError(ListingsError):
    """Conflict error for listing publish API payload"""
