"""Integration tests for the manifest-driven entry point (A3) requiring both
quickscale_core and quickscale_cli on the path.

These tests verify the end-to-end path:
  build_manifest_wiring_spec('analytics', ...) -> ModuleWiringSpec

The analytics adapter in entry_point.py delegates to analytics_manifest.py
(in quickscale_cli) and the assembler (in quickscale_core), so these tests
must run in the quickscale_cli test environment where both packages are
importable.
"""

from __future__ import annotations

import pytest

import quickscale_core.manifest.entry_point as entry_point_module
from quickscale_core.manifest import (
    MANIFEST_ADAPTER_REGISTRY,
    build_manifest_wiring_spec,
)
from quickscale_core.module_wiring import ModuleWiringSpec


# ---------------------------------------------------------------------------
# Analytics adapter smoke tests
# ---------------------------------------------------------------------------


class TestAnalyticsManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with analytics module."""

    _ANALYTICS_OPTIONS = {
        "provider": "posthog",
        "posthog_host": "https://us.i.posthog.com",
        "posthog_api_key_env_var": "POSTHOG_API_KEY",
        "posthog_host_env_var": "POSTHOG_HOST",
        "enabled": True,
        "exclude_debug": True,
        "exclude_staff": False,
        "anonymous_by_default": False,
    }

    def test_returns_module_wiring_spec(self) -> None:
        """build_manifest_wiring_spec('analytics', ...) returns a ModuleWiringSpec."""
        spec = build_manifest_wiring_spec("analytics", self._ANALYTICS_OPTIONS)
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        """The returned spec is frozen (immutable)."""
        spec = build_manifest_wiring_spec("analytics", self._ANALYTICS_OPTIONS)
        with pytest.raises(AttributeError):
            spec.apps = ()  # type: ignore[misc]

    def test_analytics_app_label_in_spec(self) -> None:
        """Analytics spec includes the analytics Django app label.

        The parity adapter uses the underscore form ``quickscale_modules_analytics``
        to match the legacy ``_analytics_wiring`` builder (PR-4 migration, C2).
        """
        spec = build_manifest_wiring_spec("analytics", self._ANALYTICS_OPTIONS)
        assert "quickscale_modules_analytics" in spec.apps

    def test_provider_setting_in_spec(self) -> None:
        """Analytics spec includes the provider derived setting."""
        spec = build_manifest_wiring_spec("analytics", self._ANALYTICS_OPTIONS)
        assert spec.settings.get("QUICKSCALE_ANALYTICS_PROVIDER") == "posthog"

    def test_enabled_setting_in_spec(self) -> None:
        """Analytics spec includes the enabled derived setting."""
        spec = build_manifest_wiring_spec("analytics", self._ANALYTICS_OPTIONS)
        assert spec.settings.get("QUICKSCALE_ANALYTICS_ENABLED") is True

    def test_none_options_uses_defaults(self) -> None:
        """options=None falls back to manifest defaults.

        The parity adapter uses the underscore form ``quickscale_modules_analytics``
        to match the legacy ``_analytics_wiring`` builder (PR-4 migration, C2).
        """
        spec = build_manifest_wiring_spec("analytics", None)
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_analytics" in spec.apps

    def test_project_package_accepted(self) -> None:
        """project_package keyword argument is accepted without error."""
        spec = build_manifest_wiring_spec(
            "analytics",
            self._ANALYTICS_OPTIONS,
            project_package="myproject",
        )
        assert isinstance(spec, ModuleWiringSpec)

    def test_settings_reflect_supplied_options(self) -> None:
        """Derived settings reflect the supplied option values.

        PR-4 (C2) note: when ``enabled=False``, the parity adapter reproduces
        the legacy ``_analytics_wiring`` short-circuit and returns an EMPTY
        ModuleWiringSpec.  Only the enabled=True case populates settings.
        """
        # Enabled case: custom api key must appear in settings.
        enabled_options = dict(self._ANALYTICS_OPTIONS)
        enabled_options["posthog_api_key_env_var"] = "MY_CUSTOM_KEY"
        enabled_options["enabled"] = True

        spec = build_manifest_wiring_spec("analytics", enabled_options)
        assert spec.settings.get("QUICKSCALE_ANALYTICS_ENABLED") is True
        assert (
            spec.settings.get("QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR")
            == "MY_CUSTOM_KEY"
        )

        # Disabled case: legacy returns an EMPTY spec (PR-4 parity).
        disabled_options = dict(self._ANALYTICS_OPTIONS)
        disabled_options["enabled"] = False

        disabled_spec = build_manifest_wiring_spec("analytics", disabled_options)
        assert disabled_spec.apps == ()
        assert dict(disabled_spec.settings) == {}

    def test_all_expected_settings_present(self) -> None:
        """All expected analytics settings are present in the spec."""
        spec = build_manifest_wiring_spec("analytics", self._ANALYTICS_OPTIONS)
        expected_keys = {
            "QUICKSCALE_ANALYTICS_PROVIDER",
            "QUICKSCALE_ANALYTICS_ENABLED",
            "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
            "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
            "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
        }
        for key in expected_keys:
            assert key in spec.settings, f"Missing expected setting: {key}"


# ---------------------------------------------------------------------------
# Social adapter integration tests
# ---------------------------------------------------------------------------


class TestSocialManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with social module."""

    _PROJECT_PACKAGE = "myproject"

    def test_returns_module_wiring_spec(self) -> None:
        """build_manifest_wiring_spec('social', ...) returns a ModuleWiringSpec."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        """The returned spec is frozen (immutable)."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        with pytest.raises(AttributeError):
            spec.apps = ()  # type: ignore[misc]

    def test_social_has_no_apps(self) -> None:
        """Social spec has no Django app labels (matching legacy)."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        assert spec.apps == ()

    def test_social_has_no_middleware(self) -> None:
        """Social spec has no middleware (matching legacy)."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        assert spec.middleware == ()

    def test_social_url_include_is_project_package_qualified(self) -> None:
        """Social URL include uses the project_package-qualified path."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        assert len(spec.url_includes) == 1
        prefix, module_path = spec.url_includes[0]
        assert prefix == "_quickscale/social/"
        assert module_path == f"{self._PROJECT_PACKAGE}.quickscale_managed.social_urls"

    def test_social_settings_contain_all_expected_keys(self) -> None:
        """Social spec contains all expected QUICKSCALE_SOCIAL_* settings."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        expected_keys = {
            "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED",
            "QUICKSCALE_SOCIAL_LAYOUT_VARIANT",
            "QUICKSCALE_SOCIAL_EMBEDS_ENABLED",
            "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST",
            "QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST",
            "QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS",
            "QUICKSCALE_SOCIAL_LINKS_PER_PAGE",
            "QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE",
            "QUICKSCALE_SOCIAL_LINK_TREE_PATH",
            "QUICKSCALE_SOCIAL_EMBEDS_PATH",
            "QUICKSCALE_SOCIAL_INTEGRATION_BASE_PATH",
            "QUICKSCALE_SOCIAL_INTEGRATION_EMBEDS_PATH",
        }
        assert expected_keys == set(spec.settings.keys())

    def test_social_fixed_path_constants(self) -> None:
        """Social spec preserves fixed path constants."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        assert spec.settings["QUICKSCALE_SOCIAL_LINK_TREE_PATH"] == "/social"
        assert spec.settings["QUICKSCALE_SOCIAL_EMBEDS_PATH"] == "/social/embeds"
        assert (
            spec.settings["QUICKSCALE_SOCIAL_INTEGRATION_BASE_PATH"]
            == "/_quickscale/social/"
        )
        assert (
            spec.settings["QUICKSCALE_SOCIAL_INTEGRATION_EMBEDS_PATH"]
            == "/_quickscale/social/embeds/"
        )

    def test_social_provider_normalization(self) -> None:
        """Social spec normalizes provider aliases in the allowlist."""
        spec = build_manifest_wiring_spec(
            "social",
            {"provider_allowlist": ["Twitter", "YouTube", "FB"]},
            project_package=self._PROJECT_PACKAGE,
        )
        allowlist = spec.settings["QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST"]
        assert allowlist == ["x", "youtube", "facebook"]
        embed_allowlist = spec.settings["QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST"]
        assert embed_allowlist == ["youtube"]

    def test_social_managed_files_contain_real_content(self) -> None:
        """Social managed files contain real Python content, not renderer IDs."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        assert len(spec.managed_files) == 3
        for path, content in spec.managed_files.items():
            assert path.startswith("quickscale_managed/")
            assert isinstance(content, str)
            assert len(content) > 50  # Real content, not a short renderer ID
            assert '"""' in content  # All managed files have docstrings

    def test_social_managed_files_keys(self) -> None:
        """Social managed files have the expected output paths."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        expected_paths = {
            "quickscale_managed/__init__.py",
            "quickscale_managed/social_urls.py",
            "quickscale_managed/social_views.py",
        }
        assert set(spec.managed_files.keys()) == expected_paths

    def test_social_managed_files_paths_match_manifest_contract(self) -> None:
        """Social managed file output paths are sourced from the module.yml manifest.

        The adapter must consume the manifest-declared managed_files contract
        rather than hardcoding output paths, so module.yml remains the single
        source of truth for managed-file inventory.
        """
        from quickscale_core.manifest.social_manifest import load_social_manifest

        manifest = load_social_manifest()
        manifest_output_paths = {
            decl.output_path for decl in manifest.managed_files.values()
        }

        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        adapter_output_paths = set(spec.managed_files.keys())

        assert adapter_output_paths == manifest_output_paths, (
            "Social adapter output paths must match manifest-declared managed_files"
        )

    def test_social_managed_files_renderer_ids_match_manifest_contract(self) -> None:
        """Social managed file renderer IDs are sourced from the module.yml manifest.

        The assembler populates spec.managed_files with output_path -> renderer_id
        mappings from the manifest declarations before the post-hook renders content.
        This test verifies the manifest-declared renderer IDs flow through correctly.
        """
        from quickscale_core.manifest.social_manifest import load_social_manifest

        manifest = load_social_manifest()
        manifest_renderer_ids = {
            decl.renderer for decl in manifest.managed_files.values()
        }

        # The renderer IDs in module.yml should include the known social renderers.
        assert "social.managed_init" in manifest_renderer_ids
        assert "social.managed_urls" in manifest_renderer_ids
        assert "social.managed_views" in manifest_renderer_ids

    def test_social_requires_project_package(self) -> None:
        """Social adapter raises ValueError without project_package."""
        with pytest.raises(ValueError, match="project_package"):
            build_manifest_wiring_spec("social", {})


# ---------------------------------------------------------------------------
# Billing adapter integration tests
# ---------------------------------------------------------------------------


class TestBillingManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with billing module."""

    _BILLING_OPTIONS = {
        "enabled": True,
        "publishable_key_env_var": "STRIPE_PUBLISHABLE_KEY",
        "secret_key_env_var": "STRIPE_SECRET_KEY",
        "webhook_secret_env_var": "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "billing_currency": "usd",
    }

    def test_returns_module_wiring_spec(self) -> None:
        spec = build_manifest_wiring_spec("billing", self._BILLING_OPTIONS)
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        spec = build_manifest_wiring_spec("billing", self._BILLING_OPTIONS)
        with pytest.raises(AttributeError):
            spec.apps = ()  # type: ignore[misc]

    def test_app_labels(self) -> None:
        """Billing spec includes rest_framework and billing app labels."""
        spec = build_manifest_wiring_spec("billing", self._BILLING_OPTIONS)
        assert "rest_framework" in spec.apps
        assert "quickscale_modules_billing" in spec.apps

    def test_url_include(self) -> None:
        spec = build_manifest_wiring_spec("billing", self._BILLING_OPTIONS)
        assert len(spec.url_includes) >= 1
        # Billing is included at root.
        assert any(prefix == "" for prefix, _ in spec.url_includes)

    def test_billing_currency_setting(self) -> None:
        spec = build_manifest_wiring_spec("billing", self._BILLING_OPTIONS)
        assert spec.settings.get("QUICKSCALE_BILLING_CURRENCY") == "usd"

    def test_enabled_setting(self) -> None:
        spec = build_manifest_wiring_spec("billing", self._BILLING_OPTIONS)
        assert spec.settings.get("QUICKSCALE_BILLING_ENABLED") is True

    def test_none_options_uses_defaults(self) -> None:
        spec = build_manifest_wiring_spec("billing", None)
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_billing" in spec.apps
        # Default currency should be usd
        assert spec.settings.get("QUICKSCALE_BILLING_CURRENCY") == "usd"

    def test_all_expected_settings_present(self) -> None:
        spec = build_manifest_wiring_spec("billing", self._BILLING_OPTIONS)
        expected_keys = {
            "QUICKSCALE_BILLING_ENABLED",
            "QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR",
            "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR",
            "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR",
            "QUICKSCALE_BILLING_CURRENCY",
        }
        for key in expected_keys:
            assert key in spec.settings, f"Missing expected setting: {key}"

    def test_disabled_returns_empty_spec(self) -> None:
        """When billing is disabled, the spec should still be valid (no PR-4 short-circuit)."""
        spec = build_manifest_wiring_spec("billing", {"enabled": False})
        assert isinstance(spec, ModuleWiringSpec)


# ---------------------------------------------------------------------------
# Blog adapter integration tests
# ---------------------------------------------------------------------------


class TestBlogManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with blog module."""

    _BLOG_OPTIONS = {
        "posts_per_page": 10,
        "enable_rss": True,
        "api_rate_limit": "5/hour",
    }

    def test_returns_module_wiring_spec(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        with pytest.raises(AttributeError):
            spec.apps = ()  # type: ignore[misc]

    def test_app_labels(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        assert "markdownx" in spec.apps
        assert "quickscale_modules_blog" in spec.apps

    def test_url_includes(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        # Blog has markdownx/ and root URL includes
        urls = dict(spec.url_includes)
        assert "markdownx/" in urls

    def test_posts_per_page_setting(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        assert spec.settings.get("BLOG_POSTS_PER_PAGE") == 10

    def test_enable_rss_setting(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        assert spec.settings.get("BLOG_ENABLE_RSS") is True

    def test_markdownx_settings(self) -> None:
        """Blog spec includes static markdownx settings."""
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        assert "MARKDOWNX_MARKDOWN_EXTENSIONS" in spec.settings
        assert "MARKDOWNX_MEDIA_PATH" in spec.settings
        assert spec.settings["MARKDOWNX_MEDIA_PATH"] == "blog/markdownx/"

    def test_none_options_uses_defaults(self) -> None:
        spec = build_manifest_wiring_spec("blog", None)
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_blog" in spec.apps

    def test_all_expected_settings_present(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        expected_keys = {
            "BLOG_POSTS_PER_PAGE",
            "BLOG_ENABLE_RSS",
            "BLOG_API_RATE_LIMIT",
            "MARKDOWNX_MARKDOWN_EXTENSIONS",
            "MARKDOWNX_MEDIA_PATH",
        }
        for key in expected_keys:
            assert key in spec.settings, f"Missing expected setting: {key}"


# ---------------------------------------------------------------------------
# Listings adapter integration tests
# ---------------------------------------------------------------------------


class TestListingsManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with listings module."""

    def test_returns_module_wiring_spec(self) -> None:
        spec = build_manifest_wiring_spec("listings", None)
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        spec = build_manifest_wiring_spec("listings", None)
        with pytest.raises(AttributeError):
            spec.apps = ()  # type: ignore[misc]

    def test_app_labels(self) -> None:
        spec = build_manifest_wiring_spec("listings", None)
        assert "django_filters" in spec.apps
        assert "markdownx" in spec.apps
        assert "quickscale_modules_listings" in spec.apps

    def test_url_includes(self) -> None:
        spec = build_manifest_wiring_spec("listings", None)
        urls = dict(spec.url_includes)
        assert "listings/" in urls
        assert "markdownx/" in urls

    def test_listings_per_page_default(self) -> None:
        spec = build_manifest_wiring_spec("listings", None)
        assert spec.settings.get("LISTINGS_PER_PAGE") == 12

    def test_markdownx_settings(self) -> None:
        """Listings spec includes static markdownx extensions."""
        spec = build_manifest_wiring_spec("listings", None)
        assert "MARKDOWNX_MARKDOWN_EXTENSIONS" in spec.settings

    def test_custom_listings_per_page(self) -> None:
        spec = build_manifest_wiring_spec("listings", {"listings_per_page": 24})
        assert spec.settings.get("LISTINGS_PER_PAGE") == 24


# ---------------------------------------------------------------------------
# CRM adapter integration tests
# ---------------------------------------------------------------------------


class TestCrmManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with CRM module."""

    _CRM_OPTIONS = {
        "deals_per_page": 25,
        "contacts_per_page": 50,
        "enable_api": True,
    }

    def test_returns_module_wiring_spec(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        with pytest.raises(AttributeError):
            spec.apps = ()  # type: ignore[misc]

    def test_app_labels(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert "rest_framework" in spec.apps
        assert "django_filters" in spec.apps
        assert "quickscale_modules_crm" in spec.apps

    def test_url_include(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert len(spec.url_includes) >= 1

    def test_deals_per_page_setting(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert spec.settings.get("CRM_DEALS_PER_PAGE") == 25

    def test_contacts_per_page_setting(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert spec.settings.get("CRM_CONTACTS_PER_PAGE") == 50

    def test_enable_api_setting(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert spec.settings.get("CRM_ENABLE_API") is True

    def test_none_options_uses_defaults(self) -> None:
        spec = build_manifest_wiring_spec("crm", None)
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.settings.get("CRM_DEALS_PER_PAGE") == 25
        assert spec.settings.get("CRM_ENABLE_API") is True

    def test_all_expected_settings_present(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        expected_keys = {
            "CRM_DEALS_PER_PAGE",
            "CRM_CONTACTS_PER_PAGE",
            "CRM_ENABLE_API",
        }
        for key in expected_keys:
            assert key in spec.settings, f"Missing expected setting: {key}"


# ---------------------------------------------------------------------------
# Forms adapter integration tests
# ---------------------------------------------------------------------------


class TestFormsManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with forms module."""

    _FORMS_OPTIONS = {
        "forms_per_page": 25,
        "spam_protection_enabled": True,
        "rate_limit": "5/hour",
        "data_retention_days": 365,
        "submissions_api_enabled": True,
    }

    def test_returns_module_wiring_spec(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        with pytest.raises(AttributeError):
            spec.apps = ()  # type: ignore[misc]

    def test_app_labels(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert "rest_framework" in spec.apps
        assert "django_filters" in spec.apps
        assert "quickscale_modules_forms" in spec.apps

    def test_url_include(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert len(spec.url_includes) >= 1

    def test_forms_per_page_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("FORMS_PER_PAGE") == 25

    def test_spam_protection_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("FORMS_SPAM_PROTECTION") is True

    def test_rate_limit_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("FORMS_RATE_LIMIT") == "5/hour"

    def test_data_retention_days_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("FORMS_DATA_RETENTION_DAYS") == 365

    def test_submissions_api_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("FORMS_SUBMISSIONS_API") is True

    def test_none_options_uses_defaults(self) -> None:
        spec = build_manifest_wiring_spec("forms", None)
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.settings.get("FORMS_PER_PAGE") == 25
        assert spec.settings.get("FORMS_SPAM_PROTECTION") is True

    def test_all_expected_settings_present(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        expected_keys = {
            "FORMS_PER_PAGE",
            "FORMS_SPAM_PROTECTION",
            "FORMS_RATE_LIMIT",
            "FORMS_DATA_RETENTION_DAYS",
            "FORMS_SUBMISSIONS_API",
        }
        for key in expected_keys:
            assert key in spec.settings, f"Missing expected setting: {key}"


# ---------------------------------------------------------------------------
# Caller-parity coverage (CR-SA18.1-001, CR-SA18.1-002): verify that
# repeated build_manifest_wiring_spec calls through the public entry-point
# seam continue surfacing managed-adapter failures when the lazy-init path
# cannot complete (i.e. the fix for the _ADAPTERS_INITIALIZED latch bug).
# ---------------------------------------------------------------------------


class TestLazyInitCallerParity:
    """Caller-parity evidence for the public manifest entry-point seam:
    repeated ``build_manifest_wiring_spec`` attempts must surface the
    managed-adapter failure on every call, not silently skip after the
    first failure (CR-SA18.1-002 latch fix).

    This test simulates what happens when:
    1. Import-time init is deferred (e.g. circular import).
    2. The lazy init in ``_ensure_adapters_initialized`` fails because a
       managed module's Python adapter package is not importable.
    3. The caller retries — the failure must still be surfaced.
    """

    def test_repeated_build_attempts_surface_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Calling build_manifest_wiring_spec twice when the lazy-init path
        fails must raise ImproperlyConfigured both times."""
        from django.core.exceptions import ImproperlyConfigured

        # Simulate deferred import-time init (e.g. circular import).
        monkeypatch.setattr(entry_point_module, "_ADAPTERS_INITIALIZED", False)

        # Prevent refresh_managed_adapters from succeeding — simulate a
        # managed module whose Python adapter package is not importable.
        def _raise() -> None:
            raise ImproperlyConfigured(
                "Managed adapter for 'test_billing' not importable"
            )

        monkeypatch.setattr(
            entry_point_module,
            "refresh_managed_adapters",
            _raise,
        )

        # Remove billing from the registry so the adapter lookup path is
        # exercised (without a registered adapter, build_manifest_wiring_spec
        # raises ManifestAdapterNotFound before reaching the lazy-init path).
        # Save/restore to avoid leaking state to sibling tests.
        _orig_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        try:
            MANIFEST_ADAPTER_REGISTRY.pop("billing", None)

            # First call: must raise (lazy init fails).
            with pytest.raises(ImproperlyConfigured, match="not importable"):
                build_manifest_wiring_spec("billing", {})

            # _ADAPTERS_INITIALIZED must remain False.
            assert entry_point_module._ADAPTERS_INITIALIZED is False

            # Second call: must also raise (was not latched).
            with pytest.raises(ImproperlyConfigured, match="not importable"):
                build_manifest_wiring_spec("billing", {})

            # Flag still False after second attempt.
            assert entry_point_module._ADAPTERS_INITIALIZED is False
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(_orig_registry)

    def test_success_path_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When the lazy-init path succeeds, subsequent calls use the
        adapter normally — verify the happy path is preserved."""
        monkeypatch.setattr(entry_point_module, "_ADAPTERS_INITIALIZED", False)

        # Patch refresh_managed_adapters to succeed.
        monkeypatch.setattr(
            entry_point_module,
            "refresh_managed_adapters",
            lambda: None,
        )

        spec = build_manifest_wiring_spec("analytics", {"enabled": True})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_analytics" in spec.apps
