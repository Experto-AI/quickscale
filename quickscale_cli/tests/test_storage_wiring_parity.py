"""Wiring-parity tests for the manifest-driven storage path (Track 2 M4 follow-up).

Compares the legacy ``_storage_wiring`` builder output against the
manifest-driven ``build_manifest_wiring_spec("storage", ...)`` for every
option case, asserting full
:class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Scope
-----
* Default options (empty dict) — local backend
* Explicit local backend
* S3 backend with full cloud options
* R2 backend
* Invalid backend value — falls back to local
* Media URL normalisation (leading/trailing slash, missing prefix)
* Public base URL
* Private media enabled
* Cloud fields (bucket_name, endpoint_url, region_name, access_key_id,
  secret_access_key, default_acl, querystring_auth)
* Combined override cases
* Batch multi-case parity
"""

from __future__ import annotations

from wiring_parity import assert_wiring_parity


class TestStorageWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("storage", [{}])


class TestStorageWiringParityLocalBackend:
    """Local backend: no STORAGES or AWS_* settings."""

    def test_explicit_local(self) -> None:
        assert_wiring_parity("storage", [{"backend": "local"}])

    def test_local_no_storages_setting(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {"backend": "local"})
        assert "STORAGES" not in spec.settings
        assert "AWS_QUERYSTRING_AUTH" not in spec.settings

    def test_local_settings(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {})
        assert spec.settings["QUICKSCALE_STORAGE_BACKEND"] == "local"
        assert spec.settings["MEDIA_URL"] == "/media/"
        assert spec.settings["QUICKSCALE_STORAGE_PUBLIC_BASE_URL"] == ""
        assert spec.settings["QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED"] is False


class TestStorageWiringParityS3Backend:
    """S3 backend: STORAGES dict and AWS_* settings present."""

    _S3_OPTIONS = {
        "backend": "s3",
        "bucket_name": "my-bucket",
        "endpoint_url": "https://s3.amazonaws.com",
        "region_name": "us-east-1",
        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "default_acl": "",
        "querystring_auth": True,
    }

    def test_s3_parity(self) -> None:
        assert_wiring_parity("storage", [self._S3_OPTIONS])

    def test_s3_has_storages_setting(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", self._S3_OPTIONS)
        assert "STORAGES" in spec.settings
        storages = spec.settings["STORAGES"]
        assert storages["default"]["BACKEND"] == "storages.backends.s3.S3Storage"
        assert (
            storages["staticfiles"]["BACKEND"]
            == "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )

    def test_s3_has_aws_settings(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", self._S3_OPTIONS)
        assert spec.settings["AWS_QUERYSTRING_AUTH"] is True
        assert spec.settings["AWS_STORAGE_BUCKET_NAME"] == "my-bucket"
        assert spec.settings["AWS_S3_ENDPOINT_URL"] == "https://s3.amazonaws.com"
        assert spec.settings["AWS_S3_REGION_NAME"] == "us-east-1"
        assert spec.settings["AWS_ACCESS_KEY_ID"] == "AKIAIOSFODNN7EXAMPLE"
        assert (
            spec.settings["AWS_SECRET_ACCESS_KEY"]
            == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )

    def test_s3_minimal_options(self) -> None:
        """S3 backend with only required fields — empty cloud fields omitted."""
        assert_wiring_parity("storage", [{"backend": "s3"}])

    def test_s3_minimal_no_aws_bucket(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {"backend": "s3"})
        assert "AWS_STORAGE_BUCKET_NAME" not in spec.settings
        assert "AWS_S3_ENDPOINT_URL" not in spec.settings


class TestStorageWiringParityR2Backend:
    """R2 backend: same conditional wiring as S3."""

    _R2_OPTIONS = {
        "backend": "r2",
        "bucket_name": "my-r2-bucket",
        "endpoint_url": "https://abc123.r2.cloudflarestorage.com",
        "region_name": "auto",
        "access_key_id": "r2-access-key",
        "secret_access_key": "r2-secret-key",
    }

    def test_r2_parity(self) -> None:
        assert_wiring_parity("storage", [self._R2_OPTIONS])

    def test_r2_has_storages_setting(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", self._R2_OPTIONS)
        assert "STORAGES" in spec.settings


class TestStorageWiringParityInvalidBackend:
    """Invalid backend values must fall back to local."""

    def test_invalid_backend_fallback(self) -> None:
        assert_wiring_parity("storage", [{"backend": "gcs"}])

    def test_invalid_backend_uses_local(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {"backend": "gcs"})
        assert spec.settings["QUICKSCALE_STORAGE_BACKEND"] == "local"
        assert "STORAGES" not in spec.settings


class TestStorageWiringParityMediaUrl:
    """Media URL normalisation must match legacy behaviour."""

    def test_custom_media_url(self) -> None:
        assert_wiring_parity("storage", [{"media_url": "/uploads/"}])

    def test_media_url_missing_trailing_slash(self) -> None:
        assert_wiring_parity("storage", [{"media_url": "/uploads"}])

    def test_media_url_missing_leading_slash(self) -> None:
        assert_wiring_parity("storage", [{"media_url": "uploads/"}])

    def test_media_url_http_prefix(self) -> None:
        assert_wiring_parity(
            "storage", [{"media_url": "https://cdn.example.com/media/"}]
        )

    def test_media_url_blank_fallback(self) -> None:
        assert_wiring_parity("storage", [{"media_url": ""}])

    def test_media_url_normalised_value(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {"media_url": "uploads"})
        assert spec.settings["MEDIA_URL"] == "/uploads/"


class TestStorageWiringParityPublicBaseUrl:
    """Public base URL overrides."""

    def test_custom_public_base_url(self) -> None:
        assert_wiring_parity(
            "storage", [{"public_base_url": "https://cdn.example.com"}]
        )

    def test_public_base_url_stripped(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec(
            "storage", {"public_base_url": "  https://cdn.example.com  "}
        )
        assert spec.settings["QUICKSCALE_STORAGE_PUBLIC_BASE_URL"] == (
            "https://cdn.example.com"
        )


class TestStorageWiringParityPrivateMedia:
    """Private media enabled flag."""

    def test_private_media_enabled(self) -> None:
        assert_wiring_parity("storage", [{"private_media_enabled": True}])

    def test_private_media_disabled_explicit(self) -> None:
        assert_wiring_parity("storage", [{"private_media_enabled": False}])


class TestStorageWiringParityCloudFieldStripping:
    """Cloud-provider string fields must be stripped."""

    def test_bucket_name_stripped(self) -> None:
        assert_wiring_parity(
            "storage",
            [{"backend": "s3", "bucket_name": "  my-bucket  "}],
        )

    def test_endpoint_url_stripped(self) -> None:
        assert_wiring_parity(
            "storage",
            [{"backend": "s3", "endpoint_url": "  https://s3.example.com  "}],
        )


class TestStorageWiringParityCombinedOverrides:
    """Combined option overrides must produce equal specs from both paths."""

    def test_s3_combined(self) -> None:
        assert_wiring_parity(
            "storage",
            [
                {
                    "backend": "s3",
                    "bucket_name": "combined-bucket",
                    "endpoint_url": "https://s3.example.com",
                    "region_name": "eu-west-1",
                    "access_key_id": "KEY",
                    "secret_access_key": "SECRET",
                    "querystring_auth": False,
                    "media_url": "/assets/",
                    "public_base_url": "https://cdn.example.com",
                }
            ],
        )

    def test_local_with_custom_media_url(self) -> None:
        assert_wiring_parity(
            "storage",
            [
                {
                    "backend": "local",
                    "media_url": "/custom-media/",
                    "public_base_url": "https://media.example.com",
                }
            ],
        )


class TestStorageWiringParityStaticWiring:
    """Static wiring fields must be present and identical in both paths."""

    def test_apps(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {})
        assert spec.apps == ("quickscale_modules_storage",)

    def test_no_middleware(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {})
        assert spec.middleware == ()

    def test_no_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {})
        assert spec.url_includes == ()
        assert spec.pre_home_url_includes == ()


class TestStorageWiringParityBatchCases:
    """Run multiple option cases through the harness in a single call."""

    def test_multiple_cases_in_one_call(self) -> None:
        assert_wiring_parity(
            "storage",
            [
                {},
                {"backend": "local"},
                {"backend": "s3"},
                {
                    "backend": "s3",
                    "bucket_name": "my-bucket",
                    "endpoint_url": "https://s3.amazonaws.com",
                    "region_name": "us-east-1",
                    "access_key_id": "KEY",
                    "secret_access_key": "SECRET",
                    "querystring_auth": True,
                },
                {
                    "backend": "r2",
                    "bucket_name": "r2-bucket",
                    "endpoint_url": "https://abc.r2.cloudflarestorage.com",
                    "region_name": "auto",
                },
                {"backend": "gcs"},
                {"media_url": "/uploads/"},
                {"media_url": "uploads"},
                {"media_url": "https://cdn.example.com/media/"},
                {"public_base_url": "https://cdn.example.com"},
                {"private_media_enabled": True},
            ],
        )


class TestStorageWiringParityWhitespacePaddedBackend:
    """Regression: whitespace-padded backend values must match legacy parity.

    The legacy ``_storage_wiring`` only calls ``.lower()`` on the backend
    value (no ``.strip()``).  A whitespace-padded value like ``" s3 "``
    lowercases to ``" s3 "`` which is not in the valid set, so the legacy
    path falls back to ``"local"``.  The manifest adapter must produce the
    same result — it must NOT strip whitespace before lowercasing.
    """

    def test_whitespace_padded_s3_falls_back_to_local(self) -> None:
        """``" s3 "`` is not stripped by legacy; both paths must agree."""
        assert_wiring_parity("storage", [{"backend": " s3 "}])

    def test_whitespace_padded_s3_manifest_uses_local(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("storage", {"backend": " s3 "})
        assert spec.settings["QUICKSCALE_STORAGE_BACKEND"] == "local"
        assert "STORAGES" not in spec.settings

    def test_leading_space_backend(self) -> None:
        assert_wiring_parity("storage", [{"backend": " s3"}])

    def test_trailing_space_backend(self) -> None:
        assert_wiring_parity("storage", [{"backend": "s3 "}])

    def test_tab_padded_backend(self) -> None:
        assert_wiring_parity("storage", [{"backend": "\ts3\t"}])

    def test_whitespace_padded_local_still_valid(self) -> None:
        """``" local "`` lowercases to ``" local "`` → invalid → local fallback."""
        assert_wiring_parity("storage", [{"backend": " local "}])
