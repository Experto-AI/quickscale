"""Tests for storage helper utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from quickscale_modules_storage.helpers import (
    build_public_media_url,
    build_upload_path,
    make_cache_friendly_name,
    select_storage_backend,
    validate_file_upload,
)


def _uploaded_image(
    *,
    filename: str = "asset.png",
    image_format: str = "PNG",
    size: tuple[int, int] = (800, 600),
) -> SimpleUploadedFile:
    image_bytes = BytesIO()
    image = Image.new("RGB", size, color="navy")
    image.save(image_bytes, format=image_format)
    return SimpleUploadedFile(
        filename,
        image_bytes.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )


class TestSelectStorageBackend:
    def test_local_backend_is_default(self) -> None:
        resolved = select_storage_backend({})
        assert resolved.backend == "local"
        assert resolved.use_s3_compatible is False
        assert resolved.django_backend == "django.core.files.storage.FileSystemStorage"

    def test_s3_backend_uses_s3_storage(self) -> None:
        resolved = select_storage_backend(
            {
                "QUICKSCALE_STORAGE_BACKEND": "s3",
                "AWS_STORAGE_BUCKET_NAME": "my-bucket",
                "AWS_S3_CUSTOM_DOMAIN": "cdn.example.com",
                "AWS_S3_ENDPOINT_URL": "",
            }
        )
        assert resolved.backend == "s3"
        assert resolved.use_s3_compatible is True
        assert resolved.django_backend == "storages.backends.s3.S3Storage"
        assert resolved.options["bucket_name"] == "my-bucket"
        assert resolved.options["custom_domain"] == "cdn.example.com"

    def test_r2_backend_accepts_endpoint_mode(self) -> None:
        resolved = select_storage_backend(
            {
                "QUICKSCALE_STORAGE_BACKEND": "r2",
                "AWS_S3_ENDPOINT_URL": "https://example.r2.cloudflarestorage.com",
            }
        )
        assert resolved.backend == "r2"
        assert resolved.options["endpoint_url"].startswith("https://")


class TestUploadPathAndNaming:
    def test_make_cache_friendly_name_uses_hash(self) -> None:
        name = make_cache_friendly_name("hero image.png", content=b"abc")
        assert name.startswith("hero-image-")
        assert len(name.split("-")) >= 3

    def test_build_upload_path_scopes_by_module_kind_and_date(self) -> None:
        path = build_upload_path(
            "blog",
            "uploads",
            "hero.png",
            now=datetime(2026, 3, 18, tzinfo=timezone.utc),
            content=b"abc",
        )
        assert path.startswith("blog/uploads/2026/03/")
        assert path.endswith(".png")


class TestPublicUrlHelpers:
    def test_build_public_media_url_with_absolute_reference(self) -> None:
        absolute_url = "https://cdn.example.com/blog/uploads/image.png"
        resolved = build_public_media_url(absolute_url)
        assert resolved == absolute_url

    def test_build_public_media_url_with_public_base_url(self) -> None:
        resolved = build_public_media_url(
            "blog/uploads/image.png",
            public_base_url="https://cdn.example.com/media",
        )
        assert resolved == "https://cdn.example.com/media/blog/uploads/image.png"

    def test_build_public_media_url_with_media_url_fallback(self) -> None:
        resolved = build_public_media_url(
            "blog/uploads/image.png",
            media_url="/media/",
        )
        assert resolved == "/media/blog/uploads/image.png"

    def test_build_public_media_url_supports_legacy_custom_domain_callers(self) -> None:
        resolved = build_public_media_url(
            "blog/uploads/image.png",
            custom_domain="cdn.example.com",
        )
        assert resolved == "https://cdn.example.com/blog/uploads/image.png"


class TestValidateFileUpload:
    def test_validate_file_upload_accepts_supported_image(self) -> None:
        uploaded = _uploaded_image(image_format="PNG", size=(640, 360))
        validated = validate_file_upload(
            uploaded,
            max_size_bytes=2_000_000,
            allowed_image_formats={"PNG", "JPEG"},
            max_width=2000,
            max_height=2000,
        )
        assert validated.width == 640
        assert validated.height == 360
        assert validated.format == "PNG"

    def test_validate_file_upload_rejects_unsupported_format(self) -> None:
        uploaded = _uploaded_image(image_format="GIF")
        with pytest.raises(ValueError, match="Unsupported image format"):
            validate_file_upload(
                uploaded,
                max_size_bytes=2_000_000,
                allowed_image_formats={"PNG", "JPEG"},
            )

    def test_validate_file_upload_rejects_oversize(self) -> None:
        payload = SimpleUploadedFile(
            "small.txt",
            b"12345",
            content_type="text/plain",
        )
        with pytest.raises(ValueError, match="maximum upload size"):
            validate_file_upload(
                payload,
                max_size_bytes=2,
                allowed_image_formats={"PNG"},
            )
