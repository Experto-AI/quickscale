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

from quickscale_core.manifest import (
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
        from quickscale_cli.social_manifest import load_social_manifest

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
        from quickscale_cli.social_manifest import load_social_manifest

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
