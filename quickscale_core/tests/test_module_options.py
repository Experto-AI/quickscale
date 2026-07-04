"""Tests for quickscale_core.contracts.module_options.

Covers normalize, validate, sanitize, and helper functions that form the
central module-options contract surface.
"""

from __future__ import annotations


import pytest

from quickscale_core.contracts.module_options import (
    ANALYTICS_PROVIDERS,
    AUTH_REGISTRATION_ENABLED_OPTION,
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    BILLING_SUPPORTED_CURRENCIES,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    ENV_VAR_PORTABILITY_IGNORED,
    ENV_VAR_PORTABILITY_MANUAL,
    ENV_VAR_PORTABILITY_PORTABLE,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    format_auth_desired_config_contract,
    get_env_var_portability,
    has_legacy_backups_secret_values,
    normalize_analytics_module_options,
    normalize_auth_module_options,
    normalize_backups_module_options,
    normalize_billing_module_options,
    normalize_crm_module_options,
    normalize_notifications_module_options,
    normalize_social_module_options,
    sanitize_module_options,
    validate_analytics_env_var_reference,
    validate_analytics_module_options,
    validate_auth_module_options,
    validate_backups_env_var_reference,
    validate_billing_currency,
    validate_billing_env_var_reference,
    validate_billing_module_options,
    validate_notifications_env_var_reference,
    validate_notifications_module_options,
    validate_social_module_options,
)
from quickscale_core.schema.config_schema import ConfigValidationError


# ---------------------------------------------------------------------------
# normalize_analytics_module_options
# ---------------------------------------------------------------------------


class TestNormalizeAnalytics:
    def test_none_options_returns_empty(self) -> None:
        assert normalize_analytics_module_options(None) == {}

    def test_provider_lowered_and_stripped(self) -> None:
        result = normalize_analytics_module_options({"provider": "  PostHog "})
        assert result["provider"] == "posthog"

    def test_env_var_options_stripped(self) -> None:
        result = normalize_analytics_module_options(
            {"posthog_api_key_env_var": "  MY_KEY  ", "posthog_host_env_var": "  H "}
        )
        assert result["posthog_api_key_env_var"] == "MY_KEY"
        assert result["posthog_host_env_var"] == "H"

    def test_posthog_host_gets_https_prefix(self) -> None:
        result = normalize_analytics_module_options(
            {"posthog_host": "  us.i.posthog.com/  "}
        )
        assert result["posthog_host"] == "https://us.i.posthog.com"

    def test_posthog_host_preserves_existing_scheme(self) -> None:
        result = normalize_analytics_module_options(
            {"posthog_host": "https://eu.i.posthog.com"}
        )
        assert result["posthog_host"] == "https://eu.i.posthog.com"

    def test_posthog_host_http_preserved(self) -> None:
        result = normalize_analytics_module_options(
            {"posthog_host": "http://localhost:8080"}
        )
        assert result["posthog_host"] == "http://localhost:8080"

    def test_empty_posthog_host_stays_empty(self) -> None:
        result = normalize_analytics_module_options({"posthog_host": "  "})
        assert result["posthog_host"] == ""


# ---------------------------------------------------------------------------
# normalize_auth_module_options
# ---------------------------------------------------------------------------


class TestNormalizeAuth:
    def test_none_options_returns_empty(self) -> None:
        assert normalize_auth_module_options(None) == {}

    def test_legacy_allow_registration_raises(self) -> None:
        """allow_registration raises ConfigValidationError instead of silent migration."""
        with pytest.raises(ConfigValidationError, match="allow_registration"):
            normalize_auth_module_options({"allow_registration": False})

    def test_legacy_social_providers_raises(self) -> None:
        """social_providers raises ConfigValidationError instead of silent drop."""
        with pytest.raises(ConfigValidationError, match="social_providers"):
            normalize_auth_module_options({"social_providers": ["google"]})

    def test_canonical_keys_pass_through(self) -> None:
        """Canonical keys pass through without error."""
        result = normalize_auth_module_options(
            {"registration_enabled": True, "email_verification": "none"}
        )
        assert result[AUTH_REGISTRATION_ENABLED_OPTION] is True


# ---------------------------------------------------------------------------
# normalize_backups_module_options
# ---------------------------------------------------------------------------


class TestNormalizeBackups:
    def test_none_options_returns_empty(self) -> None:
        assert normalize_backups_module_options(None) == {}

    def test_legacy_access_key_converted_to_env_var(self) -> None:
        result = normalize_backups_module_options(
            {"remote_access_key_id": "AKIAIOSF000000000000"}
        )
        assert (
            result[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
            == DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )

    def test_legacy_secret_key_converted_to_env_var(self) -> None:
        result = normalize_backups_module_options(
            {"remote_secret_access_key": "supersecret"}
        )
        assert (
            result[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
            == DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )

    def test_existing_env_var_not_overwritten_by_legacy(self) -> None:
        result = normalize_backups_module_options(
            {
                "remote_access_key_id": "AKIAIOSF000000000000",
                BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "MY_CUSTOM_VAR",
            }
        )
        assert result[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION] == "MY_CUSTOM_VAR"

    def test_legacy_keys_removed_from_output(self) -> None:
        result = normalize_backups_module_options(
            {
                "remote_access_key_id": "key",
                "remote_secret_access_key": "secret",
            }
        )
        assert "remote_access_key_id" not in result
        assert "remote_secret_access_key" not in result


# ---------------------------------------------------------------------------
# normalize_billing_module_options
# ---------------------------------------------------------------------------


class TestNormalizeBilling:
    def test_none_options_returns_empty(self) -> None:
        assert normalize_billing_module_options(None) == {}

    def test_env_var_options_stripped(self) -> None:
        result = normalize_billing_module_options(
            {"publishable_key_env_var": "  MY_KEY  "}
        )
        assert result["publishable_key_env_var"] == "MY_KEY"

    def test_billing_currency_lowered_and_stripped(self) -> None:
        result = normalize_billing_module_options({"billing_currency": "  USD "})
        assert result["billing_currency"] == "usd"


# ---------------------------------------------------------------------------
# normalize_crm_module_options
# ---------------------------------------------------------------------------


class TestNormalizeCrm:
    def test_none_options_returns_empty(self) -> None:
        assert normalize_crm_module_options(None) == {}

    def test_legacy_pipeline_stages_raises(self) -> None:
        """default_pipeline_stages raises ConfigValidationError instead of silent drop."""
        with pytest.raises(ConfigValidationError, match="default_pipeline_stages"):
            normalize_crm_module_options({"default_pipeline_stages": ["new", "won"]})

    def test_other_keys_preserved(self) -> None:
        result = normalize_crm_module_options({"deals_per_page": 50})
        assert result["deals_per_page"] == 50


# ---------------------------------------------------------------------------
# normalize_notifications_module_options
# ---------------------------------------------------------------------------


class TestNormalizeNotifications:
    def test_none_options_returns_empty_with_reply_to(self) -> None:
        result = normalize_notifications_module_options(None)
        assert result.get("reply_to_email") == ""

    def test_legacy_resend_api_key_raises(self) -> None:
        """Legacy resend_api_key raises ConfigValidationError instead of silent conversion."""
        with pytest.raises(ConfigValidationError, match="resend_api_key"):
            normalize_notifications_module_options({"resend_api_key": "re_secret_123"})

    def test_legacy_webhook_secret_raises(self) -> None:
        """Legacy webhook_secret raises ConfigValidationError instead of silent conversion."""
        with pytest.raises(ConfigValidationError, match="webhook_secret"):
            normalize_notifications_module_options({"webhook_secret": "whsec_123"})

    def test_reply_to_email_none_becomes_empty(self) -> None:
        result = normalize_notifications_module_options({"reply_to_email": None})
        assert result["reply_to_email"] == ""

    def test_canonical_keys_pass_through(self) -> None:
        """Canonical notifications keys pass through without error."""
        result = normalize_notifications_module_options(
            {NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: "MY_VAR"}
        )
        assert result[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION] == "MY_VAR"


# ---------------------------------------------------------------------------
# normalize_social_module_options
# ---------------------------------------------------------------------------


class TestNormalizeSocial:
    def test_none_options_returns_empty(self) -> None:
        assert normalize_social_module_options(None) == {}

    def test_provider_allowlist_normalized(self) -> None:
        result = normalize_social_module_options(
            {"provider_allowlist": ["Facebook", "twitter"]}
        )
        assert "facebook" in result["provider_allowlist"]
        assert "x" in result["provider_allowlist"]

    def test_layout_variant_lowered(self) -> None:
        result = normalize_social_module_options({"layout_variant": "  Grid "})
        assert result["layout_variant"] == "grid"

    def test_provider_allowlist_from_string(self) -> None:
        result = normalize_social_module_options(
            {"provider_allowlist": "facebook,instagram"}
        )
        assert "facebook" in result["provider_allowlist"]
        assert "instagram" in result["provider_allowlist"]

    def test_provider_allowlist_deduplication(self) -> None:
        result = normalize_social_module_options(
            {"provider_allowlist": ["facebook", "fb"]}
        )
        assert result["provider_allowlist"].count("facebook") == 1


# ---------------------------------------------------------------------------
# validate_analytics_env_var_reference
# ---------------------------------------------------------------------------


class TestValidateAnalyticsEnvVar:
    def test_empty_returns_none(self) -> None:
        assert validate_analytics_env_var_reference("key", "") is None

    def test_valid_name_returns_none(self) -> None:
        assert validate_analytics_env_var_reference("key", "MY_VAR") is None

    def test_invalid_name_returns_issue(self) -> None:
        result = validate_analytics_env_var_reference("key", "bad-name")
        assert result is not None
        assert "modules.analytics.key" in result


# ---------------------------------------------------------------------------
# validate_analytics_module_options
# ---------------------------------------------------------------------------


class TestValidateAnalyticsOptions:
    def test_none_returns_no_issues(self) -> None:
        assert validate_analytics_module_options(None) == []

    def test_valid_provider_no_issues(self) -> None:
        issues = validate_analytics_module_options(
            {"provider": list(ANALYTICS_PROVIDERS)[0]}
        )
        assert issues == []

    def test_invalid_provider_reported(self) -> None:
        issues = validate_analytics_module_options({"provider": "invalid_provider"})
        assert len(issues) == 1
        assert "provider" in issues[0]

    def test_invalid_env_var_reported(self) -> None:
        issues = validate_analytics_module_options(
            {"posthog_api_key_env_var": "bad-name"}
        )
        assert len(issues) == 1


# ---------------------------------------------------------------------------
# validate_auth_module_options (stub)
# ---------------------------------------------------------------------------


class TestValidateAuth:
    def test_returns_empty(self) -> None:
        assert validate_auth_module_options(None) == []
        assert validate_auth_module_options({"any": "value"}) == []


# ---------------------------------------------------------------------------
# validate_backups_env_var_reference
# ---------------------------------------------------------------------------


class TestValidateBackupsEnvVar:
    def test_empty_returns_none(self) -> None:
        assert validate_backups_env_var_reference("key", "") is None

    def test_valid_name_returns_none(self) -> None:
        assert validate_backups_env_var_reference("key", "MY_VAR") is None

    def test_invalid_name_returns_issue(self) -> None:
        result = validate_backups_env_var_reference("key", "bad-name")
        assert result is not None

    def test_literal_aws_key_rejected(self) -> None:
        result = validate_backups_env_var_reference(
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION, "AKIAIOSF000000000000"
        )
        assert result is not None
        assert "literal AWS" in result


# ---------------------------------------------------------------------------
# validate_billing_currency
# ---------------------------------------------------------------------------


class TestValidateBillingCurrency:
    def test_valid_currency(self) -> None:
        assert validate_billing_currency(list(BILLING_SUPPORTED_CURRENCIES)[0]) is None

    def test_blank_currency_rejected(self) -> None:
        result = validate_billing_currency("")
        assert result is not None
        assert "blank" in result

    def test_unsupported_currency_rejected(self) -> None:
        result = validate_billing_currency("XYZ")
        assert result is not None
        assert "supported" in result


# ---------------------------------------------------------------------------
# validate_billing_env_var_reference
# ---------------------------------------------------------------------------


class TestValidateBillingEnvVar:
    def test_empty_returns_none(self) -> None:
        assert validate_billing_env_var_reference("key", "") is None

    def test_valid_name_returns_none(self) -> None:
        assert validate_billing_env_var_reference("key", "MY_VAR") is None

    def test_invalid_name_returns_issue(self) -> None:
        result = validate_billing_env_var_reference("key", "123bad")
        assert result is not None


# ---------------------------------------------------------------------------
# validate_billing_module_options (stub)
# ---------------------------------------------------------------------------


class TestValidateBillingStub:
    def test_returns_empty(self) -> None:
        assert validate_billing_module_options(None) == []


# ---------------------------------------------------------------------------
# validate_notifications_env_var_reference
# ---------------------------------------------------------------------------


class TestValidateNotificationsEnvVar:
    def test_empty_returns_none(self) -> None:
        assert validate_notifications_env_var_reference("key", "") is None

    def test_valid_name_returns_none(self) -> None:
        assert validate_notifications_env_var_reference("key", "MY_VAR") is None

    def test_invalid_name_returns_issue(self) -> None:
        result = validate_notifications_env_var_reference("key", "bad!")
        assert result is not None


# ---------------------------------------------------------------------------
# validate_notifications_module_options (stub)
# ---------------------------------------------------------------------------


class TestValidateNotificationsStub:
    def test_returns_empty(self) -> None:
        assert validate_notifications_module_options(None) == []


# ---------------------------------------------------------------------------
# validate_social_module_options (stub)
# ---------------------------------------------------------------------------


class TestValidateSocialStub:
    def test_returns_empty(self) -> None:
        assert validate_social_module_options(None) == []


# ---------------------------------------------------------------------------
# has_legacy_backups_secret_values
# ---------------------------------------------------------------------------


class TestHasLegacyBackupsSecrets:
    def test_none_returns_false(self) -> None:
        assert has_legacy_backups_secret_values(None) is False

    def test_empty_returns_false(self) -> None:
        assert has_legacy_backups_secret_values({}) is False

    def test_legacy_key_detected(self) -> None:
        assert (
            has_legacy_backups_secret_values({"remote_access_key_id": "AKIA..."})
            is True
        )

    def test_blank_legacy_key_not_detected(self) -> None:
        assert has_legacy_backups_secret_values({"remote_access_key_id": "  "}) is False


# ---------------------------------------------------------------------------
# format_auth_desired_config_contract
# ---------------------------------------------------------------------------


class TestFormatAuthContract:
    def test_returns_nonempty_string(self) -> None:
        text = format_auth_desired_config_contract()
        assert "registration_enabled" in text
        assert "authentication_method" in text


# ---------------------------------------------------------------------------
# get_env_var_portability
# ---------------------------------------------------------------------------


class TestGetEnvVarPortability:
    def test_blank_name_ignored(self) -> None:
        cat, _ = get_env_var_portability("")
        assert cat == ENV_VAR_PORTABILITY_IGNORED

    def test_portable_variable(self) -> None:
        cat, _ = get_env_var_portability("QUICKSCALE_BILLING_ENABLED")
        assert cat == ENV_VAR_PORTABILITY_PORTABLE

    def test_manual_variable(self) -> None:
        cat, _ = get_env_var_portability("DATABASE_URL")
        assert cat == ENV_VAR_PORTABILITY_MANUAL

    def test_restore_gate_is_manual(self) -> None:
        cat, _ = get_env_var_portability("QUICKSCALE_BACKUPS_ALLOW_RESTORE")
        assert cat == ENV_VAR_PORTABILITY_MANUAL
        assert "destructive" in _


# ---------------------------------------------------------------------------
# sanitize_module_options dispatcher
# ---------------------------------------------------------------------------


class TestSanitizeDispatcher:
    def test_analytics_dispatch(self) -> None:
        result = sanitize_module_options("analytics", {"provider": "  PostHog "})
        assert result["provider"] == "posthog"

    def test_auth_dispatch_with_legacy_raises(self) -> None:
        """Legacy auth keys raise through sanitize dispatcher."""
        with pytest.raises(ConfigValidationError, match="allow_registration"):
            sanitize_module_options("auth", {"allow_registration": True})

    def test_auth_dispatch_with_canonical(self) -> None:
        """Canonical auth keys pass through sanitize dispatcher."""
        result = sanitize_module_options("auth", {"registration_enabled": True})
        assert result[AUTH_REGISTRATION_ENABLED_OPTION] is True

    def test_backups_dispatch(self) -> None:
        result = sanitize_module_options("backups", {"remote_access_key_id": "key123"})
        assert BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION in result

    def test_billing_dispatch(self) -> None:
        result = sanitize_module_options("billing", {"billing_currency": " USD "})
        assert result["billing_currency"] == "usd"

    def test_crm_dispatch_with_legacy_raises(self) -> None:
        """Legacy CRM keys raise through sanitize dispatcher."""
        with pytest.raises(ConfigValidationError, match="default_pipeline_stages"):
            sanitize_module_options("crm", {"default_pipeline_stages": ["a"]})

    def test_crm_dispatch_with_canonical(self) -> None:
        """Canonical CRM keys pass through sanitize dispatcher."""
        result = sanitize_module_options("crm", {"deals_per_page": 50})
        assert result["deals_per_page"] == 50

    def test_notifications_dispatch_with_legacy_raises(self) -> None:
        """Legacy notifications keys raise through sanitize dispatcher."""
        with pytest.raises(ConfigValidationError, match="resend_api_key"):
            sanitize_module_options("notifications", {"resend_api_key": "re_123"})

    def test_notifications_dispatch_with_canonical(self) -> None:
        """Canonical notifications keys pass through sanitize dispatcher."""
        result = sanitize_module_options(
            "notifications", {NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: "MY_VAR"}
        )
        assert result[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION] == "MY_VAR"

    def test_social_dispatch(self) -> None:
        result = sanitize_module_options("social", {"provider_allowlist": ["Facebook"]})
        assert "facebook" in result["provider_allowlist"]

    def test_unknown_module_passthrough(self) -> None:
        result = sanitize_module_options("unknown_module", {"key": "value"})
        assert result == {"key": "value"}

    def test_none_options_returns_empty(self) -> None:
        result = sanitize_module_options("analytics", None)
        assert result == {}
