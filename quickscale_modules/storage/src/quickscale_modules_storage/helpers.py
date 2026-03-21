"""Storage helper utilities for QuickScale modules."""

from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
from uuid import uuid4

from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class StorageBackendSelection:
    """Resolved storage backend selection and optional provider options."""

    backend: str
    django_backend: str
    use_s3_compatible: bool
    options: dict[str, Any]


@dataclass(frozen=True)
class ValidatedUpload:
    """Validated upload metadata returned by `validate_file_upload`."""

    size_bytes: int
    content_type: str
    width: int
    height: int
    format: str


def _read_setting(settings_obj: Any | Mapping[str, Any], key: str, default: Any) -> Any:
    if isinstance(settings_obj, Mapping):
        return settings_obj.get(key, default)
    return getattr(settings_obj, key, default)


def _normalize_backend(raw_backend: str | None) -> str:
    backend = (raw_backend or "local").strip().lower()
    if backend in {"filesystem", "file", "local"}:
        return "local"
    if backend in {"s3", "r2"}:
        return backend
    return "local"


def _normalize_media_prefix(media_url: str) -> str:
    cleaned = (media_url or "/media/").strip()
    if not cleaned:
        return "/media/"
    if (
        not cleaned.startswith("/")
        and not cleaned.startswith("http://")
        and not cleaned.startswith("https://")
    ):
        cleaned = "/" + cleaned
    if not cleaned.endswith("/"):
        cleaned += "/"
    return cleaned


def select_storage_backend(
    settings_obj: Any | Mapping[str, Any],
) -> StorageBackendSelection:
    """Resolve local vs S3-compatible backend settings from Django settings."""
    backend = _normalize_backend(
        str(_read_setting(settings_obj, "QUICKSCALE_STORAGE_BACKEND", "local"))
    )

    if backend == "local":
        return StorageBackendSelection(
            backend="local",
            django_backend="django.core.files.storage.FileSystemStorage",
            use_s3_compatible=False,
            options={},
        )

    options: dict[str, Any] = {
        "bucket_name": str(
            _read_setting(settings_obj, "AWS_STORAGE_BUCKET_NAME", "")
        ).strip(),
        "endpoint_url": str(
            _read_setting(settings_obj, "AWS_S3_ENDPOINT_URL", "")
        ).strip(),
        "region_name": str(
            _read_setting(settings_obj, "AWS_S3_REGION_NAME", "")
        ).strip(),
        "access_key_id": str(
            _read_setting(settings_obj, "AWS_ACCESS_KEY_ID", "")
        ).strip(),
        "secret_access_key": str(
            _read_setting(settings_obj, "AWS_SECRET_ACCESS_KEY", "")
        ).strip(),
        "default_acl": str(_read_setting(settings_obj, "AWS_DEFAULT_ACL", "")).strip(),
        "querystring_auth": bool(
            _read_setting(settings_obj, "AWS_QUERYSTRING_AUTH", False)
        ),
    }

    return StorageBackendSelection(
        backend=backend,
        django_backend="storages.backends.s3.S3Storage",
        use_s3_compatible=True,
        options=options,
    )


def make_cache_friendly_name(
    filename: str,
    *,
    content: bytes | None = None,
    version: str | None = None,
) -> str:
    """Build an immutable-style filename segment with deterministic hash support."""
    stem = slugify(Path(filename).stem) or "asset"

    if content is not None:
        digest = hashlib.sha256(content).hexdigest()[:16]
    else:
        seed = f"{filename}:{version or ''}:{uuid4().hex}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    if version:
        normalized_version = slugify(version) or "v1"
        return f"{stem}-{normalized_version}-{digest}"

    return f"{stem}-{digest}"


def build_upload_path(
    module_name: str,
    asset_kind: str,
    filename: str,
    *,
    now: datetime | None = None,
    content: bytes | None = None,
    version: str | None = None,
) -> str:
    """Build a cache-friendly upload path segmented by module and year/month."""
    timestamp = now or datetime.now(tz=timezone.utc)
    module_segment = slugify(module_name) or "module"
    kind_segment = slugify(asset_kind) or "asset"
    extension = Path(filename).suffix.lower() or ".bin"
    name = make_cache_friendly_name(filename, content=content, version=version)
    return f"{module_segment}/{kind_segment}/{timestamp:%Y/%m}/{name}{extension}"


def build_public_media_url(
    stored_reference: str,
    *,
    request: Any | None = None,
    public_base_url: str | None = None,
    media_url: str = "/media/",
) -> str:
    """Build a public media URL from a storage path or relative/absolute reference."""
    reference = (stored_reference or "").strip()
    if not reference:
        return ""

    parsed = urlparse(reference)
    if parsed.scheme and parsed.netloc:
        return reference

    if public_base_url and public_base_url.strip():
        base = public_base_url.rstrip("/")
        return f"{base}/{reference.lstrip('/')}"

    normalized_media_url = _normalize_media_prefix(media_url)

    if reference.startswith("/"):
        relative_path = reference
    else:
        relative_path = f"{normalized_media_url}{reference.lstrip('/')}"

    if request is not None:
        return request.build_absolute_uri(relative_path)

    return relative_path


def validate_file_upload(
    uploaded_file: UploadedFile,
    *,
    max_size_bytes: int,
    allowed_image_formats: set[str],
    max_width: int | None = None,
    max_height: int | None = None,
) -> ValidatedUpload:
    """Validate uploaded image by size, format, and optional dimensions."""
    size_bytes = int(uploaded_file.size or 0)
    if size_bytes > max_size_bytes:
        raise ValueError(f"File exceeds maximum upload size of {max_size_bytes} bytes")

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Unsupported or invalid image file") from exc
    finally:
        uploaded_file.seek(0)

    image_format = str(image.format or "").upper()
    if image_format not in allowed_image_formats:
        allowed_list = ", ".join(sorted(allowed_image_formats))
        raise ValueError(f"Unsupported image format. Allowed formats: {allowed_list}")

    width = int(image.width)
    height = int(image.height)

    if max_width is not None and width > max_width:
        raise ValueError(f"Image width exceeds maximum of {max_width} pixels")

    if max_height is not None and height > max_height:
        raise ValueError(f"Image height exceeds maximum of {max_height} pixels")

    content_type = str(uploaded_file.content_type or "application/octet-stream")

    return ValidatedUpload(
        size_bytes=size_bytes,
        content_type=content_type,
        width=width,
        height=height,
        format=image_format,
    )


def sanitize_relative_media_path(path: str) -> str:
    """Return a normalized relative media path without leading slash traversal."""
    normalized = re.sub(r"^/+", "", path.strip())
    return posixpath.normpath(normalized).lstrip("./")


__all__ = [
    "StorageBackendSelection",
    "ValidatedUpload",
    "build_public_media_url",
    "build_upload_path",
    "make_cache_friendly_name",
    "sanitize_relative_media_path",
    "select_storage_backend",
    "validate_file_upload",
]
