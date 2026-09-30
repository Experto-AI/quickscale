"""Auth module exceptions.

Every auth exception derives from :class:`AuthError`, so the module's error
surface has one base.  The account-deletion view's provider-block signal is a
private subclass used only for local control flow.
"""

from __future__ import annotations

__all__ = ["AuthError"]


class AuthError(Exception):
    """Base error for auth module operations."""


class _AccountDeletionProviderBlocked(AuthError):
    """Raised when a declared provider handler blocks account deletion."""
