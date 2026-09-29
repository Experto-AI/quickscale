"""Tests for quickscale_core.contracts.resolvers option functions.

Covers the shared manifest resolution surface and the remaining per-module
``resolve_*_module_options``/``default_*_module_options``/``validate_*``
helpers.  Manifest I/O is mocked so these tests exercise the resolver/wiring
logic without requiring module.yml files on disk.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from quickscale_core.contracts.resolvers import (
    # Shared manifest resolution
    resolve_manifest_module_options,
    # Notifications
    default_notifications_module_options,
    notifications_live_delivery_configured,
    notifications_production_targeted,
    notifications_runtime_email_backend,
    resolve_notifications_module_options,
    validate_notifications_module_options,
    # Social
    default_social_module_options,
    normalize_social_provider,
    normalize_social_provider_allowlist,
    resolve_social_module_options,
    validate_social_module_options,
    # Storage
    default_storage_module_options,
    normalize_storage_module_options,
    resolve_storage_module_options,
    validate_storage_module_options,
)
from quickscale_core.contracts.module_discovery import ImproperlyConfigured

from quickscale_core.manifest.schema import ModuleManifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_manifest(
    name: str = "analytics",
    defaults: dict | None = None,
) -> MagicMock:
    manifest = MagicMock(spec=ModuleManifest)
    manifest.name = name
    manifest.get_defaults.return_value = defaults or {}
    manifest.managed_files = {}
    # SA5.1: manifest bridge reads derivation attributes from the manifest.
    manifest.wiring_projections = None
    manifest.derived_settings = None
    manifest.option_derivations = None
    return manifest


_MANIFEST_PATCH_PATH = "quickscale_core.contracts.resolvers.load_manifest_from_path"


# ===================================================================
# Shared manifest resolution
# ===================================================================


class TestResolveManifestModuleOptions:
    """The one generic resolver converted modules' callers share."""

    @patch(_MANIFEST_PATCH_PATH)
    def test_returns_manifest_defaults(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "analytics", {"enabled": True, "provider": "posthog"}
        )
        assert resolve_manifest_module_options("analytics") == {
            "enabled": True,
            "provider": "posthog",
        }

    @patch(_MANIFEST_PATCH_PATH)
    def test_overrides_replace_defaults(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "billing", {"enabled": True, "billing_currency": "usd"}
        )
        result = resolve_manifest_module_options("billing", {"enabled": False})
        assert result == {"enabled": False, "billing_currency": "usd"}


# ===================================================================
# Notifications
# ===================================================================


class TestResolversNotifications:
    """Tests for Notifications module resolver/validate/production helpers."""

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_notifications(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "My App",
                "sender_email": "noreply@example.com",
            },
        )
        result = default_notifications_module_options()
        assert result["sender_name"] == "My App"

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_notifications(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "My App",
                "sender_email": "noreply@example.com",
                "resend_domain": "",
                "default_tags": [],
                "allowed_tags": [],
                "reply_to_email": None,
            },
        )
        result = resolve_notifications_module_options({"sender_name": "Updated"})
        assert result["sender_name"] == "Updated"
        assert result["reply_to_email"] == ""

    @patch(_MANIFEST_PATCH_PATH)
    def test_notifications_production_targeted(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "hello@example.com",
                "resend_domain": "example.com",
            },
        )
        assert (
            notifications_production_targeted(
                {
                    "enabled": True,
                    "sender_name": "App",
                    "sender_email": "hello@example.com",
                    "resend_domain": "example.com",
                }
            )
            is True
        )
        assert notifications_production_targeted({"enabled": False}) is False

    @patch(_MANIFEST_PATCH_PATH)
    def test_notifications_live_delivery_configured(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "hello@example.com",
                "resend_domain": "example.com",
                "resend_api_key_env_var": "MY_KEY",
            },
        )
        result = notifications_live_delivery_configured(
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "hello@example.com",
                "resend_domain": "example.com",
                "resend_api_key_env_var": "MY_KEY",
            }
        )
        assert result is True

    @patch(_MANIFEST_PATCH_PATH)
    def test_notifications_runtime_email_backend(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "hello@example.com",
                "resend_domain": "example.com",
                "resend_api_key_env_var": "MY_KEY",
            },
        )
        backend = notifications_runtime_email_backend(
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "hello@example.com",
                "resend_domain": "example.com",
                "resend_api_key_env_var": "MY_KEY",
            }
        )
        from quickscale_core.contracts.module_options import (
            NOTIFICATIONS_LIVE_EMAIL_BACKEND,
        )

        assert backend == NOTIFICATIONS_LIVE_EMAIL_BACKEND

        # Disabled returns None
        assert notifications_runtime_email_backend({"enabled": False}) is None

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_notifications_empty_sender(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "",
                "sender_email": "",
                "resend_domain": "",
                "default_tags": [],
                "allowed_tags": [],
                "webhook_ttl_seconds": 300,
            },
        )
        issues = validate_notifications_module_options(None)
        assert any("sender_name" in i for i in issues)
        assert any("sender_email" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_notifications_placeholder_email_with_resend(
        self, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "noreply@example.com",
                "resend_domain": "example.com",
                "resend_api_key_env_var": "",
                "default_tags": [],
                "allowed_tags": ["general"],
                "webhook_ttl_seconds": 300,
            },
        )
        issues = validate_notifications_module_options(
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "noreply@example.com",
                "resend_domain": "example.com",
            }
        )
        # Should flag placeholder email with resend_domain set
        assert any("placeholder" in i.lower() or "noreply" in i.lower() for i in issues)

    # ------------------------------------------------------------------
    # Bundled-manifest fallback (SA111a fix)
    # ------------------------------------------------------------------

    @patch("quickscale_core.contracts.module_discovery.get_bundled_manifests_path")
    @patch("quickscale_core.contracts.module_discovery.get_modules_base_path")
    @patch(_MANIFEST_PATCH_PATH)
    def test_default_notifications_fallback_on_improperly_configured(
        self,
        mock_load: MagicMock,
        mock_get_base: MagicMock,
        mock_get_bundled: MagicMock,
    ) -> None:
        """default_notifications_module_options falls back to bundled
        manifest when get_modules_base_path raises ImproperlyConfigured
        (installed-wheel context without source-tree modules workspace)."""
        mock_get_base.side_effect = ImproperlyConfigured(
            "Modules base path not found: expected ..."
        )
        mock_get_bundled.return_value = Path("/bundled/manifests")
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "noreply@example.com",
            },
        )

        result = default_notifications_module_options()
        assert result["sender_name"] == "App"

        # Verify the bundled path was used for manifest loading.
        bundled_call_path = str(mock_load.call_args[0][0])
        assert "/bundled/manifests" in bundled_call_path
        assert "notifications" in bundled_call_path

    @patch("quickscale_core.contracts.module_discovery.get_bundled_manifests_path")
    @patch("quickscale_core.contracts.module_discovery.get_modules_base_path")
    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_notifications_fallback_on_improperly_configured(
        self,
        mock_load: MagicMock,
        mock_get_base: MagicMock,
        mock_get_bundled: MagicMock,
    ) -> None:
        """resolve_notifications_module_options also falls back to bundled
        manifests when get_modules_base_path raises ImproperlyConfigured."""
        mock_get_base.side_effect = ImproperlyConfigured(
            "Modules base path not found: expected ..."
        )
        mock_get_bundled.return_value = Path("/bundled/manifests")
        mock_load.return_value = _make_mock_manifest(
            "notifications",
            {
                "enabled": True,
                "sender_name": "App",
                "sender_email": "noreply@example.com",
                "resend_domain": "",
                "default_tags": [],
                "allowed_tags": [],
                "reply_to_email": None,
            },
        )

        result = resolve_notifications_module_options({"sender_name": "Updated"})
        assert result["sender_name"] == "Updated"

        # Verify the bundled path was used for manifest loading.
        bundled_call_path = str(mock_load.call_args[0][0])
        assert "/bundled/manifests" in bundled_call_path
        assert "notifications" in bundled_call_path


# ===================================================================
# Social
# ===================================================================


class TestResolversSocial:
    """Tests for Social module resolver/validate functions."""

    def test_normalize_social_provider(self) -> None:
        assert normalize_social_provider("facebook") == "facebook"
        assert normalize_social_provider("FB") == "facebook"
        assert normalize_social_provider("twitter") == "x"
        assert normalize_social_provider("x-twitter") == "x"
        assert normalize_social_provider("") is None
        assert normalize_social_provider("!!!") is None

    def test_normalize_social_provider_allowlist(self) -> None:
        result = normalize_social_provider_allowlist(
            ["Facebook", "twitter", "instagram"]
        )
        assert "facebook" in result
        assert "x" in result
        assert "instagram" in result
        # Deduplication
        result2 = normalize_social_provider_allowlist(["fb", "facebook"])
        assert result2.count("facebook") == 1

    def test_normalize_social_provider_allowlist_string(self) -> None:
        result = normalize_social_provider_allowlist("facebook,instagram")
        assert "facebook" in result
        assert "instagram" in result

    def test_normalize_social_provider_allowlist_none(self) -> None:
        assert normalize_social_provider_allowlist(None) == []

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_social(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": True,
                "embeds_enabled": True,
                "layout_variant": "list",
                "provider_allowlist": [],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        result = default_social_module_options()
        assert result["link_tree_enabled"] is True

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_social(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": True,
                "embeds_enabled": False,
                "layout_variant": "list",
                "provider_allowlist": [],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        result = resolve_social_module_options({"layout_variant": "  Grid "})
        assert result["layout_variant"] == "grid"

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_social_missing_link_tree_and_embeds(
        self, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": False,
                "embeds_enabled": False,
                "layout_variant": "list",
                "provider_allowlist": [],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        issues = validate_social_module_options(None)
        assert any("link_tree_enabled" in i or "embeds_enabled" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_social_positive(self, mock_load: MagicMock) -> None:
        """validate_social_module_options returns no issues for valid config."""
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": True,
                "embeds_enabled": True,
                "layout_variant": "list",
                "provider_allowlist": [],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        issues = validate_social_module_options(
            {
                "link_tree_enabled": True,
                "embeds_enabled": True,
                "layout_variant": "list",
                "provider_allowlist": ["youtube", "facebook"],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            }
        )
        assert issues == []

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_social_invalid_layout(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": True,
                "embeds_enabled": True,
                "layout_variant": "bogus",
                "provider_allowlist": ["facebook"],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        issues = validate_social_module_options(None)
        assert any("layout_variant" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_social_unknown_providers(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": True,
                "embeds_enabled": False,
                "layout_variant": "list",
                "provider_allowlist": [],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        issues = validate_social_module_options(
            {
                "link_tree_enabled": True,
                "embeds_enabled": False,
                "layout_variant": "list",
                "provider_allowlist": ["unknown_provider"],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            }
        )
        assert any("unsupported" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_social_embeds_no_embed_providers(
        self, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": True,
                "embeds_enabled": True,
                "layout_variant": "list",
                "provider_allowlist": [],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        issues = validate_social_module_options(
            {
                "link_tree_enabled": True,
                "embeds_enabled": True,
                "layout_variant": "list",
                "provider_allowlist": ["facebook"],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            }
        )
        assert any("tiktok" in i or "youtube" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_social_non_bool_flags(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "social",
            {
                "link_tree_enabled": "yes",
                "embeds_enabled": "no",
                "layout_variant": "list",
                "provider_allowlist": ["facebook"],
                "cache_ttl_seconds": 300,
                "links_per_page": 24,
                "embeds_per_page": 12,
            },
        )
        issues = validate_social_module_options(None)
        assert any("link_tree_enabled" in i for i in issues)
        assert any("embeds_enabled" in i for i in issues)


# ===================================================================
# Storage
# ===================================================================


class TestResolversStorage:
    """Tests for Storage module option functions."""

    def test_normalize_storage_none_returns_empty(self) -> None:
        assert normalize_storage_module_options(None) == {}

    def test_normalize_storage_lowers_backend(self) -> None:
        result = normalize_storage_module_options({"backend": "  S3 "})
        assert result["backend"] == "  s3 "

    def test_normalize_storage_normalizes_media_url(self) -> None:
        result = normalize_storage_module_options({"media_url": "media"})
        assert result["media_url"] == "/media/"

    def test_normalize_storage_strips_keys(self) -> None:
        result = normalize_storage_module_options(
            {
                "bucket_name": "  my-bucket  ",
                "public_base_url": "  https://cdn.example.com  ",
            }
        )
        assert result["bucket_name"] == "my-bucket"
        assert result["public_base_url"] == "https://cdn.example.com"

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_storage(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "storage", {"backend": "local", "media_url": "/media/"}
        )
        result = default_storage_module_options()
        assert result["backend"] == "local"

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_storage(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "storage",
            {
                "backend": "local",
                "media_url": "/media/",
                "public_base_url": "",
                "private_media_enabled": False,
                "querystring_auth": False,
            },
        )
        result = resolve_storage_module_options({"backend": "s3"})
        assert result["backend"] == "s3"

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_storage_unknown_backend_passes_through(
        self, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = _make_mock_manifest(
            "storage", {"backend": "local", "media_url": "/media/"}
        )
        result = resolve_storage_module_options({"backend": "unknown"})
        # SA27: silent coercion removed; invalid backend passes through.
        assert result["backend"] == "unknown"

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_storage_valid(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "storage",
            {
                "backend": "local",
                "private_media_enabled": False,
                "media_url": "/media/",
            },
        )
        assert validate_storage_module_options(None) == []

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_storage_invalid_backend(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "storage",
            {
                "backend": "unknown",
                "private_media_enabled": False,
                "media_url": "/media/",
            },
        )
        issues = validate_storage_module_options(None)
        assert any("backend" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_storage_non_bool_private_media(
        self, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = _make_mock_manifest(
            "storage",
            {
                "backend": "local",
                "private_media_enabled": "yes",
                "media_url": "/media/",
            },
        )
        issues = validate_storage_module_options(None)
        assert any("private_media_enabled" in i for i in issues)
