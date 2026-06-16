"""Parity/regression tests for the manifest-driven storage option-resolution path.

These tests encode the *legacy* ``_storage_wiring`` and ``_normalize_media_url``
behaviour as gold expectations and verify that the manifest-driven replacement
(``storage_manifest.py``) produces identical results for every public entry
point that belongs to the B-phase adapter scope.

B-phase scope (this file):
* Default option values
* backend normalisation (strip + lowercase + fallback to "local")
* media_url normalisation (``_normalize_media_url`` mirror)
* public_base_url normalisation (strip)
* private_media_enabled (immutable bool, default False)
* Resolution (defaults + normalised overrides, idempotency)
* Validation messages (backend choices)

C11 scope (deferred, NOT tested here):
* Nested STORAGES / AWS_* wiring for s3 / r2 backends

The gold values below were recovered from the storage ``module.yml`` manifest,
``_normalize_media_url`` (lines 55–61 of module_wiring_specs.py), and
``_storage_wiring`` (lines 232–301).
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_cli.storage_manifest import (  # type: ignore[import-untyped]
    DEFAULT_STORAGE_BACKEND,
    DEFAULT_STORAGE_MEDIA_URL,
    DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED,
    DEFAULT_STORAGE_PUBLIC_BASE_URL,
    STORAGE_BACKEND_LOCAL,
    STORAGE_BACKEND_R2,
    STORAGE_BACKEND_S3,
    STORAGE_BACKENDS,
    STORAGE_MODULE_OPTION_KEYS,
    default_storage_module_options,
    normalize_storage_module_options,
    resolve_storage_module_options,
    validate_storage_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy _storage_wiring + module.yml
#
# Note: module.yml includes both mutable and immutable options in get_defaults().
# private_media_enabled is immutable (fixed False) but appears in the defaults.
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "backend": "local",
    "media_url": "/media/",
    "public_base_url": "",
    "bucket_name": "",
    "endpoint_url": "",
    "region_name": "",
    "access_key_id": "",
    "secret_access_key": "",
    "default_acl": "",
    "querystring_auth": False,
    "private_media_enabled": False,
}


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy(self) -> None:
        defaults = default_storage_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        defaults = default_storage_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_backend_is_local(self) -> None:
        defaults = default_storage_module_options()
        assert defaults["backend"] == DEFAULT_STORAGE_BACKEND
        assert defaults["backend"] == "local"

    def test_default_media_url(self) -> None:
        defaults = default_storage_module_options()
        assert defaults["media_url"] == DEFAULT_STORAGE_MEDIA_URL
        assert defaults["media_url"] == "/media/"

    def test_default_public_base_url_is_empty(self) -> None:
        defaults = default_storage_module_options()
        assert defaults["public_base_url"] == DEFAULT_STORAGE_PUBLIC_BASE_URL
        assert defaults["public_base_url"] == ""

    def test_default_private_media_enabled_is_false(self) -> None:
        defaults = default_storage_module_options()
        assert (
            defaults["private_media_enabled"] is DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED
        )
        assert defaults["private_media_enabled"] is False

    def test_default_querystring_auth_is_false(self) -> None:
        defaults = default_storage_module_options()
        assert defaults["querystring_auth"] is False

    def test_default_cloud_fields_are_empty_strings(self) -> None:
        defaults = default_storage_module_options()
        for key in (
            "bucket_name",
            "endpoint_url",
            "region_name",
            "access_key_id",
            "secret_access_key",
            "default_acl",
        ):
            assert defaults[key] == "", f"Expected empty string for {key}"


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must match the legacy values."""

    def test_backend_constants(self) -> None:
        assert STORAGE_BACKEND_LOCAL == "local"
        assert STORAGE_BACKEND_S3 == "s3"
        assert STORAGE_BACKEND_R2 == "r2"

    def test_backends_tuple(self) -> None:
        assert set(STORAGE_BACKENDS) == {"local", "s3", "r2"}
        for b in ("local", "s3", "r2"):
            assert b in STORAGE_BACKENDS

    def test_default_constants(self) -> None:
        assert DEFAULT_STORAGE_BACKEND == "local"
        assert DEFAULT_STORAGE_MEDIA_URL == "/media/"
        assert DEFAULT_STORAGE_PUBLIC_BASE_URL == ""
        assert DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED is False

    def test_module_option_keys_frozenset(self) -> None:
        assert STORAGE_MODULE_OPTION_KEYS == frozenset(
            {
                "backend",
                "media_url",
                "public_base_url",
                "bucket_name",
                "endpoint_url",
                "region_name",
                "access_key_id",
                "secret_access_key",
                "default_acl",
                "querystring_auth",
                "private_media_enabled",
            }
        )


# ===========================================================================
# 3. Backend normalisation parity
# ===========================================================================


class TestBackendNormalizationParity:
    """Backend normalisation must mirror legacy _storage_wiring coercion."""

    def test_backend_strip(self) -> None:
        normalized = normalize_storage_module_options({"backend": "  s3  "})
        assert normalized["backend"] == "s3"

    def test_backend_lowercase(self) -> None:
        normalized = normalize_storage_module_options({"backend": "S3"})
        assert normalized["backend"] == "s3"

    def test_backend_r2_lowercase(self) -> None:
        normalized = normalize_storage_module_options({"backend": "R2"})
        assert normalized["backend"] == "r2"

    def test_backend_local_unchanged(self) -> None:
        normalized = normalize_storage_module_options({"backend": "local"})
        assert normalized["backend"] == "local"

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_storage_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_storage_module_options({})
        assert normalized == {}


# ===========================================================================
# 4. media_url normalisation parity (_normalize_media_url mirror)
# ===========================================================================


class TestMediaUrlNormalizationParity:
    """media_url normalisation must exactly mirror ``_normalize_media_url``."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Already canonical
            ("/media/", "/media/"),
            # Missing trailing slash
            ("/media", "/media/"),
            # Missing leading slash (no http prefix)
            ("media/", "/media/"),
            ("media", "/media/"),
            # Absolute URL — preserved as-is (already starts with http)
            ("https://cdn.example.com/media/", "https://cdn.example.com/media/"),
            ("https://cdn.example.com/media", "https://cdn.example.com/media/"),
            # Blank → default /media/ (empty string is falsy, so "or" fires)
            ("", "/media/"),
            # Whitespace only → legacy behaviour: ("   " or "/media/").strip() == ""
            # "" does not start with "/" or "http", so "/" is prepended → "/"
            # "/" already ends with "/" → final result is "/"
            ("   ", "/"),
            # Custom path
            ("/uploads/", "/uploads/"),
            ("/uploads", "/uploads/"),
        ],
    )
    def test_media_url_normalization(self, raw: str, expected: str) -> None:
        normalized = normalize_storage_module_options({"media_url": raw})
        assert normalized["media_url"] == expected

    def test_media_url_normalization_via_resolve(self) -> None:
        """Normalization must also apply through resolve."""
        resolved = resolve_storage_module_options({"media_url": "uploads"})
        assert resolved["media_url"] == "/uploads/"


# ===========================================================================
# 5. public_base_url normalisation parity
# ===========================================================================


class TestPublicBaseUrlNormalizationParity:
    """public_base_url normalisation must mirror the legacy strip() call."""

    def test_public_base_url_strip(self) -> None:
        normalized = normalize_storage_module_options(
            {"public_base_url": "  https://cdn.example.com  "}
        )
        assert normalized["public_base_url"] == "https://cdn.example.com"

    def test_public_base_url_empty_passes_through(self) -> None:
        normalized = normalize_storage_module_options({"public_base_url": ""})
        assert normalized["public_base_url"] == ""


# ===========================================================================
# 6. Resolution parity (defaults + normalised overrides)
# ===========================================================================


class TestResolutionParity:
    """resolve_storage_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_storage_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_storage_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_backend_s3_override(self) -> None:
        resolved = resolve_storage_module_options({"backend": "s3"})
        assert resolved["backend"] == "s3"

    def test_backend_r2_override(self) -> None:
        resolved = resolve_storage_module_options({"backend": "r2"})
        assert resolved["backend"] == "r2"

    def test_backend_uppercase_is_lowercased(self) -> None:
        resolved = resolve_storage_module_options({"backend": "S3"})
        assert resolved["backend"] == "s3"

    def test_invalid_backend_falls_back_to_local(self) -> None:
        """Invalid backend must fall back to 'local' (mirrors legacy guard)."""
        resolved = resolve_storage_module_options({"backend": "gcs"})
        assert resolved["backend"] == "local"

    def test_media_url_normalized_in_resolve(self) -> None:
        resolved = resolve_storage_module_options({"media_url": "uploads"})
        assert resolved["media_url"] == "/uploads/"

    def test_public_base_url_stripped_in_resolve(self) -> None:
        resolved = resolve_storage_module_options(
            {"public_base_url": "  https://cdn.example.com  "}
        )
        assert resolved["public_base_url"] == "https://cdn.example.com"

    def test_private_media_enabled_default_is_false(self) -> None:
        resolved = resolve_storage_module_options(None)
        assert resolved["private_media_enabled"] is False
        assert isinstance(resolved["private_media_enabled"], bool)

    def test_querystring_auth_default_is_false(self) -> None:
        resolved = resolve_storage_module_options(None)
        assert resolved["querystring_auth"] is False
        assert isinstance(resolved["querystring_auth"], bool)

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_storage_module_options(
            {"backend": "s3", "media_url": "uploads"}
        )
        assert resolve_storage_module_options(resolved) == resolved

    def test_resolved_keys_match_legacy(self) -> None:
        resolved = resolve_storage_module_options({"backend": "s3"})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_cloud_fields_default_to_empty_string_in_resolved(self) -> None:
        resolved = resolve_storage_module_options(None)
        for key in (
            "bucket_name",
            "endpoint_url",
            "region_name",
            "access_key_id",
            "secret_access_key",
            "default_acl",
        ):
            assert resolved[key] == "", f"Expected empty string for {key}"

    def test_cloud_fields_override_and_strip(self) -> None:
        resolved = resolve_storage_module_options(
            {
                "backend": "s3",
                "bucket_name": "  my-bucket  ",
                "endpoint_url": "  https://s3.example.com  ",
                "region_name": "  us-east-1  ",
                "access_key_id": "  AKIAIOSFODNN7EXAMPLE  ",
                "secret_access_key": "  wJalrXUtnFEMI/K7MDENG  ",
                "default_acl": "  public-read  ",
            }
        )
        assert resolved["bucket_name"] == "my-bucket"
        assert resolved["endpoint_url"] == "https://s3.example.com"
        assert resolved["region_name"] == "us-east-1"
        assert resolved["access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
        assert resolved["secret_access_key"] == "wJalrXUtnFEMI/K7MDENG"
        assert resolved["default_acl"] == "public-read"


# ===========================================================================
# 7. Validation parity
# ===========================================================================


class TestValidationParity:
    """validate_storage_module_options must produce legacy-compatible issues."""

    def test_defaults_pass_validation(self) -> None:
        issues = validate_storage_module_options(None)
        assert issues == []

    def test_valid_s3_backend_passes(self) -> None:
        issues = validate_storage_module_options({"backend": "s3"})
        assert issues == []

    def test_valid_r2_backend_passes(self) -> None:
        issues = validate_storage_module_options({"backend": "r2"})
        assert issues == []

    def test_valid_local_backend_passes(self) -> None:
        issues = validate_storage_module_options({"backend": "local"})
        assert issues == []

    @pytest.mark.parametrize("invalid_backend", ["gcs", "azure", "ftp", "S3GCS"])
    def test_invalid_backend_fails_validation(self, invalid_backend: str) -> None:
        issues = validate_storage_module_options({"backend": invalid_backend})
        assert len(issues) >= 1
        assert any("backend" in i for i in issues)
        assert any("local" in i and "s3" in i and "r2" in i for i in issues)

    def test_valid_backends_parametrized(self) -> None:
        for valid_backend in ("local", "s3", "r2"):
            issues = validate_storage_module_options({"backend": valid_backend})
            assert issues == [], f"Expected no issues for backend={valid_backend!r}"

    def test_case_insensitive_backend_passes_validation(self) -> None:
        """Mixed-case valid backends are normalized before validation."""
        assert validate_storage_module_options({"backend": "S3"}) == []
        assert validate_storage_module_options({"backend": "R2"}) == []
        assert validate_storage_module_options({"backend": "Local"}) == []


# ===========================================================================
# 8. Wiring-field values parity (B-phase scope only)
# ===========================================================================


class TestWiringFieldsParity:
    """Resolved options must project to the exact wiring field values that
    ``_storage_wiring`` would have computed for the B-phase option set."""

    def test_default_backend_setting(self) -> None:
        resolved = resolve_storage_module_options(None)
        # Mirrors: backend = str(options.get("backend", "local")).lower()
        assert resolved["backend"] == "local"

    def test_default_media_url_setting(self) -> None:
        resolved = resolve_storage_module_options(None)
        # Mirrors: media_url = _normalize_media_url(str(options.get("media_url", "/media/")))
        assert resolved["media_url"] == "/media/"

    def test_default_public_base_url_setting(self) -> None:
        resolved = resolve_storage_module_options(None)
        # Mirrors: public_base_url = str(options.get("public_base_url", "")).strip()
        assert resolved["public_base_url"] == ""

    def test_default_private_media_enabled_setting(self) -> None:
        resolved = resolve_storage_module_options(None)
        # Mirrors: bool(options.get("private_media_enabled", False))
        assert resolved["private_media_enabled"] is False

    def test_resolved_contains_b_phase_wiring_keys(self) -> None:
        resolved = resolve_storage_module_options(None)
        b_phase_keys = {
            "backend",
            "media_url",
            "public_base_url",
            "private_media_enabled",
        }
        assert b_phase_keys.issubset(set(resolved.keys()))

    def test_s3_backend_wiring(self) -> None:
        """S3 backend should resolve correctly in the option dict."""
        resolved = resolve_storage_module_options(
            {
                "backend": "s3",
                "bucket_name": "my-bucket",
                "querystring_auth": True,
            }
        )
        assert resolved["backend"] == "s3"
        assert resolved["bucket_name"] == "my-bucket"
        assert resolved["querystring_auth"] is True

    def test_r2_backend_wiring(self) -> None:
        resolved = resolve_storage_module_options(
            {
                "backend": "r2",
                "endpoint_url": "https://r2.example.com",
                "bucket_name": "my-r2-bucket",
            }
        )
        assert resolved["backend"] == "r2"
        assert resolved["endpoint_url"] == "https://r2.example.com"
        assert resolved["bucket_name"] == "my-r2-bucket"

    @pytest.mark.parametrize("valid_backend", list(STORAGE_BACKENDS))
    def test_every_valid_backend_resolves_correctly(self, valid_backend: str) -> None:
        resolved = resolve_storage_module_options({"backend": valid_backend})
        assert resolved["backend"] == valid_backend
