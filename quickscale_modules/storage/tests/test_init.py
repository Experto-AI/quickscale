"""Tests for the storage package root contract (Module Conventions rule 15)."""

from __future__ import annotations

import quickscale_modules_storage as package

# The helper symbols the package root used to re-export; they now live in
# ``quickscale_modules_storage.helpers`` and are reached through that module.
FORMER_ROOT_EXPORTS = (
    "StorageBackendSelection",
    "ValidatedUpload",
    "build_public_media_url",
    "build_upload_path",
    "make_cache_friendly_name",
    "select_storage_backend",
    "validate_file_upload",
)


def test_package_root_exports_only_the_version() -> None:
    """``__init__.py`` holds ``__version__`` and ``__all__`` and nothing else."""
    assert package.__all__ == ["__version__"]
    assert isinstance(package.__version__, str)


def test_former_lazy_exports_are_no_longer_package_attributes() -> None:
    """The removed root re-exports stay gone — the public surface is services."""
    for name in FORMER_ROOT_EXPORTS:
        assert not hasattr(package, name), f"{name} leaked back onto the package root"
