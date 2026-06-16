"""Tests for the manifest-driven wiring spec entry point (A3) — core package.

These tests cover the parts of entry_point.py that are testable from within
quickscale_core without a quickscale_cli dependency:
- MANIFEST_ADAPTER_REGISTRY structure and accessibility.
- ManifestAdapterNotFound exception.
- build_manifest_wiring_spec routing for unknown modules.
- Custom adapter registration and unregistration.
- Public exports from quickscale_core.manifest.

Integration tests that call build_manifest_wiring_spec('analytics', ...)
live in quickscale_cli/tests/test_manifest_entry_point_integration.py,
where both packages are on sys.path.
"""

from __future__ import annotations

import pytest

from quickscale_core.manifest import (
    MANIFEST_ADAPTER_REGISTRY,
    ManifestAdapterNotFound,
    build_manifest_wiring_spec,
)
from quickscale_core.manifest.entry_point import (
    MANIFEST_ADAPTER_REGISTRY as REGISTRY_DIRECT,
    ManifestAdapterNotFound as ManifestAdapterNotFoundDirect,
    build_manifest_wiring_spec as build_manifest_wiring_spec_direct,
)
from quickscale_core.module_wiring import ModuleWiringSpec


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
