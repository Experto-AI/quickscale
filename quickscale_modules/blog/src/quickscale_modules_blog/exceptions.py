"""Blog module exceptions.

Every blog exception derives from :class:`BlogError`, so the module's error
surface has one base.  The publish API's validation errors carry the field
errors they were raised with, and the API-facing classes below declare the
HTTP status and rule 9's stable error code; the classes derive from
:class:`Exception` only — the one QuickScale exception handler in
``quickscale_core.runtime`` renders them (Module Conventions rules 9 and 10).
"""

from __future__ import annotations

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


class BlogPublishConflictError(BlogError):
    """Conflict error for blog publish API payload.

    A post with the generated slug already exists in the organization.
    """

    status_code = 409
    default_code = "post_conflict"


class BlogPublishError(BlogError):
    """Raised when a blog publish write fails unexpectedly."""

    status_code = 500
    default_code = "publish_failed"


class BlogMediaUploadValidationError(BlogError):
    """Validation error for blog media upload payload."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid media upload payload")
        self.errors = errors


class BlogMediaUploadError(BlogError):
    """Raised when a blog media asset write fails unexpectedly."""

    status_code = 500
    default_code = "upload_failed"
