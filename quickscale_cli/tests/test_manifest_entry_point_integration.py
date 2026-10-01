"""Integration tests for the manifest-driven entry point (A3) requiring both
quickscale_core and quickscale_cli on the path.

These tests verify the end-to-end path:
  build_manifest_wiring_spec('analytics', ...) -> ModuleWiringSpec

The analytics adapter is module-owned and routes through the public core
runtime facade and manifest assembler. These tests run in the quickscale_cli
test environment to exercise the combined core/CLI caller path.
"""

from __future__ import annotations


import pytest

from quickscale_core.contracts.module_discovery import (
    discover_shipped_module_names,
    get_modules_base_path,
)
from quickscale_core.manifest import (
    build_manifest_wiring_spec,
    refresh_managed_adapters,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.module_wiring import ModuleWiringSpec, collect_wiring

# SA44 Phase 1: managed adapters require explicit
# refresh_managed_adapters() before use.
refresh_managed_adapters()


class TestSourceDiscoveredManifestAdapterParity:
    """Source manifests and module-owned adapters define the wiring contract."""

    def test_all_source_modules_build_from_refreshed_adapters(self) -> None:
        """Build a spec for every discovered source manifest, including orgs."""
        module_names = discover_shipped_module_names()
        source_base = get_modules_base_path()
        manifests = {
            module_name: load_manifest_from_path(
                source_base / module_name / "module.yml"
            )
            for module_name in module_names
        }

        assert len(module_names) == 12
        assert "orgs" in module_names
        assert set(manifests) == set(module_names)

        refresh_managed_adapters()
        specs = {
            module_name: build_manifest_wiring_spec(
                module_name, {}, project_package="myproject"
            )
            for module_name in module_names
        }

        assert set(specs) == set(manifests)
        assert all(isinstance(spec, ModuleWiringSpec) for spec in specs.values())
        for module_name, manifest in manifests.items():
            declared_apps = {
                app
                for projection in manifest.wiring_projections
                if projection.get("wiring_field") == "apps"
                for app in (projection.get("expression") or {}).get("value", [])
            }
            assert declared_apps <= set(specs[module_name].apps)

    def test_all_source_modules_wire_without_setting_conflicts(self) -> None:
        """The shipped module set merges without conflicting setting values."""
        module_names = discover_shipped_module_names()
        refresh_managed_adapters()
        specs = {
            module_name: build_manifest_wiring_spec(
                module_name, {}, project_package="myproject"
            )
            for module_name in module_names
        }

        _, _, settings, _ = collect_wiring(specs)

        assert (
            settings["ACCOUNT_ADAPTER"]
            == "quickscale_modules_auth.allauth_adapter.QuickscaleAccountAdapter"
        )
        assert "MARKDOWNX_MARKDOWN_EXTENSIONS" in settings


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

        Analytics keeps its app and URL suppression when disabled while still
        projecting the manifest-owned settings baseline.
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

        # Disabled case: app and URL wiring are suppressed, but manifest-owned
        # settings remain available to generated settings.
        disabled_options = dict(self._ANALYTICS_OPTIONS)
        disabled_options["enabled"] = False

        disabled_spec = build_manifest_wiring_spec("analytics", disabled_options)
        assert disabled_spec.apps == ()
        assert disabled_spec.settings["QUICKSCALE_ANALYTICS_ENABLED"] is False
        assert "QUICKSCALE_ANALYTICS_PROVIDER" in disabled_spec.settings

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

    def test_social_manifest_declared_app_projection(self) -> None:
        """Social spec includes the app projection declared by module.yml."""
        spec = build_manifest_wiring_spec(
            "social", {}, project_package=self._PROJECT_PACKAGE
        )
        # Keep this value aligned with quickscale_modules/social/module.yml.
        assert spec.apps == ("quickscale_modules_social",)

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
            "QUICKSCALE_SOCIAL_ENABLED",
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
        "currency": "usd",
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
        # The manifest declares billing's mount; the URLconf is module-relative
        # (Module Conventions rule 7).
        assert spec.url_includes == (("billing/", "quickscale_modules_billing.urls"),)

    def test_currency_setting(self) -> None:
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
        "rss_enabled": True,
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
        assert spec.settings.get("QUICKSCALE_BLOG_POSTS_PER_PAGE") == 10

    def test_enable_rss_setting(self) -> None:
        spec = build_manifest_wiring_spec("blog", self._BLOG_OPTIONS)
        assert spec.settings.get("QUICKSCALE_BLOG_RSS_ENABLED") is True

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
            "QUICKSCALE_BLOG_POSTS_PER_PAGE",
            "QUICKSCALE_BLOG_RSS_ENABLED",
            "QUICKSCALE_BLOG_API_RATE_LIMIT",
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
        assert spec.settings.get("QUICKSCALE_LISTINGS_PER_PAGE") == 12

    def test_markdownx_settings(self) -> None:
        """Listings spec includes static markdownx extensions."""
        spec = build_manifest_wiring_spec("listings", None)
        assert "MARKDOWNX_MARKDOWN_EXTENSIONS" in spec.settings

    def test_custom_listings_per_page(self) -> None:
        spec = build_manifest_wiring_spec("listings", {"per_page": 24})
        assert spec.settings.get("QUICKSCALE_LISTINGS_PER_PAGE") == 24

    def test_retired_listings_per_page_key_is_refused(self) -> None:
        from quickscale_core.contracts.module_options import sanitize_module_options
        from quickscale_core.schema.config_schema import ConfigValidationError

        with pytest.raises(ConfigValidationError) as excinfo:
            sanitize_module_options("listings", {"listings_per_page": 12})

        assert "listings_per_page" in str(excinfo.value)
        assert "per_page" in str(excinfo.value)


# ---------------------------------------------------------------------------
# CRM adapter integration tests
# ---------------------------------------------------------------------------


class TestCrmManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with CRM module."""

    _CRM_OPTIONS = {
        "deals_per_page": 25,
        "contacts_per_page": 50,
        "api_enabled": True,
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
        assert spec.settings.get("QUICKSCALE_CRM_DEALS_PER_PAGE") == 25

    def test_contacts_per_page_setting(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert spec.settings.get("QUICKSCALE_CRM_CONTACTS_PER_PAGE") == 50

    def test_enable_api_setting(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        assert spec.settings.get("QUICKSCALE_CRM_API_ENABLED") is True

    def test_none_options_uses_defaults(self) -> None:
        spec = build_manifest_wiring_spec("crm", None)
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.settings.get("QUICKSCALE_CRM_DEALS_PER_PAGE") == 25
        assert spec.settings.get("QUICKSCALE_CRM_API_ENABLED") is True

    def test_all_expected_settings_present(self) -> None:
        spec = build_manifest_wiring_spec("crm", self._CRM_OPTIONS)
        expected_keys = {
            "QUICKSCALE_CRM_DEALS_PER_PAGE",
            "QUICKSCALE_CRM_CONTACTS_PER_PAGE",
            "QUICKSCALE_CRM_API_ENABLED",
        }
        for key in expected_keys:
            assert key in spec.settings, f"Missing expected setting: {key}"


# ---------------------------------------------------------------------------
# Forms adapter integration tests
# ---------------------------------------------------------------------------


class TestFormsManifestEntryPoint:
    """End-to-end tests for build_manifest_wiring_spec with forms module."""

    _FORMS_OPTIONS = {
        "submissions_per_page": 25,
        "spam_protection_enabled": True,
        "rate_limit": "5/hour",
        "retention_days": 365,
        "api_enabled": True,
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
        assert spec.settings.get("QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE") == 25

    def test_spam_protection_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED") is True

    def test_rate_limit_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("QUICKSCALE_FORMS_RATE_LIMIT") == "5/hour"

    def test_retention_days_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("QUICKSCALE_FORMS_RETENTION_DAYS") == 365

    def test_submissions_api_setting(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        assert spec.settings.get("QUICKSCALE_FORMS_API_ENABLED") is True

    def test_none_options_uses_defaults(self) -> None:
        spec = build_manifest_wiring_spec("forms", None)
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.settings.get("QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE") == 25
        assert spec.settings.get("QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED") is True

    def test_all_expected_settings_present(self) -> None:
        spec = build_manifest_wiring_spec("forms", self._FORMS_OPTIONS)
        expected_keys = {
            "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE",
            "QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED",
            "QUICKSCALE_FORMS_RATE_LIMIT",
            "QUICKSCALE_FORMS_RETENTION_DAYS",
            "QUICKSCALE_FORMS_API_ENABLED",
        }
        for key in expected_keys:
            assert key in spec.settings, f"Missing expected setting: {key}"


# ---------------------------------------------------------------------------
# SA44 Phase 1: lazy-init caller-parity tests have been removed.
# ``build_manifest_wiring_spec`` no longer calls ``_ensure_adapters_initialized``
# or references ``_ADAPTERS_INITIALIZED``.  Managed adapters must be explicitly
# registered via ``refresh_managed_adapters()`` before use.  The module-level
# call above ensures the active managed adapters are registered for all tests.
# ---------------------------------------------------------------------------


class TestNotificationsProviderOption:
    """The declared provider is constrained to the implemented runtime."""

    def test_unsupported_provider_is_refused(self) -> None:
        from quickscale_core.contracts.resolvers import (
            load_module_manifest_with_fallback,
        )
        from quickscale_core.manifest.option_validation import (
            collect_option_validation_issues,
        )

        issues = collect_option_validation_issues(
            load_module_manifest_with_fallback("notifications"),
            {"provider": "postmark"},
        )
        assert any(issue.option_name == "provider" for issue in issues)


_DISABLED_MODULE_OPTIONS: dict[str, dict[str, object]] = {
    "blog": {
        "enabled": False,
        "posts_per_page": 10,
        "api_rate_limit": "5/hour",
        "rss_enabled": True,
        "api_upload_max_bytes": 10485760,
        "api_upload_max_width": 4096,
        "api_upload_max_height": 4096,
        "api_allowed_image_formats": ["PNG", "JPEG", "WEBP", "GIF"],
    },
    "crm": {
        "enabled": False,
        "api_enabled": True,
        "deals_per_page": 25,
        "contacts_per_page": 50,
    },
    "forms": {
        "enabled": False,
        "submissions_per_page": 25,
        "spam_protection_enabled": True,
        "rate_limit": "5/hour",
        "retention_days": 365,
        "api_enabled": True,
    },
    "listings": {"enabled": False, "per_page": 12},
    "auth": {"enabled": False},
    "backups": {"enabled": False},
    "orgs": {"enabled": False},
    "social": {"enabled": False},
    "storage": {"enabled": False},
}


_DISABLED_EDITOR_INCLUDES: dict[str, tuple[tuple[str, str], ...]] = {
    # Blog and listings keep a staff-guarded copy of the Markdownx endpoints
    # their installed admin editors call; crm and forms have no shared editor,
    # and the five foundation modules keep no URL mount at all while off.
    "blog": (("markdownx/", "quickscale_modules_blog.markdownx_urls"),),
    "crm": (),
    "forms": (),
    "listings": (("markdownx/", "quickscale_modules_listings.markdownx_urls"),),
    "auth": (),
    "backups": (),
    "orgs": (),
    "social": (),
    "storage": (),
}


class TestMarkdownxEditorMountIsAlwaysGuarded:
    """The Markdownx editor mount is staff-guarded in every combination."""

    @pytest.mark.parametrize(
        ("blog_enabled", "listings_enabled"),
        [(True, True), (True, False), (False, True), (False, False)],
    )
    def test_no_unguarded_markdownx_mount(
        self, blog_enabled: bool, listings_enabled: bool
    ) -> None:
        specs = {
            "blog": build_manifest_wiring_spec(
                "blog",
                {**_DISABLED_MODULE_OPTIONS["blog"], "enabled": blog_enabled},
            ),
            "listings": build_manifest_wiring_spec(
                "listings",
                {**_DISABLED_MODULE_OPTIONS["listings"], "enabled": listings_enabled},
            ),
        }
        _, _, _, urls = collect_wiring(specs)
        markdownx_targets = [
            target for prefix, target in urls if prefix == "markdownx/"
        ]
        assert markdownx_targets, "the editor mount must exist while installed"
        assert "markdownx.urls" not in markdownx_targets
        assert all(target.endswith(".markdownx_urls") for target in markdownx_targets)


class TestModuleDisabledSwitch:
    """Rule 1 (D3): off keeps the installed app and its admin, drops the
    module's own public URLs, and keeps only installed-admin editor mounts."""

    @pytest.mark.parametrize("module_name", sorted(_DISABLED_MODULE_OPTIONS))
    def test_disabled_module_keeps_apps_and_drops_public_url_mounts(
        self, module_name: str
    ) -> None:
        extra_kwargs = (
            {"project_package": "testproject"} if module_name == "social" else {}
        )
        spec = build_manifest_wiring_spec(
            module_name, _DISABLED_MODULE_OPTIONS[module_name], **extra_kwargs
        )
        assert spec.settings[f"QUICKSCALE_{module_name.upper()}_ENABLED"] is False
        assert f"quickscale_modules_{module_name}" in spec.apps
        assert spec.url_includes == _DISABLED_EDITOR_INCLUDES[module_name]
        assert (f"{module_name}/", f"quickscale_modules_{module_name}.urls") not in (
            spec.url_includes
        )
        assert spec.pre_home_url_includes == ()
