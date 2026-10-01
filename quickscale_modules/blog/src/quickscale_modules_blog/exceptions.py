"""Blog module exceptions.

Every blog exception derives from :class:`BlogError`, so the module's error
surface has one base.  The publish API's validation errors carry the field
errors they were raised with, and the API-facing classes below also derive
from DRF's :class:`~rest_framework.exceptions.APIException`: they carry the
HTTP status and rule 9's stable error code, so the blog views raise the
module's own error and the one QuickScale exception handler renders the
response (Module Conventions rule 9).
"""

from __future__ import annotations

from rest_framework.exceptions import APIException

__all__ = [
    "BlogError",
    "BlogMediaUploadError",
    "BlogMediaUploadValidationError",
    "BlogPublishConflictError",
    "BlogPublishError",
    "BlogPublishValidationError",
]


class BlogError(Exception):
    """Base error for blog module operations."""


class BlogPublishValidationError(BlogError):
    """Validation error for blog publish API payload"""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid payload")
        self.errors = errors


class BlogPublishConflictError(BlogError, APIException):
    """Conflict error for blog publish API payload.

    A post with the generated slug already exists in the organization.
    """

    status_code = 409
    default_code = "post_conflict"


class BlogPublishError(BlogError, APIException):
    """Raised when a blog publish write fails unexpectedly."""

    status_code = 500
    default_code = "publish_failed"


class BlogMediaUploadValidationError(BlogError):
    """Validation error for blog media upload payload."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid media upload payload")
        self.errors = errors


class BlogMediaUploadError(BlogError, APIException):
    """Raised when a blog media asset write fails unexpectedly."""

    status_code = 500
    default_code = "upload_failed"
