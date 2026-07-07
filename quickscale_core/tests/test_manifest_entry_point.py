"""Tests for the manifest-driven wiring spec entry point (A3) — core package.

These tests cover the parts of entry_point.py that are testable from within
quickscale_core without a quickscale_cli dependency:
- MANIFEST_ADAPTER_REGISTRY structure and accessibility.
- ManifestAdapterNotFound exception.
- build_manifest_wiring_spec routing for unknown modules.
- Custom adapter registration and unregistration.
- Public exports from quickscale_core.manifest.
- Provenance-sensitive checks for module-owned vs core fallback adapters.
- Managed-adapter import/factory failure at an active base path.

SA44 Phase 1: managed adapters (social, billing, CRM) are NOT registered at
import time.  The module-level ``refresh_managed_adapters()`` call below
registers them explicitly before any test runs.

Integration tests that call build_manifest_wiring_spec('analytics', ...)
live in quickscale_cli/tests/test_manifest_entry_point_integration.py,
where both packages are on sys.path.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from quickscale_core.manifest import (
    MANIFEST_ADAPTER_REGISTRY,
    ManifestAdapterNotFound,
    build_generic_manifest_spec,
    build_manifest_wiring_spec,
    load_module_manifest,
    refresh_managed_adapters,
)
import quickscale_core.manifest.entry_point as entry_point_module
from quickscale_core.manifest.entry_point import (
    MANIFEST_ADAPTER_REGISTRY as REGISTRY_DIRECT,
    MANAGED_ADAPTER_ORIGINS,
    ManifestAdapterNotFound as ManifestAdapterNotFoundDirect,
    build_manifest_wiring_spec as build_manifest_wiring_spec_direct,
)
from quickscale_core.module_wiring import ModuleWiringSpec

# SA44 Phase 1: managed adapters (social, billing, CRM) are NOT registered
# at import time.  ``refresh_managed_adapters()`` must be called explicitly
# before tests that expect managed adapters in the registry.
# This module-level call runs once when the test file is loaded.
refresh_managed_adapters()


# ---------------------------------------------------------------------------
# MANIFEST_ADAPTER_REGISTRY
# ---------------------------------------------------------------------------


class TestManifestAdapterRegistry:
    """Tests for the MANIFEST_ADAPTER_REGISTRY dict."""

    def test_registry_is_dict(self) -> None:
        """MANIFEST_ADAPTER_REGISTRY is a dict."""
        assert isinstance(MANIFEST_ADAPTER_REGISTRY, dict)

    def test_analytics_registered_at_import(self) -> None:
        """Analytics adapter is registered when entry_point module loads."""
        assert "analytics" in MANIFEST_ADAPTER_REGISTRY

    def test_analytics_value_is_callable(self) -> None:
        """The analytics registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["analytics"])

    def test_notifications_registered_at_import(self) -> None:
        """Notifications adapter is registered when entry_point module loads."""
        assert "notifications" in MANIFEST_ADAPTER_REGISTRY

    def test_notifications_value_is_callable(self) -> None:
        """The notifications registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["notifications"])

    def test_auth_registered_at_import(self) -> None:
        """Auth adapter is registered when entry_point module loads."""
        assert "auth" in MANIFEST_ADAPTER_REGISTRY

    def test_auth_value_is_callable(self) -> None:
        """The auth registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["auth"])

    def test_orgs_registered_at_import(self) -> None:
        """Orgs adapter is registered when entry_point module loads."""
        assert "orgs" in MANIFEST_ADAPTER_REGISTRY

    def test_orgs_value_is_callable(self) -> None:
        """The orgs registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["orgs"])

    def test_storage_registered_at_import(self) -> None:
        """Storage adapter is registered when entry_point module loads."""
        assert "storage" in MANIFEST_ADAPTER_REGISTRY

    def test_storage_value_is_callable(self) -> None:
        """The storage registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["storage"])

    def test_social_registered_via_explicit_refresh(self) -> None:
        """Social adapter is registered after explicit refresh_managed_adapters().

        SA44 Phase 1: managed adapters are no longer registered at import time.
        The module-level ``refresh_managed_adapters()`` call in this test file
        ensures social is available.
        """
        assert "social" in MANIFEST_ADAPTER_REGISTRY

    def test_social_value_is_callable(self) -> None:
        """The social registry entry is callable after explicit refresh."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["social"])

    def test_importable_from_manifest_package(self) -> None:
        """MANIFEST_ADAPTER_REGISTRY is importable from quickscale_core.manifest."""
        assert MANIFEST_ADAPTER_REGISTRY is REGISTRY_DIRECT


# ---------------------------------------------------------------------------
# ManifestAdapterNotFound
# ---------------------------------------------------------------------------


class TestManifestAdapterNotFound:
    """Tests for ManifestAdapterNotFound exception."""

    def test_is_key_error_subclass(self) -> None:
        """ManifestAdapterNotFound is a subclass of KeyError."""
        assert issubclass(ManifestAdapterNotFound, KeyError)

    def test_importable_from_manifest_package(self) -> None:
        """ManifestAdapterNotFound is importable from quickscale_core.manifest."""
        assert ManifestAdapterNotFound is ManifestAdapterNotFoundDirect

    def test_can_be_raised(self) -> None:
        """ManifestAdapterNotFound can be raised and caught."""
        with pytest.raises(ManifestAdapterNotFound):
            raise ManifestAdapterNotFound("test module")

    def test_raised_for_unknown_module(self) -> None:
        """build_manifest_wiring_spec raises ManifestAdapterNotFound for unknown modules."""
        with pytest.raises(ManifestAdapterNotFound):
            build_manifest_wiring_spec("no_such_module_xyz", {})

    def test_error_message_contains_module_name(self) -> None:
        """The error message includes the requested module name."""
        with pytest.raises(ManifestAdapterNotFound, match="no_such_module_xyz"):
            build_manifest_wiring_spec("no_such_module_xyz", {})

    def test_error_message_lists_registered_modules(self) -> None:
        """The error message lists the registered module names."""
        with pytest.raises(ManifestAdapterNotFound, match="analytics"):
            build_manifest_wiring_spec("no_such_module_xyz", {})


# ---------------------------------------------------------------------------
# build_manifest_wiring_spec public API
# ---------------------------------------------------------------------------


class TestBuildManifestWiringSpecAPI:
    """Tests for build_manifest_wiring_spec API and routing."""

    def test_importable_from_manifest_package(self) -> None:
        """build_manifest_wiring_spec is importable from quickscale_core.manifest."""
        assert build_manifest_wiring_spec is build_manifest_wiring_spec_direct

    def test_routes_to_registered_custom_adapter(self) -> None:
        """build_manifest_wiring_spec routes to a registered custom adapter."""
        custom_spec = ModuleWiringSpec(apps=("custom.test.app",))
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)

        try:
            MANIFEST_ADAPTER_REGISTRY["_test_custom"] = lambda opts, **kw: custom_spec
            spec = build_manifest_wiring_spec("_test_custom", {})
            assert spec is custom_spec
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)

    def test_none_options_passed_as_empty_dict(self) -> None:
        """options=None is converted to an empty dict before calling the adapter."""
        called_with: list[dict] = []

        def tracking_adapter(opts: dict, **kw: object) -> ModuleWiringSpec:
            called_with.append(opts)
            return ModuleWiringSpec()

        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        try:
            MANIFEST_ADAPTER_REGISTRY["_test_track"] = tracking_adapter
            build_manifest_wiring_spec("_test_track", None)
            assert called_with == [{}]
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)

    def test_project_package_forwarded_to_adapter(self) -> None:
        """project_package keyword is forwarded to the adapter callable."""
        received_kwargs: list[dict] = []

        def tracking_adapter(opts: dict, **kw: object) -> ModuleWiringSpec:
            received_kwargs.append(kw)
            return ModuleWiringSpec()

        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        try:
            MANIFEST_ADAPTER_REGISTRY["_test_pkg"] = tracking_adapter
            build_manifest_wiring_spec("_test_pkg", {}, project_package="myproject")
            assert received_kwargs[0].get("project_package") == "myproject"
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)


# ---------------------------------------------------------------------------
# Custom adapter registration lifecycle
# ---------------------------------------------------------------------------


class TestCustomAdapterRegistration:
    """Tests for adapter registration and lookup lifecycle."""

    def test_custom_adapter_can_be_registered_and_called(self) -> None:
        """A custom adapter can be registered and called."""
        expected = ModuleWiringSpec(apps=("test.app",))
        original = dict(MANIFEST_ADAPTER_REGISTRY)

        try:
            MANIFEST_ADAPTER_REGISTRY["_test_lifecycle"] = lambda o, **k: expected
            result = build_manifest_wiring_spec("_test_lifecycle", {})
            assert result is expected
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original)

    def test_unregistered_after_cleanup(self) -> None:
        """After registry cleanup the custom adapter is not present."""
        assert "_test_lifecycle" not in MANIFEST_ADAPTER_REGISTRY


# ---------------------------------------------------------------------------
# Adapter-path coverage: exercise each registered adapter through
# build_manifest_wiring_spec and verify the returned ModuleWiringSpec.
# ---------------------------------------------------------------------------

# All catalog adapters expected in the registry.  Inline-registered modules
# (analytics, auth, blog, …) are set at module load time.  Managed modules
# (billing, crm, social) are registered by the module-level
# ``refresh_managed_adapters()`` call above (SA44 Phase 1).
_REGISTERED_ADAPTERS = [
    "analytics",
    "auth",
    "backups",
    "billing",
    "blog",
    "crm",
    "forms",
    "listings",
    "notifications",
    "orgs",
    "social",
    "storage",
]

# Adapters that require project_package to build a spec.
_ADAPTERS_REQUIRING_PROJECT_PACKAGE = frozenset({"social"})


class TestRegisteredAdapterPaths:
    """Each registered adapter produces a valid ModuleWiringSpec via the
    public build_manifest_wiring_spec entry point."""

    def test_all_expected_adapters_registered(self) -> None:
        """Every adapter in the expected set is present in the registry."""
        for name in _REGISTERED_ADAPTERS:
            assert name in MANIFEST_ADAPTER_REGISTRY, f"{name} adapter not registered"

    def test_analytics_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("analytics", {"enabled": True})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_analytics" in spec.apps

    def test_analytics_disabled_returns_empty_spec(self) -> None:
        spec = build_manifest_wiring_spec("analytics", {"enabled": False})
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.apps == ()

    def test_billing_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("billing", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_billing" in spec.apps
        assert "rest_framework" in spec.apps

    def test_blog_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("blog", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_blog" in spec.apps
        assert "markdownx" in spec.apps

    def test_listings_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("listings", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_listings" in spec.apps
        assert "django_filters" in spec.apps

    def test_crm_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("crm", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_crm" in spec.apps
        assert "rest_framework" in spec.apps

    def test_forms_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("forms", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_forms" in spec.apps
        assert "rest_framework" in spec.apps

    def test_backups_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("backups", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_backups" in spec.apps

    def test_notifications_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("notifications", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_notifications" in spec.apps

    def test_auth_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("auth", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_auth" in spec.apps
        assert "allauth" in spec.apps

    def test_auth_adapter_username_mode(self) -> None:
        spec = build_manifest_wiring_spec("auth", {"authentication_method": "username"})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_auth" in spec.apps

    def test_orgs_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("orgs", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_orgs" in spec.apps

    def test_orgs_adapter_saas_mode(self) -> None:
        spec = build_manifest_wiring_spec("orgs", {"mode": "saas"})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_orgs" in spec.apps

    def test_storage_adapter_local_backend(self) -> None:
        spec = build_manifest_wiring_spec("storage", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_storage" in spec.apps

    def test_storage_adapter_s3_backend(self) -> None:
        spec = build_manifest_wiring_spec(
            "storage",
            {
                "backend": "s3",
                "bucket_name": "test-bucket",
                "region_name": "us-east-1",
            },
        )
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_storage" in spec.apps

    def test_social_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("social", {}, project_package="myproject")
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.apps == ()
        assert "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED" in spec.settings
        assert len(spec.managed_files) == 3

    def test_social_adapter_requires_project_package(self) -> None:
        """Social adapter raises ValueError without project_package."""
        with pytest.raises(ValueError, match="project_package"):
            build_manifest_wiring_spec("social", {})

    def test_each_adapter_accepts_none_options(self) -> None:
        """Every registered adapter tolerates options=None."""
        for name in _REGISTERED_ADAPTERS:
            if name in _ADAPTERS_REQUIRING_PROJECT_PACKAGE:
                continue
            spec = build_manifest_wiring_spec(name, None)
            assert isinstance(spec, ModuleWiringSpec), (
                f"{name} adapter did not return ModuleWiringSpec with None options"
            )

    def test_each_adapter_accepts_empty_options(self) -> None:
        """Every registered adapter tolerates options={}."""
        for name in _REGISTERED_ADAPTERS:
            if name in _ADAPTERS_REQUIRING_PROJECT_PACKAGE:
                continue
            spec = build_manifest_wiring_spec(name, {})
            assert isinstance(spec, ModuleWiringSpec), (
                f"{name} adapter did not return ModuleWiringSpec with empty options"
            )

    def test_each_adapter_forwards_project_package(self) -> None:
        """project_package kwarg is forwarded without error."""
        for name in _REGISTERED_ADAPTERS:
            spec = build_manifest_wiring_spec(name, {}, project_package="myproject")
            assert isinstance(spec, ModuleWiringSpec), (
                f"{name} adapter failed with project_package kwarg"
            )


# ---------------------------------------------------------------------------
# Provenance-sensitive tests (AF7): verify that module-owned adapters
# are selected in monorepo/embedded contexts and that no core fallback
# adapters remain (fail-hard decision).
# ---------------------------------------------------------------------------


class TestManagedAdapterProvenance:
    """Verify the AF7 fail-hard discovery contract.

    In monorepo / embedded contexts the module-owned adapter (from
    ``quickscale_modules_{name}.adapter``) should be the active
    registry entry.  Core fallback adapters have been deleted — the
    module package must be importable or :func:`refresh_managed_adapters`
    raises ``ImproperlyConfigured``.
    """

    _MANAGED_MODULES = frozenset({"social", "billing", "crm"})

    def test_module_owned_adapters_are_active_in_monorepo(self) -> None:
        """When the module package is importable (monorepo/embedded context),
        the registry entry for each managed module should be the module-owned
        implementation, not the core fallback."""
        for name in self._MANAGED_MODULES:
            assert name in MANIFEST_ADAPTER_REGISTRY, f"{name} not registered"
            fn_file = inspect.getfile(MANIFEST_ADAPTER_REGISTRY[name])
            assert "quickscale_modules" in fn_file, (
                f"{name} adapter should be module-owned in monorepo context, "
                f"but source is {fn_file}"
            )

    def test_module_owned_adapter_source_location(self) -> None:
        """Each managed module's active adapter comes from its own package."""
        expected = {
            "social": "quickscale_modules_social/adapter.py",
            "billing": "quickscale_modules_billing/adapter.py",
            "crm": "quickscale_modules_crm/adapter.py",
        }
        for name, expected_suffix in expected.items():
            fn_file = inspect.getfile(MANIFEST_ADAPTER_REGISTRY[name])
            assert fn_file.endswith(expected_suffix), (
                f"{name} adapter expected to end with {expected_suffix}, got {fn_file}"
            )

    def test_module_owned_adapter_produces_valid_spec(self) -> None:
        """Module-owned adapters produce a valid ModuleWiringSpec via
        the public build_manifest_wiring_spec entry point."""
        for name in self._MANAGED_MODULES:
            if name == "social":
                spec = build_manifest_wiring_spec(
                    "social", {}, project_package="myproject"
                )
            else:
                spec = build_manifest_wiring_spec(name, {})
            assert isinstance(spec, ModuleWiringSpec), (
                f"{name} module-owned adapter did not return ModuleWiringSpec"
            )
            # Verify module-specific keys are present.
            if name == "social":
                assert "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED" in spec.settings
                assert len(spec.managed_files) == 3
            elif name == "billing":
                assert "quickscale_modules_billing" in spec.apps
                assert "QUICKSCALE_BILLING_ENABLED" in spec.settings
            elif name == "crm":
                assert "quickscale_modules_crm" in spec.apps
                assert "CRM_DEALS_PER_PAGE" in spec.settings

    def test_managed_adapter_origins_refect_registered_modules(self) -> None:
        """MANAGED_ADAPTER_ORIGINS contains exactly the managed modules."""
        assert MANAGED_ADAPTER_ORIGINS == self._MANAGED_MODULES, (
            f"Expected MANAGED_ADAPTER_ORIGINS to be {self._MANAGED_MODULES}, "
            f"got {MANAGED_ADAPTER_ORIGINS}"
        )

    def test_custom_entries_preserved_after_refresh(self) -> None:
        """Custom (non-managed) entries survive a call to
        refresh_managed_adapters unchanged."""
        original = dict(MANIFEST_ADAPTER_REGISTRY)
        try:
            MANIFEST_ADAPTER_REGISTRY["_test_custom"] = lambda opts, **kw: (
                ModuleWiringSpec()
            )
            refresh_managed_adapters()
            assert "_test_custom" in MANIFEST_ADAPTER_REGISTRY, (
                "Custom entry was removed after refresh"
            )
            # Managed entries should still be present.
            for name in self._MANAGED_MODULES:
                assert name in MANIFEST_ADAPTER_REGISTRY
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original)

    def test_public_functions_exported(self) -> None:
        """New public functions are exportable from the manifest package."""
        assert callable(build_generic_manifest_spec)
        assert callable(load_module_manifest)
        assert callable(refresh_managed_adapters)
        # backward-compat private aliases still work.
        from quickscale_core.manifest.entry_point import (
            _build_generic_manifest_spec,
            _load_module_manifest,
        )

        assert _build_generic_manifest_spec is build_generic_manifest_spec
        assert _load_module_manifest is load_module_manifest


# ---------------------------------------------------------------------------
# ImproperlyConfigured regression (AF7-CR-REV-002): verify that
# refresh_managed_adapters raises ImproperlyConfigured when a managed
# module has a manifest at the active base path but its Python adapter
# package is not importable.
# ---------------------------------------------------------------------------


class TestRefreshManagedAdaptersFailure:
    """Managed-adapter import/factory failure at an active base path raises
    ImproperlyConfigured (AF7 fail-hard decision)."""

    def test_raises_improperly_configured_when_adapter_not_importable(
        self, tmp_path: Path
    ) -> None:
        """refresh_managed_adapters raises ImproperlyConfigured when a managed
        module has a module.yml at the active base path but its Python adapter
        package cannot be imported."""
        from django.core.exceptions import ImproperlyConfigured

        from quickscale_core.contracts.module_discovery import (
            get_modules_base_path,
            set_modules_base_path,
        )

        # Save and restore the full registry / origins so this test does not
        # leak state to siblings.
        _orig_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        _orig_origins = set(MANAGED_ADAPTER_ORIGINS)

        try:
            # Clear the registry so we start fresh, then register only
            # billing as a managed origin.
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.add("_test_missing_adapter")

            # Set up a temp base path with a module.yml for a module whose
            # Python package does not exist (so import raises ImportError).
            modules_dir = tmp_path / "modules"
            (modules_dir / "_test_missing_adapter").mkdir(parents=True)
            (modules_dir / "_test_missing_adapter" / "module.yml").write_text(
                "version: '1'\nname: _test_missing_adapter\n"
            )

            original_base = get_modules_base_path()
            set_modules_base_path(modules_dir)
            try:
                with pytest.raises(
                    ImproperlyConfigured,
                    match="quickscale_modules__test_missing_adapter",
                ):
                    refresh_managed_adapters()
            finally:
                set_modules_base_path(original_base)
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(_orig_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(_orig_origins)


# ---------------------------------------------------------------------------
# SA18.2: Fail-hard on empty-after-resolution analytics manifest settings.
# An empty result after resolution means the manifest derivation produced
# an invalid result and should raise ManifestError instead of silently
# defaulting to PostHog values.
# ---------------------------------------------------------------------------


class TestAnalyticsPostHookFailHard:
    """Empty-after-resolution analytics manifest settings raise ManifestError
    instead of silently defaulting to PostHog values (SA18.2)."""

    def test_empty_provider_raises_manifest_error(self) -> None:
        """An empty QUICKSCALE_ANALYTICS_PROVIDER raises ManifestError."""
        from quickscale_core.manifest import ManifestError

        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_ANALYTICS_ENABLED": True,
                "QUICKSCALE_ANALYTICS_PROVIDER": "",
                "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": "POSTHOG_API_KEY",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": "POSTHOG_HOST",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST": "https://us.i.posthog.com",
            }
        )
        resolved = {"enabled": True}

        with pytest.raises(ManifestError, match="QUICKSCALE_ANALYTICS_PROVIDER"):
            entry_point_module._analytics_post_hook(spec, resolved)

    def test_empty_host_raises_manifest_error(self) -> None:
        """An empty QUICKSCALE_ANALYTICS_POSTHOG_HOST raises ManifestError."""
        from quickscale_core.manifest import ManifestError

        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_ANALYTICS_ENABLED": True,
                "QUICKSCALE_ANALYTICS_PROVIDER": "posthog",
                "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": "POSTHOG_API_KEY",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": "POSTHOG_HOST",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST": "",
            }
        )
        resolved = {"enabled": True}

        with pytest.raises(ManifestError, match="QUICKSCALE_ANALYTICS_POSTHOG_HOST"):
            entry_point_module._analytics_post_hook(spec, resolved)

    def test_multiple_empty_keys_reported(self) -> None:
        """Multiple empty settings are all listed in the error message."""
        from quickscale_core.manifest import ManifestError

        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_ANALYTICS_ENABLED": True,
                "QUICKSCALE_ANALYTICS_PROVIDER": "",
                "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": "",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": "",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST": "",
            }
        )
        resolved = {"enabled": True}

        with pytest.raises(ManifestError) as exc_info:
            entry_point_module._analytics_post_hook(spec, resolved)
        msg = str(exc_info.value)
        assert "QUICKSCALE_ANALYTICS_PROVIDER" in msg
        assert "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR" in msg
        assert "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR" in msg
        assert "QUICKSCALE_ANALYTICS_POSTHOG_HOST" in msg

    def test_non_empty_settings_do_not_raise(self) -> None:
        """Non-empty analytics settings pass through without error."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_ANALYTICS_ENABLED": True,
                "QUICKSCALE_ANALYTICS_PROVIDER": "posthog",
                "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR": "POSTHOG_API_KEY",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR": "POSTHOG_HOST",
                "QUICKSCALE_ANALYTICS_POSTHOG_HOST": "https://eu.i.posthog.com",
            }
        )
        resolved = {"enabled": True}

        # Should not raise.
        result = entry_point_module._analytics_post_hook(spec, resolved)
        assert result is not None
        assert isinstance(result, ModuleWiringSpec)

    def test_disabled_short_circuit_still_works(self) -> None:
        """The PR-4 disabled short-circuit returns empty spec before
        reaching the empty-settings check."""
        spec = ModuleWiringSpec(
            settings={
                "QUICKSCALE_ANALYTICS_ENABLED": False,
                "QUICKSCALE_ANALYTICS_PROVIDER": "",
            }
        )
        resolved = {"enabled": False}

        result = entry_point_module._analytics_post_hook(spec, resolved)
        assert isinstance(result, ModuleWiringSpec)
        assert result.apps == ()


# ---------------------------------------------------------------------------
# CR-SA27-001: Org/Storage custom adapter callers must fail closed on
# invalid options (silent-coercion removal caller-parity gap).
# ---------------------------------------------------------------------------


class TestOrgsStorageAdapterFailClosed:
    """Orgs/storage custom manifest-adapter callers must feed validation
    issues into ResolverResult so that assemble_wiring_spec fails closed
    on invalid options instead of silently assembling an invalid spec
    (CR-SA27-001)."""

    def test_orgs_invalid_mode_raises_manifest_error(self) -> None:
        """build_manifest_wiring_spec('orgs', {'mode': 'invalid'})
        raises ManifestError with a descriptive message."""
        from quickscale_core.manifest import ManifestError

        with pytest.raises(ManifestError) as exc_info:
            build_manifest_wiring_spec("orgs", {"mode": "invalid_mode"})
        msg = str(exc_info.value)
        assert "validation issues" in msg
        assert "modules.orgs.mode" in msg

    def test_storage_invalid_backend_raises_manifest_error(self) -> None:
        """build_manifest_wiring_spec('storage', {'backend': 'invalid'})
        raises ManifestError with a descriptive message."""
        from quickscale_core.manifest import ManifestError

        with pytest.raises(ManifestError) as exc_info:
            build_manifest_wiring_spec("storage", {"backend": "invalid_backend"})
        msg = str(exc_info.value)
        assert "validation issues" in msg
        assert "modules.storage.backend" in msg

    def test_orgs_valid_mode_still_succeeds(self) -> None:
        """Valid orgs mode continues to produce a spec (happy path)."""
        spec = build_manifest_wiring_spec("orgs", {"mode": "saas"})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_orgs" in spec.apps

    def test_storage_valid_backend_still_succeeds(self) -> None:
        """Valid storage backend continues to produce a spec (happy path)."""
        spec = build_manifest_wiring_spec(
            "storage", {"backend": "s3", "bucket_name": "b", "region_name": "r"}
        )
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_storage" in spec.apps


# ---------------------------------------------------------------------------
# SA42: Post-hook settings reads fail hard instead of silently coercing
# via .get(key, default).  Missing key -> KeyError; empty blog rate limit
# -> ManifestError (matching SA18.2 precedent).
# ---------------------------------------------------------------------------


class TestBlogPostHookFailHard:
    """Missing/empty blog post-hook settings raise instead of defaulting (SA42)."""

    def test_missing_posts_per_page_raises_key_error(self) -> None:
        """A missing BLOG_POSTS_PER_PAGE raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "BLOG_ENABLE_RSS": True,
                "BLOG_API_RATE_LIMIT": "5/hour",
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="BLOG_POSTS_PER_PAGE"):
            entry_point_module._blog_post_hook(spec, resolved)

    def test_missing_enable_rss_raises_key_error(self) -> None:
        """A missing BLOG_ENABLE_RSS raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "BLOG_POSTS_PER_PAGE": 10,
                "BLOG_API_RATE_LIMIT": "5/hour",
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="BLOG_ENABLE_RSS"):
            entry_point_module._blog_post_hook(spec, resolved)

    def test_missing_rate_limit_raises_key_error(self) -> None:
        """A missing BLOG_API_RATE_LIMIT raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "BLOG_POSTS_PER_PAGE": 10,
                "BLOG_ENABLE_RSS": True,
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="BLOG_API_RATE_LIMIT"):
            entry_point_module._blog_post_hook(spec, resolved)

    def test_empty_rate_limit_raises_manifest_error(self) -> None:
        """An empty BLOG_API_RATE_LIMIT raises ManifestError instead of defaulting."""
        from quickscale_core.manifest import ManifestError

        spec = ModuleWiringSpec(
            settings={
                "BLOG_POSTS_PER_PAGE": 10,
                "BLOG_ENABLE_RSS": True,
                "BLOG_API_RATE_LIMIT": "",
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(ManifestError, match="BLOG_API_RATE_LIMIT"):
            entry_point_module._blog_post_hook(spec, resolved)

    def test_blog_whitespace_only_rate_limit_raises_manifest_error(self) -> None:
        """A whitespace-only BLOG_API_RATE_LIMIT raises ManifestError."""
        from quickscale_core.manifest import ManifestError

        spec = ModuleWiringSpec(
            settings={
                "BLOG_POSTS_PER_PAGE": 10,
                "BLOG_ENABLE_RSS": True,
                "BLOG_API_RATE_LIMIT": "   ",
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(ManifestError, match="BLOG_API_RATE_LIMIT"):
            entry_point_module._blog_post_hook(spec, resolved)

    def test_blog_all_settings_present_passes(self) -> None:
        """All blog settings present and valid pass through without error."""
        spec = ModuleWiringSpec(
            settings={
                "BLOG_POSTS_PER_PAGE": 10,
                "BLOG_ENABLE_RSS": True,
                "BLOG_API_RATE_LIMIT": "5/hour",
            }
        )
        resolved: dict[str, Any] = {}
        result = entry_point_module._blog_post_hook(spec, resolved)
        assert isinstance(result, ModuleWiringSpec)
        assert result.settings["BLOG_POSTS_PER_PAGE"] == 10
        assert result.settings["BLOG_ENABLE_RSS"] is True
        assert result.settings["BLOG_API_RATE_LIMIT"] == "5/hour"


class TestListingsPostHookFailHard:
    """Missing listings post-hook settings raise instead of defaulting (SA42)."""

    def test_missing_listings_per_page_raises_key_error(self) -> None:
        """A missing LISTINGS_PER_PAGE raises KeyError."""
        spec = ModuleWiringSpec(settings={})
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="LISTINGS_PER_PAGE"):
            entry_point_module._listings_post_hook(spec, resolved)

    def test_listings_setting_present_passes(self) -> None:
        """A valid LISTINGS_PER_PAGE passes through without error."""
        spec = ModuleWiringSpec(settings={"LISTINGS_PER_PAGE": 24})
        resolved: dict[str, Any] = {}
        result = entry_point_module._listings_post_hook(spec, resolved)
        assert isinstance(result, ModuleWiringSpec)
        assert result.settings["LISTINGS_PER_PAGE"] == 24


class TestFormsPostHookFailHard:
    """Missing forms post-hook settings raise instead of defaulting (SA42)."""

    def test_missing_forms_per_page_raises_key_error(self) -> None:
        """A missing FORMS_PER_PAGE raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "FORMS_SPAM_PROTECTION": True,
                "FORMS_RATE_LIMIT": "5/hour",
                "FORMS_DATA_RETENTION_DAYS": 365,
                "FORMS_SUBMISSIONS_API": True,
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="FORMS_PER_PAGE"):
            entry_point_module._forms_post_hook(spec, resolved)

    def test_missing_spam_protection_raises_key_error(self) -> None:
        """A missing FORMS_SPAM_PROTECTION raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "FORMS_PER_PAGE": 25,
                "FORMS_RATE_LIMIT": "5/hour",
                "FORMS_DATA_RETENTION_DAYS": 365,
                "FORMS_SUBMISSIONS_API": True,
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="FORMS_SPAM_PROTECTION"):
            entry_point_module._forms_post_hook(spec, resolved)

    def test_missing_rate_limit_raises_key_error(self) -> None:
        """A missing FORMS_RATE_LIMIT raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "FORMS_PER_PAGE": 25,
                "FORMS_SPAM_PROTECTION": True,
                "FORMS_DATA_RETENTION_DAYS": 365,
                "FORMS_SUBMISSIONS_API": True,
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="FORMS_RATE_LIMIT"):
            entry_point_module._forms_post_hook(spec, resolved)

    def test_missing_data_retention_days_raises_key_error(self) -> None:
        """A missing FORMS_DATA_RETENTION_DAYS raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "FORMS_PER_PAGE": 25,
                "FORMS_SPAM_PROTECTION": True,
                "FORMS_RATE_LIMIT": "5/hour",
                "FORMS_SUBMISSIONS_API": True,
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="FORMS_DATA_RETENTION_DAYS"):
            entry_point_module._forms_post_hook(spec, resolved)

    def test_missing_submissions_api_raises_key_error(self) -> None:
        """A missing FORMS_SUBMISSIONS_API raises KeyError."""
        spec = ModuleWiringSpec(
            settings={
                "FORMS_PER_PAGE": 25,
                "FORMS_SPAM_PROTECTION": True,
                "FORMS_RATE_LIMIT": "5/hour",
                "FORMS_DATA_RETENTION_DAYS": 365,
            }
        )
        resolved: dict[str, Any] = {}
        with pytest.raises(KeyError, match="FORMS_SUBMISSIONS_API"):
            entry_point_module._forms_post_hook(spec, resolved)

    def test_forms_all_settings_present_passes(self) -> None:
        """All forms settings present and valid pass through without error."""
        spec = ModuleWiringSpec(
            settings={
                "FORMS_PER_PAGE": 25,
                "FORMS_SPAM_PROTECTION": True,
                "FORMS_RATE_LIMIT": "5/hour",
                "FORMS_DATA_RETENTION_DAYS": 365,
                "FORMS_SUBMISSIONS_API": True,
            }
        )
        resolved: dict[str, Any] = {}
        result = entry_point_module._forms_post_hook(spec, resolved)
        assert isinstance(result, ModuleWiringSpec)
        assert result.settings["FORMS_PER_PAGE"] == 25


class TestNotificationsPostHookFailHard:
    """Notifications derived_settings use direct access instead of .get() defaults (SA42).

    The notifications post-hook is nested inside _notifications_manifest_adapter
    and not directly importable.  We verify through the full adapter path:
    the existing integration test (test_notifications_adapter_returns_spec) proves
    the happy path still works.  The code change from .get(key, default) to
    settings[key] means any missing required setting will now raise KeyError
    instead of silently defaulting.
    """

    def test_notifications_adapter_returns_spec(self) -> None:
        """Notifications adapter still produces a valid spec (SA42 happy path)."""
        spec = build_manifest_wiring_spec("notifications", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_notifications" in spec.apps
        assert spec.settings.get("QUICKSCALE_NOTIFICATIONS_ENABLED") is True

    def test_notifications_missing_enabled_raises_key_error(self) -> None:
        """A missing QUICKSCALE_NOTIFICATIONS_ENABLED raises KeyError (SA42)."""
        import quickscale_core.manifest.resolver as _resolver_mod

        _original = _resolver_mod._project_all_derived_settings

        def _strip_enabled(schema, resolved):
            result = _original(schema, resolved)
            if schema.module_name == "notifications":
                result.pop("QUICKSCALE_NOTIFICATIONS_ENABLED", None)
            return result

        with patch.object(
            _resolver_mod,
            "_project_all_derived_settings",
            side_effect=_strip_enabled,
        ):
            with pytest.raises(KeyError, match="QUICKSCALE_NOTIFICATIONS_ENABLED"):
                build_manifest_wiring_spec("notifications", {})
