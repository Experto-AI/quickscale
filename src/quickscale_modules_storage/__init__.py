"""QuickScale storage module public API."""

from __future__ import annotations

from typing import Any

__version__ = "0.88.0"

__all__ = [
    "StorageBackendSelection",
    "ValidatedUpload",
    "build_public_media_url",
    "build_upload_path",
    "make_cache_friendly_name",
    "select_storage_backend",
    "validate_file_upload",
]


def __getattr__(name: str) -> Any:
    """Load helper exports only when their Django/Pillow runtime is installed.

    The manifest adapter is imported during ``quickscale apply`` before module
    dependencies are installed.  Keeping package initialization dependency-free
    lets that adapter load from embedded source while preserving the existing
    public helper imports once the storage module's runtime is available.
    """
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from . import helpers

    value = getattr(helpers, name)
    globals()[name] = value
    return value
