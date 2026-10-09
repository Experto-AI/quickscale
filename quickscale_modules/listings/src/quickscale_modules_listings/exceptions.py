"""Listings module exceptions.

Every listings exception derives from :class:`ListingsError`, so the
module's error surface has one base.  The publish API's validation error
carries the field errors it was raised with, and the API-facing classes
below declare the HTTP status and rule 9's stable error code; the classes
derive from :class:`Exception` only — the one QuickScale exception handler
in ``quickscale_core.runtime`` renders them (Module Conventions rules 9 and
10).
"""

from __future__ import annotations

__all__ = [
    "ListingPublishConflictError",
    "ListingPublishError",
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
    """Conflict error for listing publish API payload.

    A listing with the generated slug already exists in the organization.
    """

    status_code = 409
    default_code = "listing_conflict"


class ListingPublishError(ListingsError):
    """Raised when a listing publish write fails unexpectedly."""

    status_code = 500
    default_code = "publish_failed"
