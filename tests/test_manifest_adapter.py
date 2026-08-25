"""Focused tests for the storage manifest adapter."""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.manifest import ManifestError
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_modules_storage.adapter import (
    _storage_manifest_adapter,
    get_manifest_adapter,
)


class TestStorageManifestAdapter:
    """Storage adapter backend, settings, and credential-reference contract."""

    def test_sentinel_returns_callable(self) -> None:
        """The public sentinel returns the module adapter."""
        assert get_manifest_adapter() is _storage_manifest_adapter

    def test_local_defaults_preserve_exact_shape_and_omissions(self) -> None:
        """Local storage emits only its four unconditional settings."""
        spec = _storage_manifest_adapter({})

        assert isinstance(spec, ModuleWiringSpec)
        assert spec.apps == ("quickscale_modules_storage",)
        assert spec.middleware == ()
        assert spec.pre_home_url_includes == ()
        assert spec.url_includes == ()
        assert spec.settings == {
            "QUICKSCALE_STORAGE_BACKEND": "local",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL": "",
            "MEDIA_URL": "/media/",
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED": False,
        }
        assert list(spec.settings) == [
            "QUICKSCALE_STORAGE_BACKEND",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL",
            "MEDIA_URL",
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED",
        ]
        assert "STORAGES" not in spec.settings
        assert "AWS_ACCESS_KEY_ID" not in spec.settings
        assert "AWS_SECRET_ACCESS_KEY" not in spec.settings

    @pytest.mark.parametrize(
        ("backend", "extra_options"),
        [
            ("s3", {"bucket_name": "bucket", "region_name": "us-east-1"}),
            (
                "r2",
                {
                    "bucket_name": "bucket",
                    "endpoint_url": "https://account.r2.cloudflarestorage.com",
                    "region_name": "auto",
                },
            ),
        ],
    )
    def test_cloud_backends_preserve_storages_and_aws_settings(
        self, backend: str, extra_options: dict[str, Any]
    ) -> None:
        """S3 and R2 use the same S3-compatible settings projection."""
        spec = _storage_manifest_adapter({"backend": backend, **extra_options})

        assert spec.apps == ("quickscale_modules_storage",)
        assert spec.settings["QUICKSCALE_STORAGE_BACKEND"] == backend
        assert spec.settings["STORAGES"] == {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": {
                    "querystring_auth": False,
                    **extra_options,
                },
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        }
        assert list(spec.settings) == [
            "QUICKSCALE_STORAGE_BACKEND",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL",
            "MEDIA_URL",
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED",
            "STORAGES",
            "AWS_QUERYSTRING_AUTH",
            "AWS_STORAGE_BUCKET_NAME",
            *(["AWS_S3_ENDPOINT_URL"] if "endpoint_url" in extra_options else []),
            *(["AWS_S3_REGION_NAME"] if "region_name" in extra_options else []),
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        ]
        assert list(spec.settings["STORAGES"]["default"]["OPTIONS"]) == [
            "querystring_auth",
            *extra_options,
        ]
        assert spec.settings["AWS_QUERYSTRING_AUTH"] is False
        assert spec.settings["AWS_STORAGE_BUCKET_NAME"] == "bucket"
        for option_name, setting_name in (
            ("endpoint_url", "AWS_S3_ENDPOINT_URL"),
            ("region_name", "AWS_S3_REGION_NAME"),
        ):
            if option_name in extra_options:
                assert spec.settings[setting_name] == extra_options[option_name]

        assert spec.settings["AWS_ACCESS_KEY_ID"] == "__QS_ENV__:AWS_ACCESS_KEY_ID"
        assert spec.settings["AWS_SECRET_ACCESS_KEY"] == (
            "__QS_ENV__:AWS_SECRET_ACCESS_KEY"
        )
        assert "bucket_name" not in spec.settings["STORAGES"]["default"]["OPTIONS"] or (
            spec.settings["STORAGES"]["default"]["OPTIONS"]["bucket_name"] == "bucket"
        )

    def test_cloud_options_preserve_blanks_and_omit_blank_provider_settings(
        self,
    ) -> None:
        """Blank optional cloud fields are omitted rather than emitted as blanks."""
        spec = _storage_manifest_adapter(
            {
                "backend": "s3",
                "media_url": " /uploads ",
                "public_base_url": " https://cdn.example.com/ ",
                "bucket_name": " ",
                "endpoint_url": " ",
                "region_name": " ",
                "default_acl": " ",
                "querystring_auth": True,
                "private_media_enabled": True,
            }
        )

        assert spec.settings["QUICKSCALE_STORAGE_BACKEND"] == "s3"
        assert spec.settings["QUICKSCALE_STORAGE_PUBLIC_BASE_URL"] == (
            "https://cdn.example.com/"
        )
        assert spec.settings["MEDIA_URL"] == "/uploads/"
        assert spec.settings["QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED"] is True
        assert spec.settings["STORAGES"] == {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": {"querystring_auth": True},
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        }
        assert spec.settings["AWS_QUERYSTRING_AUTH"] is True
        for setting_name in (
            "AWS_STORAGE_BUCKET_NAME",
            "AWS_S3_ENDPOINT_URL",
            "AWS_S3_REGION_NAME",
            "AWS_DEFAULT_ACL",
        ):
            assert setting_name not in spec.settings

    def test_custom_credential_names_are_references_not_values(self) -> None:
        """Custom credential options become environment-reference markers."""
        spec = _storage_manifest_adapter(
            {
                "backend": "s3",
                "access_key_id_env_var": "CUSTOM_ACCESS",
                "secret_access_key_env_var": "CUSTOM_SECRET",
            }
        )

        assert spec.settings["AWS_ACCESS_KEY_ID"] == "__QS_ENV__:CUSTOM_ACCESS"
        assert spec.settings["AWS_SECRET_ACCESS_KEY"] == "__QS_ENV__:CUSTOM_SECRET"
        assert "CUSTOM_ACCESS" not in str(spec.settings["STORAGES"])
        assert "CUSTOM_SECRET" not in str(spec.settings["STORAGES"])

    @pytest.mark.parametrize(
        "options",
        [
            {"backend": "invalid"},
            {"backend": "s3", "access_key_id_env_var": "AKIA1234567890123456"},
            {"backend": "s3", "secret_access_key_env_var": "literal-secret"},
            {"backend": "s3", "access_key_id_env_var": "lower_case"},
        ],
    )
    def test_invalid_backend_and_literal_or_invalid_secret_references_fail_closed(
        self, options: dict[str, Any]
    ) -> None:
        """Invalid backends and credential values are rejected before assembly."""
        with pytest.raises(ManifestError, match="validation issues"):
            _storage_manifest_adapter(options)

    def test_legacy_literal_credentials_are_not_emitted(self) -> None:
        """Legacy raw credential keys are converted to default env references."""
        spec = _storage_manifest_adapter(
            {
                "backend": "s3",
                "access_key_id": "AKIA1234567890123456",
                "secret_access_key": "literal-secret",
            }
        )

        assert spec.settings["AWS_ACCESS_KEY_ID"] == "__QS_ENV__:AWS_ACCESS_KEY_ID"
        assert spec.settings["AWS_SECRET_ACCESS_KEY"] == (
            "__QS_ENV__:AWS_SECRET_ACCESS_KEY"
        )
        assert "AKIA1234567890123456" not in str(spec)
        assert "literal-secret" not in str(spec)

    def test_repeated_mixed_calls_do_not_leak_backend_state(self) -> None:
        """Repeated calls remain independent across local, S3, and R2."""
        s3 = _storage_manifest_adapter({"backend": "s3", "bucket_name": "s3-bucket"})
        local = _storage_manifest_adapter({})
        r2 = _storage_manifest_adapter(
            {"backend": "r2", "bucket_name": "r2-bucket", "endpoint_url": "https://r2"}
        )

        assert s3.settings["QUICKSCALE_STORAGE_BACKEND"] == "s3"
        assert local.settings == {
            "QUICKSCALE_STORAGE_BACKEND": "local",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL": "",
            "MEDIA_URL": "/media/",
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED": False,
        }
        assert r2.settings["QUICKSCALE_STORAGE_BACKEND"] == "r2"
        assert r2.settings["AWS_STORAGE_BUCKET_NAME"] == "r2-bucket"
