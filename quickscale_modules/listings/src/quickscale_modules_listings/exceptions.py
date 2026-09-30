"""Listings module exceptions.

Every listings exception derives from :class:`ListingsError`, so the
module's error surface has one base.  The publish API's validation error
carries the field errors it was raised with, and the API-facing classes
below also derive from DRF's :class:`~rest_framework.exceptions.APIException`:
they carry the HTTP status and rule 9's stable error code, so the listings
view raises the module's own error and the one QuickScale exception handler
renders the response (Module Conventions rule 9).
"""

from __future__ import annotations

from rest_framework.exceptions import APIException

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


class ListingPublishConflictError(ListingsError, APIException):
    """Conflict error for listing publish API payload.

    A listing with the generated slug already exists in the organization.
    """

    status_code = 409
    default_code = "listing_conflict"


class ListingPublishError(ListingsError, APIException):
    """Raised when a listing publish write fails unexpectedly."""

    status_code = 500
    default_code = "publish_failed"
