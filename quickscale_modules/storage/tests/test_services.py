"""Tests for storage's public service surface (Module Conventions rules 4, 23)."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from quickscale_modules_storage import helpers, services

#: Exactly the names rule 23 makes the module's public service surface.
SERVICE_SURFACE = [
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


def test_services_publishes_exactly_the_declared_surface() -> None:
    """``__all__`` is the module's public surface, and nothing else is public."""
    assert services.__all__ == SERVICE_SURFACE
    for name in SERVICE_SURFACE:
        assert hasattr(services, name), f"{name} is missing from services.py"


def test_services_reexports_the_helper_implementations() -> None:
    """The public surface stays one implementation, not a parallel copy."""
    assert services.build_upload_path is helpers.build_upload_path
    assert services.select_storage_backend is helpers.select_storage_backend
    assert services.make_cache_friendly_name is helpers.make_cache_friendly_name
    assert services.sanitize_relative_media_path is helpers.sanitize_relative_media_path


def test_build_upload_path_takes_its_asset_arguments_keyword_only() -> None:
    """Rule 23: at most one leading subject; the rest stay keyword-only."""
    with pytest.raises(TypeError):
        services.build_upload_path("blog", "uploads", "hero.png")  # type: ignore[call-arg]


class TestBuildPublicMediaUrl:
    """The service resolves storage's own declared settings (rule 3)."""

    def test_uses_the_declared_public_base_url(self) -> None:
        with override_settings(
            QUICKSCALE_STORAGE_PUBLIC_BASE_URL="https://cdn.example.com/media",
            MEDIA_URL="/media/",
        ):
            assert (
                services.build_public_media_url("blog/uploads/2026/03/hero.png")
                == "https://cdn.example.com/media/blog/uploads/2026/03/hero.png"
            )

    def test_falls_back_to_media_url_without_a_public_base(self) -> None:
        with override_settings(
            QUICKSCALE_STORAGE_PUBLIC_BASE_URL="",
            MEDIA_URL="/media/",
        ):
            assert (
                services.build_public_media_url("blog/uploads/2026/03/hero.png")
                == "/media/blog/uploads/2026/03/hero.png"
            )

    def test_absolute_reference_is_returned_unchanged(self) -> None:
        with override_settings(
            QUICKSCALE_STORAGE_PUBLIC_BASE_URL="https://cdn.example.com/media",
            MEDIA_URL="/media/",
        ):
            absolute = "https://other.example.com/hero.png"
            assert services.build_public_media_url(absolute) == absolute

    def test_blank_reference_is_empty(self) -> None:
        with override_settings(
            QUICKSCALE_STORAGE_PUBLIC_BASE_URL="",
            MEDIA_URL="/media/",
        ):
            assert services.build_public_media_url("") == ""


class TestServiceErrors:
    """Rule 23: a service that cannot do what it was asked raises StorageError."""

    def test_validate_file_upload_rejects_an_invalid_image_with_storage_error(
        self,
    ) -> None:
        upload = SimpleUploadedFile(
            "notes.txt",
            b"not an image",
            content_type="text/plain",
        )

        with pytest.raises(services.StorageError) as error:
            services.validate_file_upload(
                upload,
                max_size_bytes=1024,
                allowed_image_formats={"PNG", "JPEG"},
            )

        assert "Unsupported or invalid image file" in str(error.value)

    def test_validate_file_upload_rejects_an_oversize_file_with_storage_error(
        self,
    ) -> None:
        upload = SimpleUploadedFile("big.png", b"x" * 32, content_type="image/png")

        with pytest.raises(services.StorageError):
            services.validate_file_upload(
                upload,
                max_size_bytes=8,
                allowed_image_formats={"PNG"},
            )

    def test_list_s3_compatible_media_inventory_refuses_local_with_storage_error(
        self,
    ) -> None:
        with pytest.raises(services.StorageError) as error:
            services.list_s3_compatible_media_inventory(
                {"QUICKSCALE_STORAGE_BACKEND": "local"}
            )

        assert "s3-compatible" in str(error.value)

    def test_list_s3_compatible_media_inventory_wraps_provider_failures(
        self,
    ) -> None:
        """A provider request failure reaches callers as the module's error."""
        exceptions = pytest.importorskip("botocore.exceptions")
        provider_error = exceptions.ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "ListObjectsV2",
        )

        class _FailingStorage:
            def __init__(self, **_options: object) -> None:
                raise provider_error

        settings_map = {
            "QUICKSCALE_STORAGE_BACKEND": "s3",
            "AWS_STORAGE_BUCKET_NAME": "bucket",
            "AWS_S3_ENDPOINT_URL": "",
            "AWS_S3_REGION_NAME": "",
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            "AWS_DEFAULT_ACL": "",
            "AWS_QUERYSTRING_AUTH": False,
        }

        with pytest.raises(services.StorageError) as error:
            services.list_s3_compatible_media_inventory(
                settings_map,
                storage_factory=_FailingStorage,
            )

        assert isinstance(error.value.__cause__, exceptions.ClientError)

    def test_storage_error_is_the_module_error_base(self) -> None:
        assert issubclass(services.StorageError, Exception)


def test_is_enabled_reads_the_module_enabled_setting() -> None:
    """Rule 1: ``is_enabled()`` reports ``QUICKSCALE_STORAGE_ENABLED`` both ways."""
    with override_settings(QUICKSCALE_STORAGE_ENABLED=True):
        assert services.is_enabled() is True
    with override_settings(QUICKSCALE_STORAGE_ENABLED=False):
        assert services.is_enabled() is False
