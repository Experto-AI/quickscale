"""Focused tests for the storage manifest adapter.

The generic manifest boundary owns storage's option defaults, normalization
rules (including the ``path_or_absolute_url`` kind that carries the historical
``MEDIA_URL`` contract), checks, and secret projections; these tests pin the
adapter's remaining contract — the cloud-backend ``STORAGES`` block, the
backend-conditioned AWS credential aliases, and the sentinel.

The media matrix is sourced from the single frozen oracle P1 captured before
the module-owned helper was deleted; this suite does not maintain a second
expected-output list.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from quickscale_core.manifest import ManifestError
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_modules_storage.adapter import (
    _storage_manifest_adapter,
    get_manifest_adapter,
)

#: Single frozen historical MEDIA_URL oracle, owned by the P1 core test.
_CORE_MEDIA_ORACLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "quickscale_core"
    / "tests"
    / "test_manifest_resolver.py"
)


def _load_frozen_media_table() -> list[tuple[str, str]]:
    """Load the frozen media case table from its P1-owned oracle module."""
    spec = importlib.util.spec_from_file_location(
        "quickscale_core_media_oracle", _CORE_MEDIA_ORACLE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"cannot load the frozen media oracle from {_CORE_MEDIA_ORACLE_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module._MEDIA_URL_CASE_TABLE)


_MEDIA_URL_CASE_TABLE: list[tuple[str, str]] = _load_frozen_media_table()


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
        assert spec.url_includes == (
            ("markdownx/", "quickscale_modules_storage.markdownx_urls"),
        )
        assert spec.settings == {
            "QUICKSCALE_STORAGE_ENABLED": True,
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
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID": "__QS_ENV__:AWS_ACCESS_KEY_ID",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY": (
                "__QS_ENV__:AWS_SECRET_ACCESS_KEY"
            ),
            "MARKDOWNX_MARKDOWN_EXTENSIONS": [
                "markdown.extensions.fenced_code",
                "markdown.extensions.tables",
                "markdown.extensions.toc",
            ],
            "MARKDOWNX_MEDIA_PATH": "markdownx/",
            "MARKDOWNX_UPLOAD_CONTENT_TYPES": [
                "image/jpeg",
                "image/png",
                "image/gif",
            ],
        }
        assert list(spec.settings) == [
            "QUICKSCALE_STORAGE_ENABLED",
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
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY",
            "MARKDOWNX_MARKDOWN_EXTENSIONS",
            "MARKDOWNX_MEDIA_PATH",
            "MARKDOWNX_UPLOAD_CONTENT_TYPES",
        ]
        assert "STORAGES" not in spec.settings
        assert "AWS_ACCESS_KEY_ID" not in spec.settings
        assert "AWS_SECRET_ACCESS_KEY" not in spec.settings

    def test_disabled_keeps_the_shared_markdownx_mount_only(self) -> None:
        """Rule 1 (D3): off drops public URLs but keeps the shared editor mount."""
        spec = _storage_manifest_adapter({"enabled": False})

        assert spec.apps == ("quickscale_modules_storage",)
        assert spec.url_includes == (
            ("markdownx/", "quickscale_modules_storage.markdownx_urls"),
        )
        assert spec.pre_home_url_includes == ()
        assert spec.spa_routes == ()
        assert spec.settings["MARKDOWNX_MEDIA_PATH"] == "markdownx/"

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
                "BACKEND": "quickscale_modules_storage.backends.UniqueKeyS3Storage",
                "OPTIONS": {
                    "querystring_auth": False,
                    "file_overwrite": False,
                    **extra_options,
                },
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        }
        assert list(spec.settings) == [
            "QUICKSCALE_STORAGE_ENABLED",
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
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "STORAGES",
            "MARKDOWNX_MARKDOWN_EXTENSIONS",
            "MARKDOWNX_MEDIA_PATH",
            "MARKDOWNX_UPLOAD_CONTENT_TYPES",
        ]
        assert list(spec.settings["STORAGES"]["default"]["OPTIONS"]) == [
            "querystring_auth",
            "file_overwrite",
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
            }
        )

        assert spec.settings["QUICKSCALE_STORAGE_BACKEND"] == "s3"
        assert spec.settings["QUICKSCALE_STORAGE_PUBLIC_BASE_URL"] == (
            "https://cdn.example.com"
        )
        assert spec.settings["MEDIA_URL"] == "/uploads/"
        assert spec.settings["STORAGES"] == {
            "default": {
                "BACKEND": "quickscale_modules_storage.backends.UniqueKeyS3Storage",
                "OPTIONS": {"querystring_auth": True, "file_overwrite": False},
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
        ("options", "expected_fragment"),
        [
            ({"backend": "invalid"}, "modules.storage.backend"),
            (
                {"backend": "s3", "access_key_id_env_var": "AKIA1234567890123456"},
                "modules.storage.access_key_id_env_var",
            ),
            (
                {"backend": "s3", "secret_access_key_env_var": "literal-secret"},
                "modules.storage.secret_access_key_env_var",
            ),
            (
                {"backend": "s3", "access_key_id_env_var": "lower_case"},
                "modules.storage.access_key_id_env_var",
            ),
        ],
    )
    def test_invalid_backend_and_literal_or_invalid_secret_references_fail_closed(
        self, options: dict[str, Any], expected_fragment: str
    ) -> None:
        """Invalid backends and credential values are rejected before assembly."""
        with pytest.raises(ManifestError, match=expected_fragment):
            _storage_manifest_adapter(options)

    @pytest.mark.parametrize(
        ("retired_key", "replacement"),
        [
            ("access_key_id", "access_key_id_env_var"),
            ("secret_access_key", "secret_access_key_env_var"),
        ],
    )
    def test_legacy_literal_credentials_are_refused(
        self, retired_key: str, replacement: str
    ) -> None:
        """Legacy raw credential keys are refused with their replacement named."""
        with pytest.raises(ManifestError) as excinfo:
            _storage_manifest_adapter(
                {
                    "backend": "s3",
                    retired_key: "literal-secret",
                }
            )

        message = str(excinfo.value)
        assert f"'{retired_key}'" in message
        assert replacement in message
        assert "literal-secret" not in message

    def test_repeated_mixed_calls_do_not_leak_backend_state(self) -> None:
        """Repeated calls remain independent across local, S3, and R2."""
        s3 = _storage_manifest_adapter({"backend": "s3", "bucket_name": "s3-bucket"})
        local = _storage_manifest_adapter({})
        r2 = _storage_manifest_adapter(
            {"backend": "r2", "bucket_name": "r2-bucket", "endpoint_url": "https://r2"}
        )

        assert s3.settings["QUICKSCALE_STORAGE_BACKEND"] == "s3"
        assert local.settings == {
            "QUICKSCALE_STORAGE_ENABLED": True,
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
            "QUICKSCALE_STORAGE_ACCESS_KEY_ID": "__QS_ENV__:AWS_ACCESS_KEY_ID",
            "QUICKSCALE_STORAGE_SECRET_ACCESS_KEY": (
                "__QS_ENV__:AWS_SECRET_ACCESS_KEY"
            ),
            "MARKDOWNX_MARKDOWN_EXTENSIONS": [
                "markdown.extensions.fenced_code",
                "markdown.extensions.tables",
                "markdown.extensions.toc",
            ],
            "MARKDOWNX_MEDIA_PATH": "markdownx/",
            "MARKDOWNX_UPLOAD_CONTENT_TYPES": [
                "image/jpeg",
                "image/png",
                "image/gif",
            ],
        }
        assert r2.settings["QUICKSCALE_STORAGE_BACKEND"] == "r2"
        assert r2.settings["AWS_STORAGE_BUCKET_NAME"] == "r2-bucket"


class TestStorageMediaUrlContract:
    """MEDIA_URL reproduces the frozen historical matrix through the adapter."""

    @pytest.mark.parametrize(("supplied", "expected"), _MEDIA_URL_CASE_TABLE)
    def test_media_url_matches_frozen_historical_matrix(
        self, supplied: str, expected: str
    ) -> None:
        spec = _storage_manifest_adapter({"media_url": supplied})

        assert spec.settings["MEDIA_URL"] == expected

    def test_omitted_and_blank_media_url_use_the_declared_default(self) -> None:
        assert _storage_manifest_adapter({}).settings["MEDIA_URL"] == "/media/"
        for supplied in ("", "   ", "\t\n"):
            assert (
                _storage_manifest_adapter({"media_url": supplied}).settings["MEDIA_URL"]
                == "/media/"
            )

    @pytest.mark.parametrize("raw_value", [None, True, 1, ["/x/"], {"x": 1}])
    def test_non_string_media_url_is_refused(self, raw_value: object) -> None:
        """A non-string MEDIA_URL is a raw-type refusal, never a coercion."""
        with pytest.raises(ManifestError, match="modules.storage.media_url"):
            _storage_manifest_adapter({"media_url": raw_value})


class TestCloudUploadKeyUniqueness:
    """Cloud uploads allocate a distinct key for every save, including races."""

    @staticmethod
    def _recording_storage(
        options: dict[str, Any],
        *,
        barrier: threading.Barrier | None = None,
    ) -> Any:
        """Real allocation and save path with the provider connection faked."""
        pytest.importorskip("storages.backends.s3")
        from quickscale_modules_storage.backends import UniqueKeyS3Storage

        class RecordingStorage(UniqueKeyS3Storage):
            def __init__(self, **settings: Any) -> None:
                super().__init__(**settings)
                self.payloads: dict[str, bytes] = {}
                self.lock = threading.Lock()
                self.barrier = barrier

            def exists(self, name: str) -> bool:
                with self.lock:
                    return name in self.payloads

            def _save(self, name: str, content: Any) -> str:
                if self.barrier is not None:
                    self.barrier.wait(timeout=10)
                with self.lock:
                    self.payloads[name] = content.read()
                return name

        return RecordingStorage(**options)

    def test_same_filename_uploads_get_distinct_keys(self) -> None:
        """Every save carries a different token, even when no key exists yet."""
        pytest.importorskip("storages.backends.s3")
        from django.core.files.base import ContentFile

        spec = _storage_manifest_adapter({"backend": "s3", "bucket_name": "bucket"})
        assert spec.settings["STORAGES"]["default"]["BACKEND"] == (
            "quickscale_modules_storage.backends.UniqueKeyS3Storage"
        )
        options = spec.settings["STORAGES"]["default"]["OPTIONS"]
        storage = self._recording_storage(options)

        first = storage.save("listings/images/shared.jpg", ContentFile(b"first"))
        second = storage.save("listings/images/shared.jpg", ContentFile(b"second"))

        assert first != second
        assert storage.payloads == {first: b"first", second: b"second"}
        assert options["file_overwrite"] is False

    def test_concurrent_same_filename_uploads_keep_both_payloads(self) -> None:
        """Two writers that both see a free key still get distinct keys."""
        pytest.importorskip("storages.backends.s3")
        from django.core.files.base import ContentFile

        spec = _storage_manifest_adapter({"backend": "s3", "bucket_name": "bucket"})
        options = spec.settings["STORAGES"]["default"]["OPTIONS"]
        storage = self._recording_storage(
            options,
            barrier=threading.Barrier(2),
        )
        results: list[str] = []
        errors: list[BaseException] = []
        results_lock = threading.Lock()

        def upload(payload: bytes) -> None:
            try:
                name = storage.save(
                    "listings/images/shared.jpg",
                    ContentFile(payload),
                )
            except BaseException as error:  # pragma: no cover - failure path
                with results_lock:
                    errors.append(error)
                return
            with results_lock:
                results.append(name)

        threads = [
            threading.Thread(target=upload, args=(b"org-a",)),
            threading.Thread(target=upload, args=(b"org-b",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len(results) == 2
        assert len(set(results)) == 2
        assert set(storage.payloads) == set(results)
        assert sorted(storage.payloads.values()) == [b"org-a", b"org-b"]
