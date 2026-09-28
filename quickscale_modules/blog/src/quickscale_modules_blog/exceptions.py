"""Blog module exceptions.

Every blog exception derives from :class:`BlogError`, so the module's error
surface has one base.  The publish API's validation errors carry the field
errors they were raised with.
"""

from __future__ import annotations

__all__ = [
    "BlogError",
    "BlogMediaUploadValidationError",
    "BlogPublishConflictError",
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
    """Conflict error for blog publish API payload"""


class BlogMediaUploadValidationError(BlogError):
    """Validation error for blog media upload payload."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid media upload payload")
        self.errors = errors
