"""Tests for quickscale_core.contracts.module_options.

Covers the sanitize dispatcher and the DR env-var portability helpers that form
the central module-options contract surface.  SA217 removed the per-module
normalizers and validators: the manifest's declared rules own canonicalization
and validation, and the dispatcher applies them.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quickscale_core.contracts.module_options import (
    ENV_VAR_PORTABILITY_IGNORED,
    ENV_VAR_PORTABILITY_MANUAL,
    ENV_VAR_PORTABILITY_PORTABLE,
    NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION,
    get_env_var_portability,
    sanitize_module_options,
)
from quickscale_core.schema.config_schema import ConfigValidationError
from quickscale_core.manifest.loader import ManifestError


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
    def test_analytics_dispatch_passes_declared_keys_through(self) -> None:
        result = sanitize_module_options("analytics", {"provider": "posthog"})
        assert result["provider"] == "posthog"

    def test_auth_dispatch_with_legacy_raises(self) -> None:
        """Legacy auth keys raise through sanitize dispatcher."""
        with pytest.raises(ConfigValidationError, match="allow_registration"):
            sanitize_module_options("auth", {"allow_registration": True})

    def test_auth_dispatch_with_legacy_social_providers_raises(self) -> None:
        """The manifest's retired_options declaration covers social_providers."""
        with pytest.raises(ConfigValidationError, match="social_providers"):
            sanitize_module_options("auth", {"social_providers": ["google"]})

    def test_auth_dispatch_with_canonical(self) -> None:
        """Canonical auth keys pass through sanitize dispatcher."""
        result = sanitize_module_options("auth", {"registration_enabled": True})
        assert result["registration_enabled"] is True

    def test_backups_dispatch_with_retired_raises(self) -> None:
        """The manifest's retired_options declaration raises through sanitize."""
        with pytest.raises(ConfigValidationError, match="remote_access_key_id"):
            sanitize_module_options("backups", {"remote_access_key_id": "key123"})

    def test_backups_dispatch_canonicalizes_declared_keys(self) -> None:
        result = sanitize_module_options(
            "backups", {"naming_prefix": "  db  ", "retention_days": 7}
        )
        assert result["naming_prefix"] == "db"
        assert result["retention_days"] == 7

    def test_billing_dispatch_passes_declared_keys_through(self) -> None:
        result = sanitize_module_options("billing", {"billing_currency": "usd"})
        assert result["billing_currency"] == "usd"

    def test_crm_dispatch_with_retired_raises(self) -> None:
        """The manifest's retired_options declaration raises through sanitize."""
        with pytest.raises(ConfigValidationError, match="default_pipeline_stages"):
            sanitize_module_options("crm", {"default_pipeline_stages": ["a"]})

    def test_crm_dispatch_with_canonical(self) -> None:
        """Canonical CRM keys pass through sanitize dispatcher."""
        result = sanitize_module_options("crm", {"deals_per_page": 50})
        assert result["deals_per_page"] == 50

    def test_notifications_dispatch_with_legacy_raises(self) -> None:
        """The manifest's retired_options declaration raises through sanitize."""
        with pytest.raises(ConfigValidationError, match="resend_api_key"):
            sanitize_module_options("notifications", {"resend_api_key": "re_123"})

    def test_notifications_dispatch_with_legacy_webhook_secret_raises(self) -> None:
        """The webhook_secret retired key raises with its replacement named."""
        with pytest.raises(ConfigValidationError, match="webhook_secret"):
            sanitize_module_options("notifications", {"webhook_secret": "whsec_123"})

    def test_notifications_dispatch_with_canonical(self) -> None:
        """Canonical notifications keys pass through sanitize dispatcher."""
        result = sanitize_module_options(
            "notifications", {NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION: "MY_VAR"}
        )
        assert result[NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION] == "MY_VAR"

    def test_notifications_dispatch_canonicalizes_tags(self) -> None:
        """The manifest's list/slug rules canonicalize a comma-separated string."""
        result = sanitize_module_options(
            "notifications", {"allowed_tags": " Ops , _Forms_, ops "}
        )
        assert result["allowed_tags"] == ["ops", "forms"]

    def test_social_dispatch_canonicalizes_provider_aliases(self) -> None:
        result = sanitize_module_options(
            "social", {"provider_allowlist": ["Facebook", "fb", "twitter"]}
        )
        assert result["provider_allowlist"] == ["facebook", "x"]

    def test_social_dispatch_from_comma_string(self) -> None:
        result = sanitize_module_options(
            "social", {"provider_allowlist": "youtube, twitter, youtube"}
        )
        assert result["provider_allowlist"] == ["youtube", "x"]

    def test_social_dispatch_canonicalizes_layout_variant(self) -> None:
        result = sanitize_module_options("social", {"layout_variant": "  GRID "})
        assert result["layout_variant"] == "grid"

    def test_storage_dispatch_with_retired_raises(self) -> None:
        """The manifest's retired_options declaration raises through sanitize."""
        with pytest.raises(ConfigValidationError, match="access_key_id"):
            sanitize_module_options("storage", {"access_key_id": "raw-secret"})

    def test_storage_dispatch_canonicalizes_declared_keys(self) -> None:
        result = sanitize_module_options(
            "storage", {"backend": " S3 ", "bucket_name": "  assets  "}
        )
        assert result["backend"] == "s3"
        assert result["bucket_name"] == "assets"

    def test_unknown_module_passthrough(self) -> None:
        result = sanitize_module_options("unknown_module", {"key": "value"})
        assert result == {"key": "value"}

    def test_shipped_module_with_unreadable_manifest_fails_closed(self) -> None:
        """A shipped module's retirement declaration must load or options fail."""
        with patch(
            "quickscale_core.contracts.resolvers.load_module_manifest_with_fallback",
            side_effect=ManifestError("boom", "crm"),
        ):
            with pytest.raises(ManifestError):
                sanitize_module_options("crm", {"deals_per_page": 50})

    def test_unknown_module_with_unreadable_manifest_passes_through(self) -> None:
        """An undeclared module has no retirement declaration to enforce."""
        with patch(
            "quickscale_core.contracts.resolvers.load_module_manifest_with_fallback",
            side_effect=ManifestError("missing", "unknown_module"),
        ):
            result = sanitize_module_options("unknown_module", {"key": "value"})
        assert result == {"key": "value"}

    def test_module_without_manifest_passes_through(self) -> None:
        """A module with no readable manifest has no retirement declaration to enforce."""
        result = sanitize_module_options("teams", {"key": "value"})
        assert result == {"key": "value"}

    def test_none_options_returns_empty(self) -> None:
        result = sanitize_module_options("analytics", None)
        assert result == {}
