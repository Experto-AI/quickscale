"""Tests for quickscale_core.contracts.resolvers per-module option functions.

Covers the resolve_*_module_options, validate_*_module_options,
default_*_module_options, and production-targeted helpers for every
QuickScale module.  Manifest I/O is mocked so these tests exercise
the resolver/wiring logic without requiring module.yml files on disk.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.contracts.resolvers import (
    # Analytics
    analytics_production_targeted,
    default_analytics_module_options,
    resolve_analytics_module_options,
    validate_analytics_env_var_reference,
    validate_analytics_module_options,
    # Auth
    default_auth_module_options,
    format_auth_desired_config_contract,
    resolve_auth_module_options,
    # Backups
    default_backups_module_options,
    resolve_backups_module_options,
    # Billing
    billing_production_targeted,
    default_billing_module_options,
    resolve_billing_module_options,
    validate_billing_env_var_reference,
    validate_billing_currency,
    validate_billing_module_options,
    # Blog
    BLOG_MODULE_OPTION_KEYS,
    DEFAULT_BLOG_API_RATE_LIMIT,
    DEFAULT_BLOG_ENABLE_RSS,
    DEFAULT_BLOG_POSTS_PER_PAGE,
    default_blog_module_options,
    normalize_blog_module_options,
    resolve_blog_module_options,
    validate_blog_module_options,
    # CRM
    LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION,
    default_crm_module_options,
    normalize_crm_module_options,
    resolve_crm_module_options,
    validate_crm_module_options,
    # Forms
    default_forms_module_options,
    normalize_forms_module_options,
    resolve_forms_module_options,
    validate_forms_module_options,
    # Notifications
    default_notifications_module_options,
    notifications_live_delivery_configured,
    notifications_production_targeted,
    notifications_runtime_email_backend,
    resolve_notifications_module_options,
    validate_notifications_module_options,
    # Orgs
    default_orgs_module_options,
    normalize_orgs_module_options,
    resolve_orgs_module_options,
    validate_orgs_module_options,
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
from quickscale_core.schema.config_schema import ConfigValidationError

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
# Analytics
# ===================================================================


class TestResolversAnalytics:
    """Tests for analytics module resolver/validate/default functions."""

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_analytics(self, mock_load: MagicMock) -> None:
        """default_analytics_module_options returns manifest defaults."""
        mock_load.return_value = _make_mock_manifest(
            "analytics", {"provider": "posthog", "enabled": True}
        )
        result = default_analytics_module_options()
        assert result["provider"] == "posthog"
        assert result["enabled"] is True

    def test_validate_analytics_env_var_reference(self) -> None:
        """validate_analytics_env_var_reference validates env var names."""
        assert validate_analytics_env_var_reference("key", "") is None
        assert validate_analytics_env_var_reference("key", "MY_VAR") is None
        result = validate_analytics_env_var_reference("key", "bad-name")
        assert result is not None
        assert "modules.analytics.key" in result

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_analytics_with_options(self, mock_load: MagicMock) -> None:
        """resolve_analytics_module_options normalises options and resolves."""
        mock_load.return_value = _make_mock_manifest(
            "analytics",
            {
                "provider": "posthog",
                "enabled": True,
                "exclude_debug": False,
                "exclude_staff": False,
                "anonymous_by_default": True,
                "posthog_api_key_env_var": "PH_KEY",
                "posthog_host_env_var": "PH_HOST",
                "posthog_host": "https://us.i.posthog.com",
            },
        )
        result = resolve_analytics_module_options({"provider": "  PostHog "})
        assert result["provider"] == "posthog"
        assert result["enabled"] is True
        assert result["posthog_host"] == "https://us.i.posthog.com"
        assert result["posthog_api_key_env_var"] == "PH_KEY"

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_analytics_valid(self, mock_load: MagicMock) -> None:
        """validate_analytics_module_options returns no issues for valid config."""
        mock_load.return_value = _make_mock_manifest(
            "analytics",
            {
                "provider": "posthog",
                "enabled": True,
                "exclude_debug": False,
                "exclude_staff": False,
                "anonymous_by_default": True,
                "posthog_host": "https://us.i.posthog.com",
            },
        )
        assert validate_analytics_module_options(None) == []

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_analytics_invalid_options(self, mock_load: MagicMock) -> None:
        """validate_analytics_module_options reports invalid options."""
        mock_load.return_value = _make_mock_manifest(
            "analytics",
            {
                "provider": "posthog",
                "enabled": "not_bool",
                "exclude_debug": "also_not_bool",
                "exclude_staff": False,
                "anonymous_by_default": True,
                "posthog_host": "",
            },
        )
        issues = validate_analytics_module_options(None)
        assert len(issues) >= 2

    @patch(_MANIFEST_PATCH_PATH)
    def test_analytics_production_targeted(self, mock_load: MagicMock) -> None:
        """analytics_production_targeted detects production-readiness."""
        mock_load.return_value = _make_mock_manifest(
            "analytics",
            {
                "enabled": True,
                "posthog_api_key_env_var": "MY_KEY",
                "provider": "posthog",
            },
        )
        assert (
            analytics_production_targeted(
                {"enabled": True, "posthog_api_key_env_var": "MY_KEY"}
            )
            is True
        )
        # Disabled is not production-targeted
        assert analytics_production_targeted({"enabled": False}) is False


# ===================================================================
# Auth
# ===================================================================


class TestResolversAuth:
    """Tests for auth module resolver functions."""

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_auth(self, mock_load: MagicMock) -> None:
        """default_auth_module_options returns manifest defaults."""
        mock_load.return_value = _make_mock_manifest(
            "auth", {"registration_enabled": True}
        )
        result = default_auth_module_options()
        assert result["registration_enabled"] is True

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_auth(self, mock_load: MagicMock) -> None:
        """resolve_auth_module_options normalises and resolves auth options."""
        mock_load.return_value = _make_mock_manifest(
            "auth", {"registration_enabled": True}
        )
        result = resolve_auth_module_options(None)
        assert result["registration_enabled"] is True

    def test_resolve_auth_with_legacy_key_raises(self) -> None:
        """resolve_auth_module_options raises on legacy allow_registration."""
        with pytest.raises(ConfigValidationError, match="allow_registration"):
            resolve_auth_module_options({"allow_registration": False})

    def test_format_auth_contract(self) -> None:
        """format_auth_desired_config_contract returns expected text."""
        text = format_auth_desired_config_contract()
        assert "registration_enabled" in text
        assert "authentication_method" in text
        assert "allow_registration" in text


# ===================================================================
# Backups
# ===================================================================


class TestResolversBackups:
    """Tests for backups module resolver functions."""

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_backups(self, mock_load: MagicMock) -> None:
        """default_backups_module_options returns manifest defaults."""
        mock_load.return_value = _make_mock_manifest(
            "backups", {"remote_enabled": True}
        )
        result = default_backups_module_options()
        assert result["remote_enabled"] is True

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_backups(self, mock_load: MagicMock) -> None:
        """resolve_backups_module_options merges defaults with overrides."""
        mock_load.return_value = _make_mock_manifest(
            "backups", {"remote_enabled": False, "keep_local": True}
        )
        result = resolve_backups_module_options({"remote_enabled": True})
        assert result["remote_enabled"] is True
        assert result["keep_local"] is True


# ===================================================================
# Billing
# ===================================================================


class TestResolversBilling:
    """Tests for billing module resolver/validate functions."""

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_billing(self, mock_load: MagicMock) -> None:
        """default_billing_module_options returns manifest defaults."""
        mock_load.return_value = _make_mock_manifest(
            "billing", {"enabled": True, "billing_currency": "usd"}
        )
        result = default_billing_module_options()
        assert result["enabled"] is True
        assert result["billing_currency"] == "usd"

    def test_validate_billing_env_var_reference(self) -> None:
        """validate_billing_env_var_reference validates env var names."""
        assert validate_billing_env_var_reference("key", "") is None
        assert validate_billing_env_var_reference("key", "MY_VAR") is None
        result = validate_billing_env_var_reference("key", "123bad")
        assert result is not None

    def test_validate_billing_currency(self) -> None:
        """validate_billing_currency validates currency codes."""
        assert validate_billing_currency("usd") is None
        result_blank = validate_billing_currency("")
        assert result_blank is not None
        assert "blank" in result_blank
        result_unsupported = validate_billing_currency("XYZ")
        assert result_unsupported is not None
        assert "supported" in result_unsupported

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_billing_with_options(self, mock_load: MagicMock) -> None:
        """resolve_billing_module_options resolves and normalizes."""
        mock_load.return_value = _make_mock_manifest(
            "billing",
            {
                "enabled": True,
                "billing_currency": "usd",
                "publishable_key_env_var": "PK_KEY",
                "secret_key_env_var": "SK_KEY",
                "webhook_secret_env_var": "WH_SECRET",
            },
        )
        result = resolve_billing_module_options({"billing_currency": "  EUR "})
        assert result["billing_currency"] == "eur"
        assert result["enabled"] is True

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_billing_module_options(self, mock_load: MagicMock) -> None:
        """validate_billing_module_options identifies issues."""
        mock_load.return_value = _make_mock_manifest(
            "billing",
            {
                "enabled": True,
                "billing_currency": "usd",
                "publishable_key_env_var": "PK_KEY",
                "secret_key_env_var": "SK_KEY",
                "webhook_secret_env_var": "WH_SECRET",
            },
        )
        issues = validate_billing_module_options(None)
        assert issues == []

    @patch(_MANIFEST_PATCH_PATH)
    def test_billing_production_targeted(self, mock_load: MagicMock) -> None:
        """billing_production_targeted detects production-readiness."""
        mock_load.return_value = _make_mock_manifest(
            "billing",
            {
                "enabled": True,
                "billing_currency": "usd",
                "publishable_key_env_var": "PK_KEY",
                "secret_key_env_var": "SK_KEY",
                "webhook_secret_env_var": "WH_SECRET",
            },
        )
        assert (
            billing_production_targeted(
                {
                    "enabled": True,
                    "billing_currency": "usd",
                    "publishable_key_env_var": "PK_KEY",
                }
            )
            is True
        )
        assert billing_production_targeted({"enabled": False}) is False


# ===================================================================
# Blog
# ===================================================================


class TestResolversBlog:
    """Tests for blog module option functions."""

    def test_constants(self) -> None:
        assert DEFAULT_BLOG_POSTS_PER_PAGE == 10
        assert DEFAULT_BLOG_ENABLE_RSS is True
        assert DEFAULT_BLOG_API_RATE_LIMIT == "5/hour"
        assert "posts_per_page" in BLOG_MODULE_OPTION_KEYS

    def test_normalize_blog_keeps_api_rate_limit(self) -> None:
        result = normalize_blog_module_options({"api_rate_limit": "  10/minute  "})
        assert result["api_rate_limit"] == "10/minute"

    def test_normalize_blog_empty_api_rate_limit_passes_through(self) -> None:
        result = normalize_blog_module_options({"api_rate_limit": "  "})
        assert result["api_rate_limit"] == ""

    def test_normalize_blog_none_returns_empty(self) -> None:
        assert normalize_blog_module_options(None) == {}

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_blog(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "blog",
            {"posts_per_page": 10, "enable_rss": True, "api_rate_limit": "5/hour"},
        )
        result = default_blog_module_options()
        assert result["posts_per_page"] == 10

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_blog(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "blog",
            {"posts_per_page": 10, "enable_rss": True, "api_rate_limit": "5/hour"},
        )
        result = resolve_blog_module_options({"posts_per_page": 20})
        assert result["posts_per_page"] == 20
        assert result["enable_rss"] is True

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_blog_valid(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "blog",
            {"posts_per_page": 10, "enable_rss": True, "api_rate_limit": "5/hour"},
        )
        assert validate_blog_module_options(None) == []

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_blog_invalid_posts(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "blog",
            {"posts_per_page": -1, "enable_rss": True, "api_rate_limit": "5/hour"},
        )
        issues = validate_blog_module_options(None)
        assert any("posts_per_page" in i for i in issues)


# ===================================================================
# CRM
# ===================================================================


class TestResolversCrm:
    """Tests for CRM module option functions."""

    def test_legacy_constant(self) -> None:
        assert LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION == "default_pipeline_stages"

    def test_normalize_crm_legacy_raises(self) -> None:
        """normalize_crm_module_options raises on default_pipeline_stages."""
        with pytest.raises(ConfigValidationError, match="default_pipeline_stages"):
            normalize_crm_module_options(
                {"default_pipeline_stages": ["new"], "deals_per_page": 25}
            )

    def test_normalize_crm_canonical_keys_preserved(self) -> None:
        """Canonical CRM keys pass through normalize_crm_module_options."""
        result = normalize_crm_module_options({"deals_per_page": 25})
        assert result["deals_per_page"] == 25

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_crm(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "crm", {"deals_per_page": 25, "contacts_per_page": 50}
        )
        result = default_crm_module_options()
        assert result["deals_per_page"] == 25

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_crm(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "crm", {"deals_per_page": 25, "contacts_per_page": 50, "enable_api": True}
        )
        result = resolve_crm_module_options({"deals_per_page": 10})
        assert result["deals_per_page"] == 10
        assert result["contacts_per_page"] == 50

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_crm_invalid_enable_api(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "crm", {"deals_per_page": 25, "contacts_per_page": 50, "enable_api": True}
        )
        issues = validate_crm_module_options({"enable_api": "not_bool"})
        assert any("enable_api" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_crm_invalid_counts(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "crm", {"deals_per_page": 0, "contacts_per_page": 0, "enable_api": True}
        )
        issues = validate_crm_module_options(None)
        assert any("deals_per_page" in i for i in issues)
        assert any("contacts_per_page" in i for i in issues)


# ===================================================================
# Forms
# ===================================================================


class TestResolversForms:
    """Tests for Forms module option functions."""

    def test_normalize_forms_strips_rate_limit(self) -> None:
        result = normalize_forms_module_options({"rate_limit": "  10/hour  "})
        assert result["rate_limit"] == "10/hour"

    def test_normalize_forms_none_returns_empty(self) -> None:
        assert normalize_forms_module_options(None) == {}

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_forms(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "forms",
            {
                "forms_per_page": 25,
                "spam_protection_enabled": True,
                "rate_limit": "5/hour",
                "data_retention_days": 365,
                "submissions_api_enabled": True,
            },
        )
        result = default_forms_module_options()
        assert result["forms_per_page"] == 25

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_forms(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "forms",
            {
                "forms_per_page": "25",
                "spam_protection_enabled": True,
                "rate_limit": "5/hour",
                "data_retention_days": "365",
                "submissions_api_enabled": True,
            },
        )
        result = resolve_forms_module_options({"forms_per_page": 10})
        assert result["forms_per_page"] == 10

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_forms_valid(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "forms",
            {
                "forms_per_page": 25,
                "spam_protection_enabled": True,
                "rate_limit": "5/hour",
                "data_retention_days": 365,
                "submissions_api_enabled": True,
            },
        )
        assert validate_forms_module_options(None) == []

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_forms_invalid_rate_limit(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "forms",
            {
                "forms_per_page": 25,
                "spam_protection_enabled": True,
                "rate_limit": "",
                "data_retention_days": 365,
                "submissions_api_enabled": True,
            },
        )
        issues = validate_forms_module_options(None)
        assert any("rate_limit" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_forms_negative_data_retention(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest(
            "forms",
            {
                "forms_per_page": 25,
                "spam_protection_enabled": True,
                "rate_limit": "5/hour",
                "data_retention_days": -1,
                "submissions_api_enabled": True,
            },
        )
        issues = validate_forms_module_options(None)
        assert any("data_retention_days" in i for i in issues)

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_forms_zero_forms_per_page(self, mock_load: MagicMock) -> None:
        """validate_forms reports issue for forms_per_page < 1."""
        mock_load.return_value = _make_mock_manifest(
            "forms",
            {
                "forms_per_page": 0,
                "spam_protection_enabled": True,
                "rate_limit": "5/hour",
                "data_retention_days": 365,
                "submissions_api_enabled": True,
            },
        )
        issues = validate_forms_module_options(None)
        assert any("forms_per_page" in i for i in issues)


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

    @patch("quickscale_core.contracts.resolvers.get_bundled_manifests_path")
    @patch("quickscale_core.contracts.resolvers.get_modules_base_path")
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

    @patch("quickscale_core.contracts.resolvers.get_bundled_manifests_path")
    @patch("quickscale_core.contracts.resolvers.get_modules_base_path")
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
# Orgs
# ===================================================================


class TestResolversOrgs:
    """Tests for Orgs module option functions."""

    def test_normalize_orgs_lowers_mode(self) -> None:
        result = normalize_orgs_module_options({"mode": "  Multi "})
        assert result["mode"] == "multi"

    def test_normalize_orgs_none_returns_empty(self) -> None:
        assert normalize_orgs_module_options(None) == {}

    @patch(_MANIFEST_PATCH_PATH)
    def test_default_orgs(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest("orgs", {"mode": "solo"})
        result = default_orgs_module_options()
        assert result["mode"] == "solo"

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_orgs(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest("orgs", {"mode": "solo"})
        result = resolve_orgs_module_options({"mode": "saas"})
        assert result["mode"] == "saas"

    @patch(_MANIFEST_PATCH_PATH)
    def test_resolve_orgs_passes_through_invalid_mode(
        self, mock_load: MagicMock
    ) -> None:
        mock_load.return_value = _make_mock_manifest("orgs", {"mode": "solo"})
        result = resolve_orgs_module_options({"mode": "unknown"})
        # SA27: silent coercion removed; invalid mode passes through.
        # Validation is now gated at the apply path via _validate_module_prerequisites
        # and at the assembler via validation_issues.
        assert result["mode"] == "unknown"

    @patch(_MANIFEST_PATCH_PATH)
    def test_validate_orgs_invalid_mode(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _make_mock_manifest("orgs", {"mode": "unknown"})
        issues = validate_orgs_module_options(None)
        assert any("mode" in i for i in issues)


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
