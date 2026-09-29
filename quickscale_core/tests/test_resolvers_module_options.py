"""Tests for the shared manifest resolution surface and its module consumers.

SA217 removed the per-module ``resolve_*``/``default_*``/``validate_*`` option
functions.  These tests pin the same behavior through the one generic resolver
(``resolve_manifest_module_options``), the option-validation engine, and the
module-owned code that remains (the notifications adapter's runtime backend
predicates).  Manifest I/O is mocked where the test exercises the resolver
seam; the module behavior tests load the shipped manifests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.contracts.module_discovery import ImproperlyConfigured
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)
from quickscale_core.manifest.option_validation import validate_module_options
from quickscale_core.manifest.schema import ModuleManifest
from quickscale_modules_notifications.adapter import (
    NOTIFICATIONS_CONSOLE_EMAIL_BACKEND,
    NOTIFICATIONS_LIVE_EMAIL_BACKEND,
    get_manifest_adapter as get_notifications_adapter,
    notifications_live_delivery_configured,
    notifications_production_targeted,
    notifications_runtime_email_backend,
)
from quickscale_modules_social.adapter import get_manifest_adapter


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

    def test_improperly_configured_base_path_propagates(self) -> None:
        """An unresolvable modules base path fails hard, never defaults."""
        with patch(
            "quickscale_core.contracts.resolvers.resolve_manifest_base_path",
            side_effect=ImproperlyConfigured("no base path"),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_manifest_module_options("notifications", {})

    def test_resolution_from_bundled_manifest_base(self) -> None:
        """The bundled snapshots resolve the same declared options."""
        import quickscale_core

        bundled = Path(quickscale_core.__file__).parent / "data" / "manifests"
        with patch(
            "quickscale_core.contracts.resolvers.resolve_manifest_base_path",
            return_value=bundled,
        ):
            resolved = resolve_manifest_module_options("notifications", {})
        assert resolved["sender_name"] == "QuickScale"
        assert resolved["allowed_tags"] == [
            "quickscale",
            "transactional",
            "notifications",
            "auth",
            "forms",
            "ops",
            "testing",
        ]


# ===================================================================
# Notifications
# ===================================================================


class TestNotificationsManifest:
    """Notifications options resolve and validate from its manifest."""

    def test_defaults(self) -> None:
        resolved = resolve_manifest_module_options("notifications", {})
        assert resolved["enabled"] is True
        assert resolved["sender_name"] == "QuickScale"
        assert resolved["sender_email"] == "noreply@example.com"
        assert resolved["reply_to_email"] == ""
        assert resolved["resend_domain"] == ""
        assert resolved["resend_api_key_env_var"] == "RESEND_API_KEY"
        assert resolved["webhook_secret_env_var"] == (
            "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET"
        )
        assert resolved["default_tags"] == ["quickscale", "transactional"]
        assert resolved["webhook_ttl_seconds"] == 300

    def test_tag_lists_normalize_like_the_retired_helper(self) -> None:
        resolved = resolve_manifest_module_options(
            "notifications", {"default_tags": [" Quickscale ", "_ops", "ops"]}
        )
        assert resolved["default_tags"] == ["quickscale", "ops"]

    def test_tag_normalization_truncates_at_fifty(self) -> None:
        resolved = resolve_manifest_module_options(
            "notifications", {"allowed_tags": ["a" * 60]}
        )
        assert resolved["allowed_tags"] == ["a" * 50]

    def test_validation_uses_the_engine(self) -> None:
        manifest = load_module_manifest_with_fallback("notifications")
        assert validate_module_options(manifest, {}) == []

    def test_placeholder_sender_is_refused_when_production_targeted(self) -> None:
        manifest = load_module_manifest_with_fallback("notifications")
        issues = validate_module_options(manifest, {"resend_domain": "mg.example.com"})
        assert any("sender_email" in issue for issue in issues)
        assert any("noreply@example.com" in issue for issue in issues)

    def test_console_safe_placeholder_sender_is_allowed(self) -> None:
        manifest = load_module_manifest_with_fallback("notifications")
        assert validate_module_options(manifest, {}) == []


class TestNotificationsAdapterPredicates:
    """The runtime backend predicates are module adapter code."""

    def test_production_targeted_true_with_resend_domain(self) -> None:
        assert notifications_production_targeted({"resend_domain": "mg.example.com"})

    def test_production_targeted_false_without_domain(self) -> None:
        assert not notifications_production_targeted({})

    def test_production_targeted_false_when_disabled(self) -> None:
        assert not notifications_production_targeted(
            {"enabled": False, "resend_domain": "mg.example.com"}
        )

    def test_live_delivery_configured_with_complete_config(self) -> None:
        assert notifications_live_delivery_configured(
            {
                "sender_name": "Ops",
                "sender_email": "ops@example.com",
                "resend_domain": "mg.example.com",
                "resend_api_key_env_var": "OPS_RESEND_API_KEY",
            }
        )

    def test_live_delivery_not_configured_with_placeholder_sender(self) -> None:
        assert not notifications_live_delivery_configured(
            {"resend_domain": "mg.example.com"}
        )

    def test_live_delivery_not_configured_with_invalid_env_var_name(self) -> None:
        assert not notifications_live_delivery_configured(
            {
                "sender_email": "ops@example.com",
                "resend_domain": "mg.example.com",
                "resend_api_key_env_var": "not a name",
            }
        )

    def test_runtime_backend_is_live_when_configured(self) -> None:
        assert (
            notifications_runtime_email_backend(
                {
                    "sender_name": "Ops",
                    "sender_email": "ops@example.com",
                    "resend_domain": "mg.example.com",
                    "resend_api_key_env_var": "OPS_RESEND_API_KEY",
                }
            )
            == NOTIFICATIONS_LIVE_EMAIL_BACKEND
        )

    def test_runtime_backend_is_console_safe_by_default(self) -> None:
        assert (
            notifications_runtime_email_backend({})
            == NOTIFICATIONS_CONSOLE_EMAIL_BACKEND
        )

    def test_runtime_backend_is_none_when_disabled(self) -> None:
        assert notifications_runtime_email_backend({"enabled": False}) is None

    def test_null_reply_to_email_wires_blank(self) -> None:
        """A null state value wires a blank setting, never the string "None"."""
        spec = get_notifications_adapter()({"reply_to_email": None})
        assert spec.settings["QUICKSCALE_NOTIFICATIONS_REPLY_TO_EMAIL"] == ""


# ===================================================================
# Social
# ===================================================================


class TestSocialManifest:
    """Social options resolve and validate from its manifest."""

    def test_defaults(self) -> None:
        resolved = resolve_manifest_module_options("social", {})
        assert resolved["link_tree_enabled"] is True
        assert resolved["embeds_enabled"] is True
        assert resolved["layout_variant"] == "list"
        assert resolved["provider_allowlist"] == [
            "facebook",
            "instagram",
            "linkedin",
            "tiktok",
            "x",
            "youtube",
        ]
        # resolve reapplies defaults
        assert resolved["cache_ttl_seconds"] == 300

    def test_provider_alias_normalization_and_dedupe(self) -> None:
        resolved = resolve_manifest_module_options(
            "social", {"provider_allowlist": ["YouTube", "twitter", "x-twitter", "fb"]}
        )
        assert resolved["provider_allowlist"] == ["youtube", "x", "facebook"]

    def test_layout_variant_is_stripped_and_lowered(self) -> None:
        resolved = resolve_manifest_module_options(
            "social", {"layout_variant": "  GRID "}
        )
        assert resolved["layout_variant"] == "grid"

    def test_disabled_surfaces_are_refused(self) -> None:
        manifest = load_module_manifest_with_fallback("social")
        issues = validate_module_options(
            manifest, {"link_tree_enabled": False, "embeds_enabled": False}
        )
        assert any("is required" in issue for issue in issues)

    def test_invalid_layout_names_the_setting(self) -> None:
        manifest = load_module_manifest_with_fallback("social")
        issues = validate_module_options(manifest, {"layout_variant": "mosaic"})
        assert any("QUICKSCALE_SOCIAL_LAYOUT_VARIANT" in issue for issue in issues)

    def test_unknown_provider_is_refused(self) -> None:
        manifest = load_module_manifest_with_fallback("social")
        issues = validate_module_options(manifest, {"provider_allowlist": ["myspace"]})
        assert any("unsupported values: myspace" in issue for issue in issues)

    def test_embeds_need_an_embed_capable_provider(self) -> None:
        manifest = load_module_manifest_with_fallback("social")
        issues = validate_module_options(
            manifest, {"provider_allowlist": ["facebook", "instagram", "linkedin"]}
        )
        assert any("tiktok" in issue and "youtube" in issue for issue in issues)

    def test_positive_configuration_passes(self) -> None:
        manifest = load_module_manifest_with_fallback("social")
        assert (
            validate_module_options(
                manifest,
                {
                    "link_tree_enabled": False,
                    "embeds_enabled": True,
                    "provider_allowlist": ["youtube"],
                },
            )
            == []
        )

    def test_embeds_disabled_relaxes_the_embed_provider_rule(self) -> None:
        manifest = load_module_manifest_with_fallback("social")
        assert (
            validate_module_options(
                manifest,
                {"embeds_enabled": False, "provider_allowlist": ["facebook"]},
            )
            == []
        )

    def test_adapter_spec_comes_from_the_manifest(self) -> None:
        spec = get_manifest_adapter()({}, project_package="myapp")
        assert spec.apps == ("quickscale_modules_social",)
        assert spec.settings["QUICKSCALE_SOCIAL_LAYOUT_VARIANT"] == "list"
        assert spec.settings["QUICKSCALE_SOCIAL_LINK_TREE_ENABLED"] is True
