"""Storage module exceptions (Module Conventions rule 10)."""

from __future__ import annotations

__all__ = ["StorageError"]


class StorageError(Exception):
    """Base error for a storage operation that cannot be performed.

    The public services in :mod:`quickscale_modules_storage.services` raise
    this (or a subclass) when a request fails, so callers catch the module's
    one error base instead of a built-in.
    """
