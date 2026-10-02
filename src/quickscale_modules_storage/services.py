"""Public service surface for the QuickScale storage module.

Module Conventions rule 4: another module uses storage only through this
file, and rule 23: exactly ``__all__`` below is the module's public service
surface, public functions take keyword-only parameters after at most one
leading subject, and a service that cannot do what it was asked raises
:class:`StorageError` (rule 10).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from quickscale_modules_storage.exceptions import StorageError
from quickscale_modules_storage.helpers import (
    StorageBackendSelection,
    ValidatedUpload,
    build_public_media_url as _build_public_media_url,
    build_upload_path,
    list_s3_compatible_media_inventory as _list_s3_compatible_media_inventory,
    make_cache_friendly_name,
    sanitize_relative_media_path,
    select_storage_backend,
    validate_file_upload as _validate_file_upload,
)


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_STORAGE_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_STORAGE_ENABLED)


__all__ = [
    "StorageBackendSelection",
    "StorageError",
    "ValidatedUpload",
    "build_public_media_url",
    "build_upload_path",
    "is_enabled",
    "list_s3_compatible_media_inventory",
    "make_cache_friendly_name",
    "sanitize_relative_media_path",
    "select_storage_backend",
    "validate_file_upload",
]


def build_public_media_url(
    stored_reference: str,
    *,
    request: Any | None = None,
) -> str:
    """Build a public media URL from one of storage's stored references.

    Rule 3: the canonical public base and the media URL prefix come from
    storage's own declared settings, so a caller never reads them.
    """
    return _build_public_media_url(
        stored_reference,
        request=request,
        public_base_url=str(settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL),
        media_url=str(settings.MEDIA_URL),
    )


def _provider_error_classes() -> tuple[type[BaseException], ...]:
    """The cloud SDK's error bases, or ``()`` without the cloud extra.

    The provider SDK is an optional dependency, so it is imported lazily at
    the service boundary; a local-only install never imports it, and an empty
    tuple simply matches nothing.
    """
    try:
        from botocore.exceptions import (  # type: ignore[import-untyped]
            BotoCoreError,
            ClientError,
        )
    except ModuleNotFoundError:
        return ()
    return (BotoCoreError, ClientError)


def list_s3_compatible_media_inventory(
    settings_obj: Any,
    *,
    storage_factory: type[Any] | None = None,
) -> list[dict[str, Any]]:
    """List private s3-compatible media objects without exposing credentials.

    Raises:
        StorageError: when the selected backend is not s3-compatible, the
            bucket name is missing, or the provider request fails (rule 23).
            Configuration failures keep their rule-3 ``ImproperlyConfigured``
            shape and are not converted.
    """
    try:
        return _list_s3_compatible_media_inventory(
            settings_obj,
            storage_factory=storage_factory,
        )
    except ValueError as exc:
        raise StorageError(str(exc)) from exc
    except _provider_error_classes() as exc:
        raise StorageError(str(exc)) from exc


def validate_file_upload(
    uploaded_file: UploadedFile,
    *,
    max_size_bytes: int,
    allowed_image_formats: set[str],
    max_width: int | None = None,
    max_height: int | None = None,
) -> ValidatedUpload:
    """Validate an uploaded image by size, format, and optional dimensions.

    Raises:
        StorageError: when the upload fails a validation rule (rule 23).
    """
    try:
        return _validate_file_upload(
            uploaded_file,
            max_size_bytes=max_size_bytes,
            allowed_image_formats=allowed_image_formats,
            max_width=max_width,
            max_height=max_height,
        )
    except ValueError as exc:
        raise StorageError(str(exc)) from exc
