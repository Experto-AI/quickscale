"""Focused tests for the storage manifest adapter."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from typing import Any

import pytest

import quickscale_modules_storage as storage_api
from quickscale_core.manifest import ManifestError
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_modules_storage.adapter import (
    _storage_manifest_adapter,
    get_manifest_adapter,
)


PUBLIC_STORAGE_EXPORTS = (
    "StorageBackendSelection",
    "ValidatedUpload",
    "build_public_media_url",
    "build_upload_path",
    "make_cache_friendly_name",
    "select_storage_backend",
    "validate_file_upload",
)


class TestStoragePublicApi:
    """The dependency-light package facade preserves every helper export."""

    def test_public_export_inventory_is_explicit_and_complete(self) -> None:
        assert tuple(storage_api.__all__) == PUBLIC_STORAGE_EXPORTS

    @pytest.mark.parametrize("name", PUBLIC_STORAGE_EXPORTS)
    def test_public_export_is_resolved_lazily_and_cached(self, name: str) -> None:
        storage_api.__dict__.pop(name, None)

        value = getattr(storage_api, name)
        helpers = importlib.import_module("quickscale_modules_storage.helpers")

        assert value is getattr(helpers, name)
        assert storage_api.__dict__[name] is value
        assert getattr(storage_api, name) is value

    def test_unknown_attribute_fails_without_polluting_the_package(self) -> None:
        missing_name = "not_a_storage_export"

        with pytest.raises(
            AttributeError,
            match=(
                r"module 'quickscale_modules_storage' has no attribute "
                r"'not_a_storage_export'"
            ),
        ):
            getattr(storage_api, missing_name)

        assert missing_name not in storage_api.__dict__


class TestStorageManifestAdapter:
    """Storage adapter backend, settings, and credential-reference contract."""

    def test_sentinel_returns_callable(self) -> None:
        """The public sentinel returns the module adapter."""
        assert get_manifest_adapter() is _storage_manifest_adapter

    def test_adapter_imports_before_django_and_pillow_are_installed(self) -> None:
        """Installed apply can load the adapter before module dependencies."""
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib.abc, sys\n"
                    "class Blocker(importlib.abc.MetaPathFinder):\n"
                    "    def find_spec(self, fullname, path=None, target=None):\n"
                    "        if fullname.split('.', 1)[0] in {'django', 'PIL'}:\n"
                    "            raise ModuleNotFoundError(fullname)\n"
                    "        return None\n"
                    "sys.meta_path.insert(0, Blocker())\n"
                    "from quickscale_modules_storage.adapter import get_manifest_adapter\n"
                    "assert callable(get_manifest_adapter())\n"
                ),
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
        assert probe.returncode == 0, probe.stderr

    def test_local_defaults_emit_all_manifest_settings_and_omit_cloud_runtime(
        self,
    ) -> None:
        """Local storage emits every manifest setting but no cloud runtime block."""
        spec = _storage_manifest_adapter({})

        assert isinstance(spec, ModuleWiringSpec)
        assert spec.apps == ("quickscale_modules_storage",)
        assert spec.middleware == ()
        assert spec.pre_home_url_includes == ()
        assert spec.url_includes == ()
        assert spec.settings == {
            "QUICKSCALE_STORAGE_BACKEND": "local",
            "MEDIA_URL": "/media/",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL": "",
            "AWS_STORAGE_BUCKET_NAME": "",
            "AWS_S3_ENDPOINT_URL": "",
            "AWS_S3_REGION_NAME": "",
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID_ENV_VAR": "AWS_ACCESS_KEY_ID",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY_ENV_VAR": "AWS_SECRET_ACCESS_KEY",
            "AWS_DEFAULT_ACL": "",
            "AWS_QUERYSTRING_AUTH": False,
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED": False,
        }
        assert list(spec.settings) == [
            "QUICKSCALE_STORAGE_BACKEND",
            "MEDIA_URL",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL",
            "AWS_STORAGE_BUCKET_NAME",
            "AWS_S3_ENDPOINT_URL",
            "AWS_S3_REGION_NAME",
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID_ENV_VAR",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY_ENV_VAR",
            "AWS_DEFAULT_ACL",
            "AWS_QUERYSTRING_AUTH",
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
            "MEDIA_URL",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL",
            "AWS_STORAGE_BUCKET_NAME",
            "AWS_S3_ENDPOINT_URL",
            "AWS_S3_REGION_NAME",
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID_ENV_VAR",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY_ENV_VAR",
            "AWS_DEFAULT_ACL",
            "AWS_QUERYSTRING_AUTH",
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED",
            "STORAGES",
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
        """Blank cloud fields remain settings but stay out of provider options."""
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
            assert spec.settings[setting_name] == ""

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
            "MEDIA_URL": "/media/",
            "QUICKSCALE_STORAGE_PUBLIC_BASE_URL": "",
            "AWS_STORAGE_BUCKET_NAME": "",
            "AWS_S3_ENDPOINT_URL": "",
            "AWS_S3_REGION_NAME": "",
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID_ENV_VAR": "AWS_ACCESS_KEY_ID",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY_ENV_VAR": "AWS_SECRET_ACCESS_KEY",
            "AWS_DEFAULT_ACL": "",
            "AWS_QUERYSTRING_AUTH": False,
            "QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED": False,
        }
        assert r2.settings["QUICKSCALE_STORAGE_BACKEND"] == "r2"
        assert r2.settings["AWS_STORAGE_BUCKET_NAME"] == "r2-bucket"
