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

import inspect

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
# Legacy builder independence
# ---------------------------------------------------------------------------


class TestLegacyBuilderIndependence:
    """Verify the legacy builder is not affected by the new entry point."""

    def test_legacy_builder_importable(self) -> None:
        """build_module_wiring_specs can still be imported from its original location."""
        from quickscale_cli.commands.module_wiring_specs import (
            build_module_wiring_specs,
        )

        assert callable(build_module_wiring_specs)

    def test_legacy_builder_does_not_reference_manifest_registry(self) -> None:
        """The legacy builder has no reference to MANIFEST_ADAPTER_REGISTRY."""
        from quickscale_cli.commands.module_wiring_specs import (
            build_module_wiring_specs,
        )

        source = inspect.getsource(build_module_wiring_specs)
        assert "MANIFEST_ADAPTER_REGISTRY" not in source

    def test_legacy_builder_does_not_call_manifest_entry_point(self) -> None:
        """The legacy builder does not call build_manifest_wiring_spec."""
        from quickscale_cli.commands.module_wiring_specs import (
            build_module_wiring_specs,
        )

        source = inspect.getsource(build_module_wiring_specs)
        assert "build_manifest_wiring_spec" not in source
