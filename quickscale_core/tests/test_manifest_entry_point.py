"""Tests for the manifest-driven wiring spec entry point (A3) — core package.

These tests cover the parts of entry_point.py that are testable from within
quickscale_core without a quickscale_cli dependency:
- MANIFEST_ADAPTER_REGISTRY structure and accessibility.
- ManifestAdapterNotFound exception.
- build_manifest_wiring_spec routing for unknown modules.
- Custom adapter registration and unregistration.
- Public exports from quickscale_core.manifest.
- Provenance-sensitive checks for module-owned adapters and the absence of
  core fallback adapters.
- Managed-adapter import/factory failure at an active base path.

SA44 Phase 1: managed adapters are NOT registered at
import time.  The session-scoped ``_session_managed_adapters`` fixture below
registers them explicitly via ``refresh_managed_adapters()`` before any test runs.

Integration tests that call build_manifest_wiring_spec('analytics', ...)
live in quickscale_cli/tests/test_manifest_entry_point_integration.py,
where both packages are on sys.path.
"""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pytest

from quickscale_core.manifest import (
    MANIFEST_ADAPTER_REGISTRY,
    ConfigOption,
    ManifestAdapterNotFound,
    ManifestError,
    ModuleManifest,
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
from quickscale_core.manifest.option_validation import validate_module_options
from quickscale_core.module_wiring import (
    ModuleWiringSpec,
    render_settings_modules_py,
)
from quickscale_modules_auth.adapter import (
    get_manifest_adapter as get_auth_manifest_adapter,
)
from quickscale_modules_orgs.adapter import (
    get_manifest_adapter as get_orgs_manifest_adapter,
)
from quickscale_modules_storage.adapter import (
    get_manifest_adapter as get_storage_manifest_adapter,
)

# SA44 Phase 1: managed adapters are NOT registered
# at import time.  ``refresh_managed_adapters()`` is called by the
# session-scoped autouse fixture below, which only tolerates the
# genuine "managed package not installed" case outside CI. Broken adapter
# imports still fail the unit gate.


def _discovered_inventory() -> set[str]:
    """Return the shipped inventory used by registry transition assertions."""
    from quickscale_core.contracts.module_discovery import (
        discover_shipped_module_names,
    )

    return set(discover_shipped_module_names())


_REGISTERED_ADAPTERS = sorted(_discovered_inventory())


def _is_missing_managed_package_root(exc: Exception, module_name: str) -> bool:
    """Return True only for the current module's missing package root.

    A real missing managed package raises ``ModuleNotFoundError`` with the
    managed package root (for example ``quickscale_modules_billing``) as the
    missing import target. Broken adapters should propagate instead of being
    converted into session-wide skips.
    """

    target_package = f"quickscale_modules_{module_name}"

    # The root package may be reported as the exception itself (direct
    # ModuleNotFoundError) or as its cause (chained ImportError → ...
    # → ModuleNotFoundError).  Check both.
    candidate = exc if isinstance(exc, ModuleNotFoundError) else exc.__cause__
    if not isinstance(candidate, ModuleNotFoundError):
        return False

    missing_module = getattr(candidate, "name", None)
    return missing_module == target_package


def _assert_full_adapter_registry_present() -> None:
    """Fail fast in CI when any expected adapter failed to register."""

    missing = [
        name for name in _REGISTERED_ADAPTERS if name not in MANIFEST_ADAPTER_REGISTRY
    ]
    assert not missing, (
        "CI environment missing expected manifest adapters after session refresh: "
        + ", ".join(sorted(missing))
    )


def _refresh_session_managed_adapters() -> None:
    """Refresh managed adapters per module with deterministic ordering.

    Processes each managed module independently so that a tolerated
    absence case (module not shipped at the active base path, or a
    shipped manifest whose managed package root is genuinely absent)
    does not prevent later modules from being refreshed. Non-tolerated
    adapter failures still propagate.
    """
    import importlib  # noqa: PLC0415

    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        ImproperlyConfigured,
        discover_shipped_module_names,
    )

    shipped_at_base = set(discover_shipped_module_names())
    origins = sorted(shipped_at_base)

    for module_name in _REGISTERED_ADAPTERS:
        if module_name not in shipped_at_base:
            MANIFEST_ADAPTER_REGISTRY.pop(module_name, None)

    for module_name in origins:
        if module_name not in shipped_at_base:
            # Module not present at the active base path — remove any
            # stale registry entry and move on.
            MANIFEST_ADAPTER_REGISTRY.pop(module_name, None)
            continue

        # Module has a manifest at the active base path — the
        # module-owned adapter MUST be importable.
        try:
            adapter_module = importlib.import_module(
                f"quickscale_modules_{module_name}.adapter"
            )
        except ImportError as exc:
            if not _is_missing_managed_package_root(exc, module_name):
                raise ImproperlyConfigured(
                    f"Managed adapter for '{module_name}' not importable: "
                    f"quickscale_modules_{module_name}.adapter could not "
                    f"be loaded. The module package must be installed and "
                    f"importable."
                ) from exc
            # Root package genuinely absent — tolerate and continue.
            continue

        sentinel = getattr(adapter_module, "get_manifest_adapter", None)
        if sentinel is not None:
            MANIFEST_ADAPTER_REGISTRY[module_name] = sentinel()
            continue

        raise ImproperlyConfigured(
            f"Managed adapter for '{module_name}' not importable: "
            f"quickscale_modules_{module_name}.adapter has no "
            f"get_manifest_adapter function."
        )


@pytest.fixture(scope="session", autouse=True)
def _session_managed_adapters() -> None:
    """Refresh managed adapters once per test session.

    Tolerates only the genuine "managed package not installed" case in
    nongated environments. Broken managed-adapter imports keep failing
    closed, and CI additionally asserts that every expected adapter is
    present after the refresh.

    The completeness assertion belongs to this session-scoped refresh of
    the *real* shipped set, not to ``_refresh_session_managed_adapters``
    itself: tests that deliberately narrow the shipped set to exercise
    tolerance call the helper directly, and a registry that is expected
    to be incomplete must not trip a completeness check.
    """

    refresh_managed_adapters()
    if os.environ.get("CI"):
        _assert_full_adapter_registry_present()


class TestSessionManagedAdaptersFixtureGuard:
    """Regression coverage for SA75's narrowed session-fixture behavior."""

    def test_missing_managed_package_is_tolerated_outside_ci(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A genuinely absent managed package still passes without error outside CI."""

        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            discover_shipped_module_names,
        )

        monkeypatch.delenv("CI", raising=False)

        # Simulate billing not being shipped at the active base path.
        def _discover_no_billing() -> list[str]:
            return [n for n in discover_shipped_module_names() if n != "billing"]

        monkeypatch.setattr(
            discover_shipped_module_names.__module__ + ".discover_shipped_module_names",
            _discover_no_billing,
        )

        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        try:
            _refresh_session_managed_adapters()
            assert "billing" not in MANIFEST_ADAPTER_REGISTRY, (
                "billing should not be registered when absent from shipped set"
            )
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)

    def test_broken_managed_adapter_import_is_not_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-package import failures still fail the unit gate."""

        import importlib as _importlib_mod  # noqa: PLC0415

        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            ImproperlyConfigured,
        )

        monkeypatch.delenv("CI", raising=False)

        _orig_import = _importlib_mod.import_module

        def _raise_broken_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "quickscale_modules_billing.adapter":
                raise ImportError("broken managed adapter") from (
                    ModuleNotFoundError(
                        "No module named 'stripe'",
                        name="stripe",
                    )
                )
            return _orig_import(name, *args, **kwargs)

        monkeypatch.setattr(
            _importlib_mod,
            "import_module",
            _raise_broken_import,
        )

        with pytest.raises(ImproperlyConfigured, match="not importable") as exc_info:
            _refresh_session_managed_adapters()

        # The ImproperlyConfigured is raised ``from exc`` (the caught
        # ImportError), preserving the full cause chain.
        assert isinstance(exc_info.value.__cause__, ImportError)
        assert isinstance(exc_info.value.__cause__.__cause__, ModuleNotFoundError)
        assert exc_info.value.__cause__.__cause__.name == "stripe"

    def test_ci_requires_full_adapter_registry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CI fails fast if the session refresh leaves any expected adapter missing."""

        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            discover_shipped_module_names,
        )

        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        monkeypatch.setenv("CI", "1")

        # No managed modules are shipped — the refresh will skip them,
        # leaving only the explicitly-registered analytics adapter.
        monkeypatch.setattr(
            discover_shipped_module_names.__module__ + ".discover_shipped_module_names",
            lambda: [],
        )

        try:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY["analytics"] = lambda opts, **kw: (
                ModuleWiringSpec()
            )

            # Mirrors the session fixture: refresh the real shipped set,
            # then assert completeness. The guard lives on the fixture, so
            # exercising it means running the same two steps in order.
            with pytest.raises(
                AssertionError,
                match="missing expected manifest adapters after session refresh",
            ):
                _refresh_session_managed_adapters()
                if os.environ.get("CI"):
                    _assert_full_adapter_registry_present()
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)


# ---------------------------------------------------------------------------
# CR-SA75-REV-001 regression: one missing managed package coexisting
# with a later managed adapter that is broken or available must not
# suppress failures or prevent the healthy adapter's refresh.
# ---------------------------------------------------------------------------


class TestSA75CoexistenceRegression:
    """Regression coverage for CR-SA75-REV-001.

    Verifies that a genuinely missing managed module (not shipped at the
    active base path) does not prevent later managed adapters from being
    refreshed, and that a shipped module with a broken adapter still
    surfaces its failure.

    Follow-up (CR-SA75-REV-002): corrected the root-package-missing
    detection to check the exception itself (direct ModuleNotFoundError)
    in addition to its cause, so a shipped module whose Python package
    root is genuinely absent is tolerated as a nongated skip.
    """

    def test_missing_package_root_is_tolerated(self, tmp_path: Path) -> None:
        """A shipped module whose Python package root is missing is
        tolerated (skipped) without raising ImproperlyConfigured."""

        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            get_modules_base_path,
            set_modules_base_path,
        )

        _orig_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        _orig_origins = set(MANAGED_ADAPTER_ORIGINS)
        _orig_base = get_modules_base_path()

        try:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(
                {"_test_missing_mod", "_test_absent_pkg_mod"}
            )

            # _test_absent_pkg_mod has a module.yml at the temp base
            # path but its Python package root is missing — must be
            # tolerated as a nongated skip.  _test_missing_mod is
            # genuinely absent from the shipped set.
            modules_dir = tmp_path / "modules"
            (modules_dir / "_test_absent_pkg_mod").mkdir(parents=True)
            (modules_dir / "_test_absent_pkg_mod" / "module.yml").write_text(
                "version: '1'\nname: _test_absent_pkg_mod\n"
            )

            set_modules_base_path(modules_dir)

            # Previously this raised ImproperlyConfigured because the
            # handler only checked exc.__cause__ for ModuleNotFoundError;
            # a direct ModuleNotFoundError (missing package root) was
            # not recognised as the tolerated case.  CR-SA75-REV-002
            # corrected the check to also inspect exc itself.
            _refresh_session_managed_adapters()

            # Neither module's adapter is registrable.
            assert "_test_absent_pkg_mod" not in MANIFEST_ADAPTER_REGISTRY
            assert "_test_missing_mod" not in MANIFEST_ADAPTER_REGISTRY
        finally:
            set_modules_base_path(_orig_base)
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(_orig_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(_orig_origins)

    def test_missing_package_plus_healthy_adapter_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing module is tolerated and a healthy module gets
        registered when both coexist during refresh."""

        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            discover_shipped_module_names,
        )

        # Patch shipped set so only social (which has no RLS
        # dependency in unit tests) is considered shipped.
        def _discover_just_social() -> list[str]:
            return [n for n in discover_shipped_module_names() if n == "social"]

        monkeypatch.setattr(
            discover_shipped_module_names.__module__ + ".discover_shipped_module_names",
            _discover_just_social,
        )

        _orig_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        _orig_origins = set(MANAGED_ADAPTER_ORIGINS)

        try:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update({"_test_missing_mod", "social"})

            _refresh_session_managed_adapters()

            # _test_missing_mod was not shipped → absent from registry.
            assert "_test_missing_mod" not in MANIFEST_ADAPTER_REGISTRY
            # social WAS shipped and its adapter imports fine.
            assert "social" in MANIFEST_ADAPTER_REGISTRY
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(_orig_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(_orig_origins)


# ---------------------------------------------------------------------------
# MANIFEST_ADAPTER_REGISTRY
# ---------------------------------------------------------------------------


class TestManifestAdapterRegistry:
    """Tests for the MANIFEST_ADAPTER_REGISTRY dict."""

    def test_registry_is_dict(self) -> None:
        """MANIFEST_ADAPTER_REGISTRY is a dict."""
        assert isinstance(MANIFEST_ADAPTER_REGISTRY, dict)

    def test_analytics_registered_after_session_refresh(self) -> None:
        """Analytics adapter is registered by the session refresh fixture."""
        assert "analytics" in MANIFEST_ADAPTER_REGISTRY

    def test_analytics_value_is_callable(self) -> None:
        """The analytics registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["analytics"])

    def test_notifications_registered_after_session_refresh(self) -> None:
        """Notifications adapter is registered by the session refresh fixture."""
        assert "notifications" in MANIFEST_ADAPTER_REGISTRY

    def test_notifications_value_is_callable(self) -> None:
        """The notifications registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["notifications"])

    def test_auth_registered_after_session_refresh(self) -> None:
        """Auth adapter is registered by the session refresh fixture."""
        assert "auth" in MANIFEST_ADAPTER_REGISTRY

    def test_auth_value_is_callable(self) -> None:
        """The auth registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["auth"])

    def test_orgs_registered_after_session_refresh(self) -> None:
        """Orgs adapter is registered by the session refresh fixture."""
        assert "orgs" in MANIFEST_ADAPTER_REGISTRY

    def test_orgs_value_is_callable(self) -> None:
        """The orgs registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["orgs"])

    def test_storage_registered_after_session_refresh(self) -> None:
        """Storage adapter is registered by the session refresh fixture."""
        assert "storage" in MANIFEST_ADAPTER_REGISTRY

    def test_storage_value_is_callable(self) -> None:
        """The storage registry entry is callable."""
        assert callable(MANIFEST_ADAPTER_REGISTRY["storage"])

    def test_social_registered_via_explicit_refresh(self) -> None:
        """Social adapter is registered after explicit refresh_managed_adapters().

        SA44 Phase 1: managed adapters are no longer registered at import time.
        The session-scoped ``_session_managed_adapters`` fixture in this module
        calls ``refresh_managed_adapters()`` and safely handles
        ``ImproperlyConfigured`` when a module is not importable.
        """
        if "social" not in MANIFEST_ADAPTER_REGISTRY:
            pytest.skip("social adapter not registered (managed module not available)")
        assert "social" in MANIFEST_ADAPTER_REGISTRY

    def test_social_value_is_callable(self) -> None:
        """The social registry entry is callable after explicit refresh."""
        if "social" not in MANIFEST_ADAPTER_REGISTRY:
            pytest.skip("social adapter not registered (managed module not available)")
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

# Adapters that require project_package to build a spec.
_ADAPTERS_REQUIRING_PROJECT_PACKAGE = frozenset({"social"})


def _available_adapters() -> list[str]:
    """Return the subset of expected adapters present in the registry.

    Filters *REGISTERED_ADAPTERS* to names that are actually present in
    ``MANIFEST_ADAPTER_REGISTRY``. Managed adapters may be absent when the
    session fixture caught ``ImproperlyConfigured`` because their module
    packages were not importable.
    """
    return [name for name in _REGISTERED_ADAPTERS if name in MANIFEST_ADAPTER_REGISTRY]


class TestRegisteredAdapterPaths:
    """Each registered adapter produces a valid ModuleWiringSpec via the
    public build_manifest_wiring_spec entry point."""

    def test_all_expected_adapters_registered(self) -> None:
        """Every available adapter (including managed ones that loaded)
        is present in the registry."""
        for name in _available_adapters():
            assert name in MANIFEST_ADAPTER_REGISTRY, f"{name} adapter not registered"

    def test_analytics_adapter_returns_spec(self) -> None:
        spec = build_manifest_wiring_spec("analytics", {"enabled": True})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_analytics" in spec.apps

    def test_analytics_disabled_keeps_apps_and_drops_public_urls(self) -> None:
        spec = build_manifest_wiring_spec("analytics", {"enabled": False})
        assert isinstance(spec, ModuleWiringSpec)
        assert "quickscale_modules_analytics" in spec.apps
        assert spec.url_includes == ()
        assert spec.settings["QUICKSCALE_ANALYTICS_ENABLED"] is False
        assert (
            spec.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
            == "__QS_ENV__:POSTHOG_API_KEY"
        )
        assert (
            spec.settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE"]
            == "__QS_ENV__:POSTHOG_HOST"
        )

    def test_billing_adapter_returns_spec(self) -> None:
        if "billing" not in MANIFEST_ADAPTER_REGISTRY:
            pytest.skip("billing adapter not registered (managed module not available)")
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
        if "crm" not in MANIFEST_ADAPTER_REGISTRY:
            pytest.skip("crm adapter not registered (managed module not available)")
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
        if "social" not in MANIFEST_ADAPTER_REGISTRY:
            pytest.skip("social adapter not registered (managed module not available)")
        spec = build_manifest_wiring_spec("social", {}, project_package="myproject")
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.apps == ("quickscale_modules_social",)
        assert "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED" in spec.settings
        assert len(spec.managed_files) == 3

    def test_social_adapter_requires_project_package(self) -> None:
        """Social adapter raises ValueError without project_package."""
        if "social" not in MANIFEST_ADAPTER_REGISTRY:
            pytest.skip("social adapter not registered (managed module not available)")
        with pytest.raises(ValueError, match="project_package"):
            build_manifest_wiring_spec("social", {})

    def test_each_adapter_accepts_none_options(self) -> None:
        """Every registered adapter tolerates options=None."""
        for name in _available_adapters():
            if name in _ADAPTERS_REQUIRING_PROJECT_PACKAGE:
                continue
            spec = build_manifest_wiring_spec(name, None)
            assert isinstance(spec, ModuleWiringSpec), (
                f"{name} adapter did not return ModuleWiringSpec with None options"
            )

    def test_each_adapter_accepts_empty_options(self) -> None:
        """Every registered adapter tolerates options={}."""
        for name in _available_adapters():
            if name in _ADAPTERS_REQUIRING_PROJECT_PACKAGE:
                continue
            spec = build_manifest_wiring_spec(name, {})
            assert isinstance(spec, ModuleWiringSpec), (
                f"{name} adapter did not return ModuleWiringSpec with empty options"
            )

    def test_each_adapter_forwards_project_package(self) -> None:
        """project_package kwarg is forwarded without error."""
        for name in _available_adapters():
            spec = build_manifest_wiring_spec(name, {}, project_package="myproject")
            assert isinstance(spec, ModuleWiringSpec), (
                f"{name} adapter failed with project_package kwarg"
            )

    def test_all_adapters_emit_manifest_owned_mutable_settings(self) -> None:
        """Every public adapter preserves its complete manifest setting map."""
        inventory = {
            module_name: (
                load_module_manifest(module_name),
                load_module_manifest(module_name).get_django_settings_mapping(),
                load_module_manifest(module_name).get_defaults(),
            )
            for module_name in _REGISTERED_ADAPTERS
        }

        for module_name, (_, mapping, defaults) in inventory.items():
            kwargs = {"project_package": "myapp"} if module_name == "social" else {}
            spec = build_manifest_wiring_spec(module_name, {}, **kwargs)

            for option_name, setting_name in mapping.items():
                assert setting_name in spec.settings, (
                    f"{module_name} omitted manifest setting {setting_name} "
                    f"for option {option_name}"
                )
                assert spec.settings[setting_name] == defaults[option_name], (
                    f"{module_name} changed manifest default for {option_name}"
                )

    @pytest.mark.parametrize(
        ("module_name", "overrides", "setting_name", "expected"),
        [
            ("analytics", {"enabled": False}, "QUICKSCALE_ANALYTICS_ENABLED", False),
            (
                "notifications",
                {"default_tags": []},
                "QUICKSCALE_NOTIFICATIONS_DEFAULT_TAGS",
                [],
            ),
        ],
    )
    def test_manifest_setting_edge_values_survive_public_adapters(
        self,
        module_name: str,
        overrides: dict[str, object],
        setting_name: str,
        expected: object,
    ) -> None:
        """False and empty values remain settings rather than being omitted."""
        spec = build_manifest_wiring_spec(module_name, overrides)

        assert spec.settings[setting_name] == expected

    def test_social_empty_allowlist_is_refused_by_manifest_authority(self) -> None:
        """The shipped social manifest forbids an empty provider allowlist.

        The generic boundary enforces the manifest's own ``not_empty`` check
        before the adapter's hook runs, so the empty list is refused naming
        the manifest setting path instead of silently surviving as a setting.
        """
        with pytest.raises(ManifestError) as exc_info:
            build_manifest_wiring_spec(
                "social", {"provider_allowlist": []}, project_package="myapp"
            )
        message = str(exc_info.value)
        assert "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST" in message
        assert "modules.social.provider_allowlist" in message


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

    _MANAGED_MODULES = frozenset(_REGISTERED_ADAPTERS)

    def _available_managed(self) -> frozenset[str]:
        """Return managed modules that are actually registered."""
        return frozenset(
            n for n in self._MANAGED_MODULES if n in MANIFEST_ADAPTER_REGISTRY
        )

    def test_module_owned_adapters_are_active_in_monorepo(self) -> None:
        """When the module package is importable (monorepo/embedded context),
        the registry entry for each managed module should be the module-owned
        implementation, not the core fallback."""
        available = self._available_managed()
        if not available:
            pytest.skip("no managed modules are available in this environment")
        for name in available:
            fn_file = inspect.getfile(MANIFEST_ADAPTER_REGISTRY[name])
            assert "quickscale_modules" in fn_file, (
                f"{name} adapter should be module-owned in monorepo context, "
                f"but source is {fn_file}"
            )

    def test_module_owned_adapter_source_location(self) -> None:
        """Each managed module's active adapter comes from its own package."""
        expected = {
            name: f"quickscale_modules_{name}/adapter.py"
            for name in self._MANAGED_MODULES
        }
        available = self._available_managed()
        if not available:
            pytest.skip("no managed modules are available in this environment")
        for name in available:
            fn_file = inspect.getfile(MANIFEST_ADAPTER_REGISTRY[name])
            expected_suffix = expected[name]
            assert fn_file.endswith(expected_suffix), (
                f"{name} adapter expected to end with {expected_suffix}, got {fn_file}"
            )

    def test_module_owned_adapter_produces_valid_spec(self) -> None:
        """Module-owned adapters produce a valid ModuleWiringSpec via
        the public build_manifest_wiring_spec entry point."""
        available = self._available_managed()
        if not available:
            pytest.skip("no managed modules are available in this environment")
        for name in available:
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
                assert "QUICKSCALE_CRM_DEALS_PER_PAGE" in spec.settings

    def test_managed_adapter_origins_refect_registered_modules(self) -> None:
        """MANAGED_ADAPTER_ORIGINS contains exactly the managed modules."""
        assert MANAGED_ADAPTER_ORIGINS == self._MANAGED_MODULES, (
            f"Expected MANAGED_ADAPTER_ORIGINS to be {self._MANAGED_MODULES}, "
            f"got {MANAGED_ADAPTER_ORIGINS}"
        )

    def test_custom_entries_preserved_after_refresh(self) -> None:
        """Custom (non-managed) entries survive a call to
        refresh_managed_adapters unchanged."""
        from quickscale_core.contracts.module_discovery import ImproperlyConfigured

        original = dict(MANIFEST_ADAPTER_REGISTRY)
        try:
            MANIFEST_ADAPTER_REGISTRY["_test_custom"] = lambda opts, **kw: (
                ModuleWiringSpec()
            )
            try:
                refresh_managed_adapters()
                refresh_ok = True
            except ImproperlyConfigured:
                refresh_ok = False
            # Custom entry survives regardless of managed module availability.
            assert "_test_custom" in MANIFEST_ADAPTER_REGISTRY, (
                "Custom entry was removed after refresh"
            )
            # Managed entries should still be present when refresh succeeded.
            if refresh_ok:
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


class TestDiscoveredInventoryRegistryTransition:
    """Registry ownership is derived from one source inventory transaction."""

    def test_refresh_uses_one_discovery_and_registers_exact_inventory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quickscale_core.contracts import module_discovery

        discovered = set(module_discovery.discover_shipped_module_names())
        original_presence = module_discovery.discover_module_presence
        calls: list[object] = []
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)

        def custom(options: object, **kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec(apps=("custom",))

        def discover_once(*args: object, **kwargs: object) -> object:
            calls.append(object())
            return original_presence(*args, **kwargs)

        monkeypatch.setattr(
            module_discovery,
            "discover_module_presence",
            discover_once,
        )
        try:
            MANIFEST_ADAPTER_REGISTRY["_test_custom"] = custom
            refresh_managed_adapters()

            assert calls and len(calls) == 1
            assert len(discovered) == 12
            assert MANAGED_ADAPTER_ORIGINS == discovered
            assert set(MANAGED_ADAPTER_ORIGINS) == {
                name for name in MANIFEST_ADAPTER_REGISTRY if name != "_test_custom"
            }
            assert all(callable(MANIFEST_ADAPTER_REGISTRY[name]) for name in discovered)
            assert MANIFEST_ADAPTER_REGISTRY["_test_custom"] is custom
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)

    def test_scoped_refresh_registers_generated_subset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Generated projects load only their active embedded adapters."""
        from quickscale_core.contracts import module_discovery

        active = {"auth", "orgs"}
        bundled = set(module_discovery.discover_bundled_module_names())
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)

        monkeypatch.setattr(
            module_discovery,
            "discover_bundled_module_names",
            lambda: sorted(bundled),
        )
        monkeypatch.setattr(
            module_discovery,
            "discover_module_presence",
            lambda **_kwargs: [
                module_discovery.ModulePresenceRecord(
                    name,
                    module_discovery.ModulePresenceState.ACTIVE,
                    Path("/tmp") / name,
                )
                for name in sorted(active)
            ],
        )
        monkeypatch.setattr(
            entry_point_module,
            "_load_managed_adapter",
            lambda _name: lambda _options, **_kwargs: ModuleWiringSpec(),
        )
        try:
            refresh_managed_adapters()

            assert MANAGED_ADAPTER_ORIGINS == active
            assert active.issubset(MANIFEST_ADAPTER_REGISTRY)
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)

    def test_incomplete_module_fails_before_adapter_import_atomically(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An incomplete directory cannot partially refresh managed state."""
        from quickscale_core.contracts.module_discovery import (
            ImproperlyConfigured,
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "_test_incomplete"
        modules_dir = tmp_path / "modules"
        (modules_dir / module_name).mkdir(parents=True)
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        registry_identity = id(MANIFEST_ADAPTER_REGISTRY)
        origins_identity = id(MANAGED_ADAPTER_ORIGINS)
        prior_registry = {"_test_custom": lambda *_args, **_kwargs: ModuleWiringSpec()}
        prior_origins = {"_test_custom"}
        imports: list[str] = []

        def fail_if_imported(name: str) -> object:
            imports.append(name)
            raise AssertionError("incomplete modules must fail before adapter import")

        try:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(prior_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(prior_origins)
            set_modules_base_path(modules_dir)
            monkeypatch.setattr(
                entry_point_module, "_load_managed_adapter", fail_if_imported
            )

            with pytest.raises(
                ImproperlyConfigured, match="_test_incomplete"
            ) as exc_info:
                refresh_managed_adapters()

            assert "module.yml" in str(exc_info.value)
            assert imports == []
            assert id(MANIFEST_ADAPTER_REGISTRY) == registry_identity
            assert id(MANAGED_ADAPTER_ORIGINS) == origins_identity
            assert MANIFEST_ADAPTER_REGISTRY == prior_registry
            assert MANAGED_ADAPTER_ORIGINS == prior_origins
            assert get_modules_base_path() == modules_dir
        finally:
            set_modules_base_path(original_base)
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)

    def test_undeclared_active_module_fails_before_import_atomically(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An undeclared active module is rejected before any import or commit."""
        from quickscale_core.contracts.module_discovery import (
            ImproperlyConfigured,
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "ghost"
        package_name = f"quickscale_modules_{module_name}"
        modules_dir = tmp_path / "modules"
        module_dir = modules_dir / module_name
        module_dir.mkdir(parents=True)
        manifest_path = module_dir / "module.yml"
        manifest_path.write_text(f"version: '1'\nname: {module_name}\n")

        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_sys_path = sys.path.copy()
        original_package_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == package_name or name.startswith(f"{package_name}.")
        }
        registry_identity = id(MANIFEST_ADAPTER_REGISTRY)
        origins_identity = id(MANAGED_ADAPTER_ORIGINS)

        def prior_adapter(*_args: object, **_kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec(apps=("prior",))

        prior_registry = {"_test_custom": prior_adapter}
        prior_origins = {"_test_custom"}
        prior_package = ModuleType(package_name)
        prior_child = ModuleType(f"{package_name}.prior")
        expected_package_modules = dict(original_package_modules)
        expected_package_modules.update(
            {
                package_name: prior_package,
                f"{package_name}.prior": prior_child,
            }
        )
        imports: list[str] = []

        def fail_if_imported(name: str) -> object:
            imports.append(name)
            raise AssertionError(
                "undeclared active modules must fail before adapter import"
            )

        try:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(prior_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(prior_origins)
            sys.modules[package_name] = prior_package
            sys.modules[f"{package_name}.prior"] = prior_child
            set_modules_base_path(modules_dir)
            monkeypatch.setattr(
                entry_point_module, "_load_managed_adapter", fail_if_imported
            )

            with pytest.raises(
                ImproperlyConfigured, match="outside the release inventory"
            ) as exc_info:
                refresh_managed_adapters()

            assert "ghost" in str(exc_info.value)
            assert imports == []
            assert id(MANIFEST_ADAPTER_REGISTRY) == registry_identity
            assert id(MANAGED_ADAPTER_ORIGINS) == origins_identity
            assert MANIFEST_ADAPTER_REGISTRY == prior_registry
            assert MANAGED_ADAPTER_ORIGINS == prior_origins
            assert sys.path == original_sys_path
            assert {
                name: module
                for name, module in sys.modules.items()
                if name == package_name or name.startswith(f"{package_name}.")
            } == expected_package_modules
        finally:
            set_modules_base_path(original_base)
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)
            for name in list(sys.modules):
                if name == package_name or name.startswith(f"{package_name}."):
                    sys.modules.pop(name, None)
            sys.modules.update(original_package_modules)
            sys.path[:] = original_sys_path

    def test_failed_resolution_preserves_registry_and_origins_atomically(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quickscale_core.contracts import module_discovery
        from quickscale_core.contracts.module_discovery import ImproperlyConfigured

        discovered = set(module_discovery.discover_shipped_module_names())
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        registry_identity = id(MANIFEST_ADAPTER_REGISTRY)
        origins_identity = id(MANAGED_ADAPTER_ORIGINS)
        prior_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        prior_origins = set(MANAGED_ADAPTER_ORIGINS)
        failing_name = sorted(discovered)[-1]
        resolved: list[str] = []

        monkeypatch.setattr(
            module_discovery,
            "discover_module_presence",
            lambda **_kwargs: [
                module_discovery.ModulePresenceRecord(
                    name,
                    module_discovery.ModulePresenceState.ACTIVE,
                    Path("/tmp") / name,
                )
                for name in sorted(discovered)
            ],
        )

        def fail_after_resolution(
            module_name: str,
        ) -> object:
            resolved.append(module_name)
            if module_name == failing_name:
                raise ImproperlyConfigured("broken discovered adapter")
            return lambda options, **kwargs: ModuleWiringSpec()

        monkeypatch.setattr(
            entry_point_module,
            "_load_managed_adapter",
            fail_after_resolution,
        )
        try:
            with pytest.raises(ImproperlyConfigured, match="broken discovered adapter"):
                refresh_managed_adapters()
            assert len(resolved) == len(discovered)
            assert id(MANIFEST_ADAPTER_REGISTRY) == registry_identity
            assert id(MANAGED_ADAPTER_ORIGINS) == origins_identity
            assert MANIFEST_ADAPTER_REGISTRY == prior_registry
            assert MANAGED_ADAPTER_ORIGINS == prior_origins
        finally:
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)

    def test_no_final_inline_adapter_blocks_or_direct_registrations(self) -> None:
        source = Path(inspect.getfile(entry_point_module)).read_text()
        tree = ast.parse(source)
        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert not function_names.intersection(
            {
                "_auth_manifest_adapter",
                "_orgs_manifest_adapter",
                "_storage_manifest_adapter",
            }
        )
        assert 'MANIFEST_ADAPTER_REGISTRY["auth"]' not in source
        assert 'MANIFEST_ADAPTER_REGISTRY["orgs"]' not in source
        assert 'MANIFEST_ADAPTER_REGISTRY["storage"]' not in source


# ---------------------------------------------------------------------------
# ImproperlyConfigured regression (AF7-CR-REV-002): verify that
# refresh_managed_adapters raises ImproperlyConfigured when a managed
# module has a manifest at the active base path but its Python adapter
# package is not importable.
# ---------------------------------------------------------------------------


class TestRefreshManagedAdaptersFailure:
    """Managed-adapter import/factory failure at an active base path raises
    ImproperlyConfigured (AF7 fail-hard decision)."""

    def test_no_argument_refresh_accepts_active_embedded_subset_atomically(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Project refresh loads the active subset from one presence snapshot."""
        from quickscale_core.contracts import module_discovery
        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            get_modules_base_path,
            set_modules_base_path,
        )

        original_base = get_modules_base_path()
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        modules_dir = tmp_path / "modules"
        active = {"auth", "orgs"}
        bundled = set(module_discovery.discover_bundled_module_names())

        adapters = {
            name: (lambda options, **kwargs: ModuleWiringSpec())
            for name in ("auth", "orgs")
        }
        monkeypatch.setattr(
            module_discovery,
            "discover_bundled_module_names",
            lambda: sorted(bundled),
        )
        monkeypatch.setattr(
            module_discovery,
            "discover_module_presence",
            lambda **_kwargs: [
                module_discovery.ModulePresenceRecord(
                    name,
                    module_discovery.ModulePresenceState.ACTIVE,
                    modules_dir / name,
                )
                for name in sorted(active)
            ],
        )
        monkeypatch.setattr(
            entry_point_module,
            "_load_managed_adapter",
            lambda name: adapters[name],
        )
        set_modules_base_path(modules_dir)
        try:
            refresh_managed_adapters()
            assert MANAGED_ADAPTER_ORIGINS == active
            assert set(MANIFEST_ADAPTER_REGISTRY) == active
            assert MANIFEST_ADAPTER_REGISTRY["orgs"] is adapters["orgs"]
            assert MANIFEST_ADAPTER_REGISTRY["auth"] is adapters["auth"]
        finally:
            set_modules_base_path(original_base)
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)

    def test_source_only_discovery_rejects_bundled_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``refresh_managed_adapters`` uses ``discover_shipped_module_names``
        directly (source-only), NOT ``get_discovered_module_names`` (which
        falls back to bundled).  When the monorepo is not available, it must
        raise ``ImproperlyConfigured`` regardless of bundled availability.
        """
        from quickscale_core.contracts import module_discovery as _md
        from quickscale_core.contracts.module_discovery import (
            ImproperlyConfigured,
        )

        original_override = _md._modules_base_path
        _md._modules_base_path = None
        try:
            monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"
            real_is_dir = Path.is_dir

            def _no_monorepo(self: Path) -> bool:
                if self.resolve() == monorepo_path.resolve():
                    return False
                return real_is_dir(self)

            monkeypatch.setattr(Path, "is_dir", _no_monorepo)

            # bundled manifests ARE available, but refresh_managed_adapters
            # uses source-only discover_shipped_module_names which raises.
            with pytest.raises(
                ImproperlyConfigured,
                match="Modules base path not found",
            ):
                refresh_managed_adapters()
        finally:
            _md._modules_base_path = original_override

    def test_raises_improperly_configured_when_adapter_not_importable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """refresh_managed_adapters raises ImproperlyConfigured when a managed
        module has a module.yml at the active base path but its Python adapter
        package cannot be imported."""
        from quickscale_core.contracts.module_discovery import (
            ImproperlyConfigured,
            get_modules_base_path,
            set_modules_base_path,
        )

        # Save and restore the full registry / origins so this test does not
        # leak state to siblings.
        _orig_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        _orig_origins = set(MANAGED_ADAPTER_ORIGINS)

        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                1,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: ["_test_missing_adapter"],
            )
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

    def test_failed_refresh_preserves_registry_content_and_identity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A later managed import failure cannot partially commit earlier work."""
        import importlib as _importlib_mod  # noqa: PLC0415

        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            ImproperlyConfigured,
            get_modules_base_path,
            set_modules_base_path,
        )

        first_name = "_test_atomic_first"
        failing_name = "_test_atomic_second"
        failing_package = f"quickscale_modules_{failing_name}"
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_failing_package = sys.modules.get(failing_package)
        registry_identity = id(MANIFEST_ADAPTER_REGISTRY)

        def first_adapter(*args: object, **kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec(apps=("new.first",))

        def old_first_adapter(*args: object, **kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec(apps=("old.first",))

        def old_second_adapter(*args: object, **kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec(apps=("old.second",))

        def custom_adapter(*args: object, **kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec(apps=("custom",))

        first_module = ModuleType(f"quickscale_modules_{first_name}.adapter")
        setattr(first_module, "get_manifest_adapter", lambda: first_adapter)
        real_import = _importlib_mod.import_module

        def _import_adapter(name: str, *args: object, **kwargs: object) -> object:
            if name == f"quickscale_modules_{first_name}.adapter":
                return first_module
            if name == f"{failing_package}.adapter":
                raise ImportError("later managed adapter failed")
            return real_import(name, *args, **kwargs)

        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                2,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: [first_name, failing_name],
            )
            modules_dir = tmp_path / "modules"
            for module_name in (first_name, failing_name):
                module_dir = modules_dir / module_name
                module_dir.mkdir(parents=True)
                (module_dir / "module.yml").write_text(
                    f"version: '1'\nname: {module_name}\n"
                )

            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(
                {
                    first_name: old_first_adapter,
                    failing_name: old_second_adapter,
                    "_test_custom": custom_adapter,
                }
            )
            expected_registry = dict(MANIFEST_ADAPTER_REGISTRY)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update({first_name, failing_name})
            set_modules_base_path(modules_dir)
            sys.modules[failing_package] = ModuleType(failing_package)
            monkeypatch.setattr(_importlib_mod, "import_module", _import_adapter)

            with pytest.raises(ImproperlyConfigured, match="not importable"):
                refresh_managed_adapters()

            assert id(MANIFEST_ADAPTER_REGISTRY) == registry_identity
            assert MANIFEST_ADAPTER_REGISTRY == expected_registry
        finally:
            set_modules_base_path(original_base)
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)
            if original_failing_package is None:
                sys.modules.pop(failing_package, None)
            else:
                sys.modules[failing_package] = original_failing_package


class TestSA146ManagedAdapterImportRetry:
    """Embedded managed adapters can be imported without weakening fail-hard."""

    @staticmethod
    def _write_embedded_module(
        modules_dir: Path,
        module_name: str,
        adapter_source: str,
    ) -> Path:
        module_dir = modules_dir / module_name
        src_dir = module_dir / "src"
        package_dir = src_dir / f"quickscale_modules_{module_name}"
        package_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text(f"version: '1'\nname: {module_name}\n")
        (package_dir / "__init__.py").write_text("")
        (package_dir / "adapter.py").write_text(adapter_source)
        return src_dir

    @staticmethod
    def _restore_state(
        original_registry: dict[str, Any],
        original_origins: set[str],
        original_base: Path,
        module_name: str,
    ) -> None:
        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            set_modules_base_path,
        )

        set_modules_base_path(original_base)
        MANIFEST_ADAPTER_REGISTRY.clear()
        MANIFEST_ADAPTER_REGISTRY.update(original_registry)
        MANAGED_ADAPTER_ORIGINS.clear()
        MANAGED_ADAPTER_ORIGINS.update(original_origins)
        sys.modules.pop(f"quickscale_modules_{module_name}.adapter", None)
        sys.modules.pop(f"quickscale_modules_{module_name}", None)

    def test_embedded_src_retry_registers_adapter_and_restores_sys_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fresh embedded source tree is searched only for the retry."""
        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "_test_sa146_retry"
        adapter_source = """from quickscale_core.module_wiring import ModuleWiringSpec


def get_manifest_adapter():
    return lambda options, **kwargs: ModuleWiringSpec()
"""
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_sys_path = sys.path.copy()
        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                1,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: [module_name],
            )
            modules_dir = tmp_path / "modules"
            src_dir = self._write_embedded_module(
                modules_dir, module_name, adapter_source
            )
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.add(module_name)
            set_modules_base_path(modules_dir)

            refresh_managed_adapters()

            assert module_name in MANIFEST_ADAPTER_REGISTRY
            assert callable(MANIFEST_ADAPTER_REGISTRY[module_name])
            assert sys.path == original_sys_path
            assert str(src_dir) not in sys.path
        finally:
            self._restore_state(
                original_registry, original_origins, original_base, module_name
            )
            sys.path[:] = original_sys_path

    def test_embedded_src_import_failure_still_fails_and_restores_sys_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A broken adapter in embedded source still raises fail-hard."""
        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            ImproperlyConfigured,
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "_test_sa146_broken"
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_sys_path = sys.path.copy()
        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                1,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: [module_name],
            )
            modules_dir = tmp_path / "modules"
            self._write_embedded_module(
                modules_dir,
                module_name,
                "raise ImportError('broken embedded adapter')\n",
            )
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.add(module_name)
            set_modules_base_path(modules_dir)

            with pytest.raises(
                ImproperlyConfigured, match="not importable"
            ) as exc_info:
                refresh_managed_adapters()

            assert str(exc_info.value.__cause__) == "broken embedded adapter"
            assert sys.path == original_sys_path
        finally:
            self._restore_state(
                original_registry, original_origins, original_base, module_name
            )
            sys.path[:] = original_sys_path

    def test_importable_package_does_not_mutate_sys_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An already importable package uses the primary path unchanged."""
        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "_test_sa146_importable"
        adapter_source = """from quickscale_core.module_wiring import ModuleWiringSpec


def get_manifest_adapter():
    return lambda options, **kwargs: ModuleWiringSpec()
"""
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_sys_path = sys.path.copy()
        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                1,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: [module_name],
            )
            modules_dir = tmp_path / "modules"
            src_dir = self._write_embedded_module(
                modules_dir, module_name, adapter_source
            )
            sys.path.insert(0, str(src_dir))
            importable_sys_path = sys.path.copy()
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.add(module_name)
            set_modules_base_path(modules_dir)

            refresh_managed_adapters()

            assert module_name in MANIFEST_ADAPTER_REGISTRY
            assert sys.path == importable_sys_path
        finally:
            self._restore_state(
                original_registry, original_origins, original_base, module_name
            )
            sys.path[:] = original_sys_path

    def test_importable_package_does_not_retry_after_primary_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A broken adapter does not retry when its package root is importable."""
        import importlib as _importlib_mod  # noqa: PLC0415

        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            ImproperlyConfigured,
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "_test_sa146_importable_failure"
        package_name = f"quickscale_modules_{module_name}"
        adapter_name = f"{package_name}.adapter"
        adapter_source = """from quickscale_core.module_wiring import ModuleWiringSpec


def get_manifest_adapter():
    return lambda options, **kwargs: ModuleWiringSpec()
"""
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_sys_path = sys.path.copy()
        original_package = sys.modules.get(package_name)
        import_attempts: list[str] = []
        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                1,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: [module_name],
            )
            modules_dir = tmp_path / "modules"
            src_dir = self._write_embedded_module(
                modules_dir, module_name, adapter_source
            )

            # The package root is already importable, while its adapter import
            # fails.  A second call would succeed, so this test proves the
            # importable-root guard prevents the embedded-src retry.
            package_root = ModuleType(package_name)
            package_root.__path__ = [str(src_dir / package_name)]
            sys.modules[package_name] = package_root
            fake_adapter = ModuleType(adapter_name)
            setattr(
                fake_adapter,
                "get_manifest_adapter",
                lambda: lambda options, **kwargs: ModuleWiringSpec(),
            )

            original_import = _importlib_mod.import_module

            def _fail_once_then_succeed(
                name: str, *args: object, **kwargs: object
            ) -> object:
                if name == adapter_name:
                    import_attempts.append(name)
                    if len(import_attempts) == 1:
                        raise ImportError("primary adapter failure")
                    return fake_adapter
                return original_import(name, *args, **kwargs)

            monkeypatch.setattr(
                _importlib_mod,
                "import_module",
                _fail_once_then_succeed,
            )
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.add(module_name)
            set_modules_base_path(modules_dir)

            with pytest.raises(ImproperlyConfigured, match="not importable"):
                refresh_managed_adapters()

            assert import_attempts == [adapter_name]
            assert module_name not in MANIFEST_ADAPTER_REGISTRY
            assert sys.path == original_sys_path
        finally:
            self._restore_state(
                original_registry, original_origins, original_base, module_name
            )
            if original_package is None:
                sys.modules.pop(package_name, None)
            else:
                sys.modules[package_name] = original_package
            sys.path[:] = original_sys_path

    def test_distinct_embedded_bases_load_their_own_adapter_without_cache_leakage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each base executes its own adapter and leaves ``sys.modules`` exact."""
        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "_test_sa146_distinct_bases"
        package_name = f"quickscale_modules_{module_name}"
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_sys_path = sys.path.copy()
        original_package_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == package_name or name.startswith(f"{package_name}.")
        }

        def _adapter_source(marker: str) -> str:
            return f'''from quickscale_core.module_wiring import ModuleWiringSpec


def _adapter(options, **kwargs):
    return ModuleWiringSpec(settings={{"SOURCE_MARKER": "{marker}"}})


def get_manifest_adapter():
    return _adapter
'''

        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                1,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: [module_name],
            )
            first_base = tmp_path / "first" / "modules"
            second_base = tmp_path / "second" / "modules"
            self._write_embedded_module(
                first_base, module_name, _adapter_source("first")
            )
            self._write_embedded_module(
                second_base, module_name, _adapter_source("second")
            )
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.add(module_name)

            set_modules_base_path(first_base)
            refresh_managed_adapters()
            first_adapter = MANIFEST_ADAPTER_REGISTRY[module_name]
            assert first_adapter({}).settings["SOURCE_MARKER"] == "first"

            set_modules_base_path(second_base)
            refresh_managed_adapters()
            second_adapter = MANIFEST_ADAPTER_REGISTRY[module_name]
            assert second_adapter({}).settings["SOURCE_MARKER"] == "second"
            assert first_adapter({}).settings["SOURCE_MARKER"] == "first"
            assert sys.path == original_sys_path
            assert {
                name: module
                for name, module in sys.modules.items()
                if name == package_name or name.startswith(f"{package_name}.")
            } == original_package_modules
        finally:
            self._restore_state(
                original_registry, original_origins, original_base, module_name
            )
            sys.path[:] = original_sys_path

    def test_failed_embedded_import_restores_relevant_sys_modules_exactly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed source probe restores prior package objects and entries."""
        from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
            ImproperlyConfigured,
            get_modules_base_path,
            set_modules_base_path,
        )

        module_name = "_test_sa146_sys_modules_failure"
        package_name = f"quickscale_modules_{module_name}"
        child_name = f"{package_name}.prior"
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_base = get_modules_base_path()
        original_sys_path = sys.path.copy()
        prior_package = ModuleType(package_name)
        prior_child = ModuleType(child_name)
        try:
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.AUTHORITATIVE_MODULE_COUNT",
                1,
            )
            monkeypatch.setattr(
                "quickscale_core.contracts.module_discovery.discover_bundled_module_names",
                lambda: [module_name],
            )
            modules_dir = tmp_path / "modules"
            self._write_embedded_module(
                modules_dir,
                module_name,
                "raise ImportError('broken source context')\n",
            )
            sys.modules[package_name] = prior_package
            sys.modules[child_name] = prior_child
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.add(module_name)
            set_modules_base_path(modules_dir)

            with pytest.raises(ImproperlyConfigured, match="not importable"):
                refresh_managed_adapters()

            assert sys.modules[package_name] is prior_package
            assert sys.modules[child_name] is prior_child
            assert f"{package_name}.adapter" not in sys.modules
            assert sys.path == original_sys_path
        finally:
            self._restore_state(
                original_registry, original_origins, original_base, module_name
            )
            sys.modules.pop(child_name, None)
            sys.path[:] = original_sys_path


# ---------------------------------------------------------------------------
# SA263: analytics' option checks and secret projections belong to the
# manifest boundary.  The former adapter-only nonempty policy is gone; an
# invalid supplied value is refused by the manifest's own declared rules.
# ---------------------------------------------------------------------------


class TestAnalyticsManifestBoundary:
    """Analytics invalid options fail closed at the manifest boundary."""

    def test_empty_provider_is_refused_by_the_choices_rule(self) -> None:
        """An empty QUICKSCALE_ANALYTICS_PROVIDER names its setting path."""
        with pytest.raises(ManifestError) as exc_info:
            build_manifest_wiring_spec("analytics", {"provider": ""})
        message = str(exc_info.value)
        assert "QUICKSCALE_ANALYTICS_PROVIDER" in message
        assert "modules.analytics.provider" in message

    def test_blank_host_is_refused_by_the_pattern_rule(self) -> None:
        """A blank QUICKSCALE_ANALYTICS_POSTHOG_HOST names its setting path."""
        with pytest.raises(ManifestError) as exc_info:
            build_manifest_wiring_spec("analytics", {"posthog_host": ""})
        message = str(exc_info.value)
        assert "QUICKSCALE_ANALYTICS_POSTHOG_HOST" in message
        assert "modules.analytics.posthog_host" in message

    def test_blank_env_var_names_are_accepted_spellings(self) -> None:
        """A blank env-var name is a declared spelling, projected as empty."""
        from quickscale_core.module_wiring import render_settings_modules_py

        spec = build_manifest_wiring_spec("analytics", {"posthog_api_key_env_var": ""})

        assert spec.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR"] == ""
        assert spec.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"] == ""
        content = render_settings_modules_py({"analytics": spec})
        assert 'os.environ.get("", "")' not in content

    def test_disabled_analytics_keeps_apps_and_drops_public_urls(self) -> None:
        """Rule 1 (D3): off keeps the app and settings; only URLs drop."""
        spec = build_manifest_wiring_spec("analytics", {"enabled": False})

        assert spec.apps == ("quickscale_modules_analytics",)
        assert spec.url_includes == ()
        assert spec.settings["QUICKSCALE_ANALYTICS_ENABLED"] is False
        assert spec.settings["QUICKSCALE_ANALYTICS_PROVIDER"] == "posthog"
        assert (
            spec.settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY"]
            == "__QS_ENV__:POSTHOG_API_KEY"
        )


# ---------------------------------------------------------------------------
# CR-SA27-001: Org/Storage custom adapter callers must fail closed on
# invalid options (silent-coercion removal caller-parity gap).
# ---------------------------------------------------------------------------


class TestOrgsStorageAdapterFailClosed:
    """Orgs/storage custom manifest-adapter callers must fail closed on
    invalid options (silent-coercion removal caller-parity gap).

    The generic boundary refuses the supplied option through the
    option-validation engine before resolution, so an invalid option never
    reaches a hook or the assembler (CR-SA27-001)."""

    def test_orgs_invalid_mode_raises_manifest_error(self) -> None:
        """build_manifest_wiring_spec('orgs', {'mode': 'invalid'})
        raises ManifestError naming the manifest setting path."""
        from quickscale_core.manifest import ManifestError

        with pytest.raises(ManifestError) as exc_info:
            build_manifest_wiring_spec("orgs", {"mode": "invalid_mode"})
        msg = str(exc_info.value)
        assert "modules.orgs.mode" in msg
        assert "must be one of" in msg

    def test_storage_invalid_backend_raises_manifest_error(self) -> None:
        """build_manifest_wiring_spec('storage', {'backend': 'invalid'})
        raises ManifestError naming the manifest setting path."""
        from quickscale_core.manifest import ManifestError

        with pytest.raises(ManifestError) as exc_info:
            build_manifest_wiring_spec("storage", {"backend": "invalid_backend"})
        msg = str(exc_info.value)
        assert "modules.storage.backend" in msg
        assert "must be one of" in msg

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
# SA263: module settings boundaries are manifest-owned.  The generic boundary
# refuses wrong-shaped supplied values before any hook or rendering; the
# hooks consume canonical values and contribute only composite settings.
# ---------------------------------------------------------------------------


class TestBlogManifestBoundary:
    """Blog invalid options fail closed at the manifest boundary."""

    @pytest.mark.parametrize(
        "supplied",
        [
            {"posts_per_page": "10"},
            {"api_rate_limit": ""},
            {"api_rate_limit": "   "},
            {"rss_enabled": 1},
        ],
    )
    def test_wrong_shaped_options_are_refused(self, supplied: dict[str, Any]) -> None:
        with pytest.raises(ManifestError, match="modules.blog."):
            build_manifest_wiring_spec("blog", dict(supplied))

    def test_valid_options_flow_to_canonical_settings(self) -> None:
        spec = build_manifest_wiring_spec("blog", {"posts_per_page": 10})

        assert spec.settings["QUICKSCALE_BLOG_POSTS_PER_PAGE"] == 10
        assert spec.settings["QUICKSCALE_BLOG_RSS_ENABLED"] is True
        assert spec.settings["QUICKSCALE_BLOG_API_RATE_LIMIT"] == "5/hour"
        assert spec.settings["REST_FRAMEWORK"] == {
            "DEFAULT_THROTTLE_RATES": {"quickscale_blog_api": "5/hour"}
        }


class TestListingsManifestBoundary:
    """Listings invalid options fail closed at the manifest boundary."""

    @pytest.mark.parametrize(
        "supplied",
        [
            {"per_page": "24"},
            {"api_rate_limit": ""},
        ],
    )
    def test_wrong_shaped_options_are_refused(self, supplied: dict[str, Any]) -> None:
        with pytest.raises(ManifestError, match="modules.listings."):
            build_manifest_wiring_spec("listings", dict(supplied))

    def test_valid_options_flow_to_canonical_settings(self) -> None:
        spec = build_manifest_wiring_spec("listings", {"per_page": 24})

        assert spec.settings["QUICKSCALE_LISTINGS_PER_PAGE"] == 24
        assert spec.settings["REST_FRAMEWORK"] == {
            "DEFAULT_THROTTLE_RATES": {"quickscale_listings_api": "5/hour"}
        }


class TestFormsManifestBoundary:
    """Forms invalid options fail closed at the manifest boundary."""

    @pytest.mark.parametrize(
        "supplied",
        [
            {"submissions_per_page": "25"},
            {"per_page": True},
            {"rate_limit": ""},
            {"retention_days": -1},
        ],
    )
    def test_wrong_shaped_options_are_refused(self, supplied: dict[str, Any]) -> None:
        with pytest.raises(ManifestError, match="modules.forms."):
            build_manifest_wiring_spec("forms", dict(supplied))

    def test_valid_options_flow_to_canonical_settings(self) -> None:
        spec = build_manifest_wiring_spec("forms", {"submissions_per_page": 25})

        assert spec.settings["QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE"] == 25
        assert spec.settings["REST_FRAMEWORK"] == {
            "DEFAULT_THROTTLE_RATES": {"quickscale_forms_submit": "5/hour"}
        }


_SA167A_MANIFEST_APPS: dict[str, tuple[str, ...]] = {
    "auth": (
        "django.contrib.sites",
        "quickscale_modules_auth",
        "allauth",
        "allauth.account",
    ),
    "backups": ("quickscale_modules_backups",),
    "notifications": (
        "anymail",
        "rest_framework",
        "quickscale_modules_notifications",
    ),
    "orgs": ("rest_framework", "quickscale_modules_orgs"),
    "storage": ("quickscale_modules_storage",),
}


class _SA167aAppLiteralVisitor(ast.NodeVisitor):
    """Collect migrated app literals from executable AST nodes.

    This deliberately does not model only one constructor or keyword shape.
    An exact app member is an ownership violation whether it appears in a
    ``WiringProjection``, a helper return, a local variable, or another
    ``apps=`` consumer.  Module/function/class docstrings are skipped because
    prose is not executable wiring.
    """

    def __init__(self, app_literals: frozenset[str]) -> None:
        self.app_literals = app_literals
        self.matches: list[tuple[int, str]] = []

    @staticmethod
    def _is_docstring(node: ast.stmt) -> bool:
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )

    def _visit_body(self, body: list[ast.stmt]) -> None:
        for index, statement in enumerate(body):
            if index == 0 and self._is_docstring(statement):
                continue
            self.visit(statement)

    def _visit_function_signature(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.visit(node.args)
        if node.returns is not None:
            self.visit(node.returns)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)

    def visit_Module(self, node: ast.Module) -> None:
        self._visit_body(node.body)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_signature(node)
        self._visit_body(node.body)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_signature(node)
        self._visit_body(node.body)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword)
        for type_parameter in getattr(node, "type_params", ()):
            self.visit(type_parameter)
        self._visit_body(node.body)

    @classmethod
    def _static_string(cls, node: ast.expr) -> str | None:
        """Resolve a string assembled entirely from literals, if possible."""
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = cls._static_string(node.left)
            right = cls._static_string(node.right)
            if left is not None and right is not None:
                return left + right
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                    continue
                if (
                    isinstance(value, ast.FormattedValue)
                    and isinstance(value.value, ast.Constant)
                    and isinstance(value.value.value, str)
                ):
                    parts.append(value.value.value)
                    continue
                return None
            return "".join(parts)
        return None

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and node.value in self.app_literals:
            self.matches.append((node.lineno, node.value))

    def visit_BinOp(self, node: ast.BinOp) -> None:
        value = self._static_string(node)
        if value in self.app_literals:
            self.matches.append((node.lineno, value))
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        value = self._static_string(node)
        if value in self.app_literals:
            self.matches.append((node.lineno, value))
        self.generic_visit(node)


def _find_sa167a_app_literals(source: str) -> list[tuple[int, str]]:
    """Return every executable exact app member owned by SA167a manifests."""
    tree = ast.parse(source)
    app_literals = frozenset(
        app for apps in _SA167A_MANIFEST_APPS.values() for app in apps
    )
    visitor = _SA167aAppLiteralVisitor(app_literals)
    visitor.visit(tree)
    return visitor.matches


def _assert_no_sa167a_app_literals(source: str) -> None:
    """Assert that core source cannot reintroduce a migrated app literal."""
    matches = _find_sa167a_app_literals(source)
    assert not matches, f"SA167a app literals remain in entry_point.py: {matches}"


class TestSA167aManifestOwnedApps:
    """SA167a pins manifest ownership without changing resolved app wiring."""

    @pytest.mark.parametrize("module_name", sorted(_SA167A_MANIFEST_APPS))
    def test_manifest_declares_exact_app_projection(self, module_name: str) -> None:
        """Each migrated module has one complete static apps projection."""
        manifest = load_module_manifest(module_name)
        projections = [
            projection
            for projection in manifest.wiring_projections
            if projection.get("wiring_field") == "apps"
        ]

        assert len(projections) == 1
        projection = projections[0]
        assert projection.get("derivation_type") == "static"
        expression = projection.get("expression")
        assert isinstance(expression, dict)
        assert expression.get("value") == list(_SA167A_MANIFEST_APPS[module_name])

    def test_entry_point_has_no_core_owned_app_literals(self) -> None:
        """Core adapters consume manifest app projections rather than literals.

        The ownership invariant is intentionally stronger than checking only
        ``WiringProjection`` constructors.  A helper return, a local tuple, or
        a direct ``ResolverResult(apps=...)`` would still make core the owner.
        """
        source = Path(inspect.getfile(entry_point_module)).read_text()
        _assert_no_sa167a_app_literals(source)

    def test_non_wiring_projection_literal_is_an_expected_red_canary(self) -> None:
        """A realistic helper/variable/ModuleWiringSpec form fails closed."""
        source = Path(inspect.getfile(entry_point_module)).read_text()
        canary_source = (
            source
            + """

def _sa167a_expected_red_canary() -> ModuleWiringSpec:
    core_owned_apps = ("quickscale_modules_" + "auth",)

    def _apps_from_helper() -> tuple[str, ...]:
        return core_owned_apps

    return ModuleWiringSpec(apps=_apps_from_helper())
"""
        )
        with pytest.raises(AssertionError, match="SA167a app literals"):
            _assert_no_sa167a_app_literals(canary_source)

    @pytest.mark.parametrize(
        "source",
        [
            'def build(app="quickscale_modules_auth"):\n    return app\n',
            '@register("quickscale_modules_auth")\ndef build():\n    pass\n',
            'def build(app: Literal["quickscale_modules_auth"]):\n    pass\n',
            'class Build(registry["quickscale_modules_auth"]):\n    pass\n',
            'class Build(metaclass=resolve("quickscale_modules_auth")):\n    pass\n',
        ],
    )
    def test_semantic_ownership_guard_checks_non_body_expressions(
        self, source: str
    ) -> None:
        """Signature and class-header literals are executable ownership too."""
        matches = _find_sa167a_app_literals(source)

        assert len(matches) == 1
        assert matches[0][1] == "quickscale_modules_auth"


_EXPECTED_CATALOG_APPS: dict[str, tuple[str, ...]] = {
    "analytics": ("quickscale_modules_analytics",),
    "auth": _SA167A_MANIFEST_APPS["auth"],
    "backups": _SA167A_MANIFEST_APPS["backups"],
    "billing": ("rest_framework", "quickscale_modules_billing"),
    "blog": ("rest_framework", "markdownx", "quickscale_modules_blog"),
    "crm": ("rest_framework", "django_filters", "quickscale_modules_crm"),
    "forms": ("rest_framework", "django_filters", "quickscale_modules_forms"),
    "listings": (
        "rest_framework",
        "django_filters",
        "markdownx",
        "quickscale_modules_listings",
    ),
    "notifications": _SA167A_MANIFEST_APPS["notifications"],
    "orgs": _SA167A_MANIFEST_APPS["orgs"],
    "social": ("quickscale_modules_social",),
    "storage": _SA167A_MANIFEST_APPS["storage"],
}


@pytest.mark.parametrize("module_name", sorted(_EXPECTED_CATALOG_APPS))
def test_sa167a_all_catalog_app_resolution_is_byte_identical(module_name: str) -> None:
    """All twelve resolved app tuples remain the established contract."""
    spec = build_manifest_wiring_spec(module_name, {}, project_package="myapp")
    assert spec.apps == _EXPECTED_CATALOG_APPS[module_name]


class TestSA167bRelocationParity:
    """The module-owned auth sentinel remains identical to the core oracle."""

    @staticmethod
    def _invoke(adapter: Any, options: dict[str, Any]) -> tuple[str, Any]:
        try:
            return ("result", adapter(options))
        except Exception as exc:  # noqa: BLE001 - parity includes exact errors.
            return ("error", (type(exc), str(exc)))

    def test_auth_module_adapter_matches_core(self) -> None:
        """Registry refresh selects the auth module's public sentinel exactly."""
        core_adapter = MANIFEST_ADAPTER_REGISTRY["auth"]
        module_adapter = get_auth_manifest_adapter()
        assert inspect.getsourcefile(core_adapter) == inspect.getsourcefile(
            module_adapter
        )
        matrix = [
            {},
            {"authentication_method": "email"},
            {"authentication_method": "username"},
            {"authentication_method": "both"},
            {
                "authentication_method": "both",
                "registration_enabled": False,
                "email_verification": "mandatory",
                "session_cookie_age": 3600,
            },
            {"allow_registration": False},
            {"social_providers": ["google"]},
        ]

        for options in matrix:
            old_kind, old_value = self._invoke(core_adapter, dict(options))
            new_kind, new_value = self._invoke(module_adapter, dict(options))
            assert new_kind == old_kind, options
            if old_kind == "result":
                assert new_value == old_value, options
            else:
                assert new_value == old_value, options

        # Repeated calls exercise state independence in both implementations.
        repeated_options = (
            {"authentication_method": "username"},
            {},
            {"authentication_method": "both"},
        )
        for options in repeated_options:
            old_kind, old_value = self._invoke(core_adapter, dict(options))
            new_kind, new_value = self._invoke(module_adapter, dict(options))
            assert (new_kind, new_value) == (old_kind, old_value), options

    def test_orgs_module_adapter_matches_core(self) -> None:
        """Registry refresh selects the orgs module's public sentinel exactly."""
        core_adapter = MANIFEST_ADAPTER_REGISTRY["orgs"]
        module_adapter = get_orgs_manifest_adapter()
        assert inspect.getsourcefile(core_adapter) == inspect.getsourcefile(
            module_adapter
        )
        matrix = [
            {},
            {"mode": "solo"},
            {"mode": " SOLO "},
            {"mode": "saas"},
            {"mode": " SaaS "},
            {"mode": "invalid"},
            {"mode": ""},
        ]

        for options in matrix:
            old_kind, old_value = self._invoke(core_adapter, dict(options))
            new_kind, new_value = self._invoke(module_adapter, dict(options))
            assert new_kind == old_kind, options
            assert new_value == old_value, options

        repeated_options = (
            {"mode": "saas"},
            {},
            {"mode": "solo"},
            {"mode": "SAAS"},
        )
        for options in repeated_options:
            old_kind, old_value = self._invoke(core_adapter, dict(options))
            new_kind, new_value = self._invoke(module_adapter, dict(options))
            assert (new_kind, new_value) == (old_kind, old_value), options

    def test_storage_module_adapter_matches_core(self) -> None:
        """Registry refresh selects the storage module's public sentinel exactly."""
        core_adapter = MANIFEST_ADAPTER_REGISTRY["storage"]
        module_adapter = get_storage_manifest_adapter()
        assert inspect.getsourcefile(core_adapter) == inspect.getsourcefile(
            module_adapter
        )
        matrix = [
            {},
            {"backend": "local"},
            {"backend": "s3", "bucket_name": "bucket", "region_name": "us-east-1"},
            {
                "backend": "r2",
                "bucket_name": "bucket",
                "endpoint_url": "https://account.r2.cloudflarestorage.com",
                "region_name": "auto",
                "private_media_enabled": True,
            },
            {
                "backend": "s3",
                "bucket_name": "bucket",
                "access_key_id_env_var": "CUSTOM_ACCESS",
                "secret_access_key_env_var": "CUSTOM_SECRET",
                "querystring_auth": True,
            },
            {
                "backend": "s3",
                "media_url": " /uploads ",
                "public_base_url": " https://cdn.example.com/ ",
                "bucket_name": " ",
                "endpoint_url": " ",
                "region_name": " ",
                "default_acl": " ",
            },
            {"backend": "invalid"},
            {"backend": "s3", "access_key_id_env_var": "AKIA1234567890123456"},
            {"backend": "s3", "secret_access_key_env_var": "literal-secret"},
            {
                "backend": "s3",
                "access_key_id": "AKIA1234567890123456",
                "secret_access_key": "literal-secret",
            },
        ]

        for options in matrix:
            old_kind, old_value = self._invoke(core_adapter, dict(options))
            new_kind, new_value = self._invoke(module_adapter, dict(options))
            assert (new_kind, new_value) == (old_kind, old_value), options

        repeated_options = (
            {"backend": "s3", "bucket_name": "s3-bucket"},
            {},
            {"backend": "r2", "bucket_name": "r2-bucket", "endpoint_url": "https://r2"},
            {"backend": "local"},
        )
        for options in repeated_options:
            old_kind, old_value = self._invoke(core_adapter, dict(options))
            new_kind, new_value = self._invoke(module_adapter, dict(options))
            assert (new_kind, new_value) == (old_kind, old_value), options


# ---------------------------------------------------------------------------
# SA263: the generic boundary validates supplied options before resolution,
# projection, or any post-resolution hook.
# ---------------------------------------------------------------------------


def _boundary_manifest() -> ModuleManifest:
    """Build a synthetic hook-free manifest covering the validation vocabulary."""
    return ModuleManifest(
        name="demo",
        version="1.0.0",
        mutable_options={
            "mode": ConfigOption(
                name="mode",
                option_type="string",
                default="basic",
                django_setting="DEMO_MODE",
                mutability="mutable",
                validation={"choices": ["basic", "full"]},
            ),
            "attempts": ConfigOption(
                name="attempts",
                option_type="integer",
                default=3,
                django_setting="DEMO_ATTEMPTS",
                mutability="mutable",
                validation={"min": 1, "max": 10},
            ),
            "endpoint": ConfigOption(
                name="endpoint",
                option_type="string",
                default="",
                django_setting="DEMO_ENDPOINT",
                mutability="mutable",
                validation={"pattern": r"^(?:https?://.*)?$"},
            ),
            "feature_enabled": ConfigOption(
                name="feature_enabled",
                option_type="boolean",
                default=False,
                django_setting="DEMO_FEATURE_ENABLED",
                mutability="mutable",
                validation={},
            ),
            "tags": ConfigOption(
                name="tags",
                option_type="list",
                default=[],
                django_setting="DEMO_TAGS",
                mutability="mutable",
                validation={},
            ),
            "api_token": ConfigOption(
                name="api_token",
                option_type="string",
                default="",
                django_setting="DEMO_API_TOKEN",
                mutability="mutable",
                validation={"required_when": {"mode": "full"}},
            ),
        },
        retired_options={
            "legacy_mode": "Legacy key 'legacy_mode' is no longer supported."
        },
        option_derivations={
            "feature_enabled": {
                "normalization_rules": [
                    {
                        "source_key": "feature_enabled",
                        "target_key": "feature_enabled",
                        "rule_type": "coerce_bool",
                    },
                ],
            },
            "tags": {
                "normalization_rules": [
                    {
                        "source_key": "tags",
                        "target_key": "tags",
                        "rule_type": "list",
                        "item_rules": [
                            {
                                "source_key": "tags",
                                "target_key": "tags",
                                "rule_type": "strip",
                            },
                        ],
                    },
                ],
            },
        },
    )


class _HookSpy:
    """A post-resolution hook that records its invocations."""

    def __init__(self) -> None:
        self.calls: list[tuple[ModuleWiringSpec, dict[str, Any]]] = []

    def __call__(
        self, spec: ModuleWiringSpec, resolved: dict[str, Any]
    ) -> ModuleWiringSpec:
        self.calls.append((spec, dict(resolved)))
        return spec


class TestGenericManifestBoundary:
    """Supplied options are checked before resolution and before hooks."""

    @pytest.fixture()
    def manifest(self, monkeypatch: pytest.MonkeyPatch) -> ModuleManifest:
        manifest = _boundary_manifest()
        monkeypatch.setattr(
            entry_point_module, "load_module_manifest", lambda _name: manifest
        )
        return manifest

    def _assert_refused(
        self,
        manifest: ModuleManifest,
        supplied: dict[str, Any],
    ) -> None:
        """Assert the boundary refuses *supplied* with the engine's own message."""
        spy = _HookSpy()
        expected = validate_module_options(manifest, dict(supplied))[0]
        with pytest.raises(ManifestError) as exc_info:
            build_generic_manifest_spec("demo", dict(supplied), post_hook=spy)
        assert str(exc_info.value) == f"[demo] {expected}"
        assert spy.calls == []

    @pytest.mark.parametrize(
        ("label", "supplied"),
        [
            ("choices", {"mode": "unknown"}),
            ("range", {"attempts": 99}),
            ("pattern", {"endpoint": "ftp://example.com"}),
            ("cross_option", {"mode": "full"}),
            ("retired_key", {"legacy_mode": "basic"}),
            ("raw_none", {"mode": None}),
            ("raw_container", {"mode": ["basic"]}),
            ("raw_mapping", {"attempts": {"min": 1}}),
            ("integer_bool", {"attempts": True}),
            ("boolean_integer", {"feature_enabled": 1}),
            ("unauthorized_string_spelling", {"attempts": "3"}),
        ],
    )
    def test_invalid_supplied_options_refuse_before_the_hook(
        self,
        manifest: ModuleManifest,
        label: str,
        supplied: dict[str, Any],
    ) -> None:
        self._assert_refused(manifest, supplied)

    def test_retired_key_keeps_precedence_over_other_issues(
        self, manifest: ModuleManifest
    ) -> None:
        spy = _HookSpy()
        with pytest.raises(ManifestError) as exc_info:
            build_generic_manifest_spec(
                "demo", {"legacy_mode": "basic", "mode": "unknown"}, post_hook=spy
            )
        assert "legacy_mode" in str(exc_info.value)
        assert spy.calls == []

    def test_declared_rule_converts_a_string_spelling_for_the_hook(
        self, manifest: ModuleManifest
    ) -> None:
        """Only a declared rule converts; the hook consumes canonical types."""
        spy = _HookSpy()
        spec = build_generic_manifest_spec(
            "demo",
            {"feature_enabled": "true", "tags": "a, b"},
            post_hook=spy,
        )

        assert len(spy.calls) == 1
        _, resolved = spy.calls[0]
        assert resolved["feature_enabled"] is True
        assert resolved["tags"] == ["a", "b"]
        assert spec.settings["DEMO_FEATURE_ENABLED"] is True
        assert spec.settings["DEMO_TAGS"] == ["a", "b"]

    def test_valid_defaults_assemble_without_a_hook(
        self, manifest: ModuleManifest
    ) -> None:
        spec = build_generic_manifest_spec("demo", {})
        assert isinstance(spec, ModuleWiringSpec)
        assert spec.settings["DEMO_MODE"] == "basic"


def _secrets_manifest() -> ModuleManifest:
    """Build a synthetic manifest with a suffix-stripped secret projection."""
    return ModuleManifest(
        name="secrets_demo",
        version="1.0.0",
        mutable_options={
            "token_env_var": ConfigOption(
                name="token_env_var",
                option_type="string",
                default="",
                django_setting="SECRETS_DEMO_TOKEN_ENV_VAR",
                mutability="mutable",
                validation={"pattern": r"^(?:[A-Z][A-Z0-9_]*)?$"},
            ),
        },
        option_derivations={
            "token_env_var": {
                "normalization_rules": [
                    {
                        "source_key": "token_env_var",
                        "target_key": "token_env_var",
                        "rule_type": "strip",
                    },
                ],
                "derived_settings": [
                    {
                        "setting_key": "SECRETS_DEMO_TOKEN",
                        "source_options": ["token_env_var"],
                        "derivation_type": "computed",
                        "expression": {"template": "__QS_ENV__:{token_env_var}"},
                        "description": "Deferred secret reference",
                    },
                ],
            },
        },
    )


class TestGenericBoundarySecrets:
    """The generic boundary projects deferred secret references, never values."""

    @pytest.fixture()
    def manifest(self, monkeypatch: pytest.MonkeyPatch) -> ModuleManifest:
        manifest = _secrets_manifest()
        monkeypatch.setattr(
            entry_point_module, "load_module_manifest", lambda _name: manifest
        )
        return manifest

    def test_nonblank_env_name_projects_the_deferred_reference(
        self, manifest: ModuleManifest
    ) -> None:
        spec = build_generic_manifest_spec(
            "secrets_demo", {"token_env_var": "DEMO_TOKEN"}
        )
        assert spec.settings["SECRETS_DEMO_TOKEN_ENV_VAR"] == "DEMO_TOKEN"
        assert spec.settings["SECRETS_DEMO_TOKEN"] == "__QS_ENV__:DEMO_TOKEN"

        content = render_settings_modules_py({"secrets_demo": spec})
        assert 'os.environ.get("DEMO_TOKEN", "")' in content

    def test_blank_env_name_renders_literal_empty_without_reading(
        self, manifest: ModuleManifest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEMO_TOKEN", "super-secret-value")
        spec = build_generic_manifest_spec("secrets_demo", {"token_env_var": "   "})

        content = render_settings_modules_py({"secrets_demo": spec})

        assert "super-secret-value" not in content
        assert 'os.environ.get("", "")' not in content
        assert "'SECRETS_DEMO_TOKEN': ''" in content

    def test_invalid_env_name_is_refused_before_the_hook(
        self, manifest: ModuleManifest
    ) -> None:
        spy = _HookSpy()
        with pytest.raises(ManifestError) as exc_info:
            build_generic_manifest_spec(
                "secrets_demo", {"token_env_var": "bad-name'"}, post_hook=spy
            )
        assert "SECRETS_DEMO_TOKEN_ENV_VAR" in str(exc_info.value)
        assert spy.calls == []


def _mapped_secrets_manifest() -> ModuleManifest:
    """Build a manifest whose secret setting comes only from the mapping.

    The manifest declares no explicit ``derived_settings`` entry, so the
    suffix-stripped secret setting can only come from the generic boundary's
    own projection over the mapped ``_ENV_VAR`` option.
    """
    return ModuleManifest(
        name="mapped_secrets_demo",
        version="1.0.0",
        mutable_options={
            "token_env_var": ConfigOption(
                name="token_env_var",
                option_type="string",
                default="",
                django_setting="MAPPED_SECRETS_DEMO_TOKEN_ENV_VAR",
                mutability="mutable",
                validation={"pattern": r"^(?:[A-Z][A-Z0-9_]*)?$"},
            ),
        },
        option_derivations={
            "token_env_var": {
                "normalization_rules": [
                    {
                        "source_key": "token_env_var",
                        "target_key": "token_env_var",
                        "rule_type": "strip",
                    },
                ],
            },
        },
    )


class TestGenericMappedEnvVarSecretProjection:
    """Every mapped ``_ENV_VAR`` option projects its suffix-stripped secret."""

    @pytest.fixture()
    def manifest(self, monkeypatch: pytest.MonkeyPatch) -> ModuleManifest:
        manifest = _mapped_secrets_manifest()
        monkeypatch.setattr(
            entry_point_module, "load_module_manifest", lambda _name: manifest
        )
        return manifest

    def test_nonblank_name_projects_the_suffix_stripped_setting(
        self, manifest: ModuleManifest
    ) -> None:
        spec = build_generic_manifest_spec(
            "mapped_secrets_demo", {"token_env_var": "DEMO_TOKEN"}
        )

        # The env-name setting is retained and the secret setting is added by
        # the generic projection with no explicit manifest declaration.
        assert spec.settings["MAPPED_SECRETS_DEMO_TOKEN_ENV_VAR"] == "DEMO_TOKEN"
        assert spec.settings["MAPPED_SECRETS_DEMO_TOKEN"] == "__QS_ENV__:DEMO_TOKEN"

        content = render_settings_modules_py({"mapped_secrets_demo": spec})
        assert 'os.environ.get("DEMO_TOKEN", "")' in content

    def test_hook_receives_the_full_projected_setting_map(
        self, manifest: ModuleManifest
    ) -> None:
        """Secrets project before hooks: the hook sees the complete setting map."""
        spy = _HookSpy()
        spec = build_generic_manifest_spec(
            "mapped_secrets_demo", {"token_env_var": "DEMO_TOKEN"}, post_hook=spy
        )

        assert len(spy.calls) == 1
        hook_spec, _ = spy.calls[0]
        assert hook_spec.settings["MAPPED_SECRETS_DEMO_TOKEN_ENV_VAR"] == "DEMO_TOKEN"
        assert (
            hook_spec.settings["MAPPED_SECRETS_DEMO_TOKEN"] == "__QS_ENV__:DEMO_TOKEN"
        )
        assert spec.settings["MAPPED_SECRETS_DEMO_TOKEN"] == "__QS_ENV__:DEMO_TOKEN"

    def test_blank_name_projects_literal_empty_without_reading(
        self, manifest: ModuleManifest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEMO_TOKEN", "super-secret-value")
        spec = build_generic_manifest_spec(
            "mapped_secrets_demo", {"token_env_var": "   "}
        )

        assert spec.settings["MAPPED_SECRETS_DEMO_TOKEN_ENV_VAR"] == ""
        assert spec.settings["MAPPED_SECRETS_DEMO_TOKEN"] == ""

        content = render_settings_modules_py({"mapped_secrets_demo": spec})
        assert "super-secret-value" not in content
        assert 'os.environ.get("", "")' not in content
        assert "'MAPPED_SECRETS_DEMO_TOKEN': ''" in content

    def test_blank_default_name_projects_literal_empty(
        self, manifest: ModuleManifest
    ) -> None:
        spec = build_generic_manifest_spec("mapped_secrets_demo", {})
        assert spec.settings["MAPPED_SECRETS_DEMO_TOKEN_ENV_VAR"] == ""
        assert spec.settings["MAPPED_SECRETS_DEMO_TOKEN"] == ""

    def test_resolution_never_reads_the_environment(
        self, manifest: ModuleManifest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEMO_TOKEN", "super-secret-value")
        spec = build_generic_manifest_spec(
            "mapped_secrets_demo", {"token_env_var": "DEMO_TOKEN"}
        )
        for value in spec.settings.values():
            assert "super-secret-value" not in str(value)


def _colliding_secrets_manifest() -> ModuleManifest:
    """Build a manifest whose ``_ENV_VAR`` suffix collides with a mapping."""
    return ModuleManifest(
        name="colliding_secrets_demo",
        version="1.0.0",
        mutable_options={
            "host": ConfigOption(
                name="host",
                option_type="string",
                default="https://fallback.example",
                django_setting="COLLIDING_SECRETS_DEMO_HOST",
                mutability="mutable",
                validation={},
            ),
            "host_env_var": ConfigOption(
                name="host_env_var",
                option_type="string",
                default="DEMO_HOST",
                django_setting="COLLIDING_SECRETS_DEMO_HOST_ENV_VAR",
                mutability="mutable",
                validation={"pattern": r"^(?:[A-Z][A-Z0-9_]*)?$"},
            ),
        },
    )


class TestGenericMappedEnvVarSecretCollision:
    """An explicit direct mapping wins over the generic suffix projection."""

    @pytest.fixture()
    def manifest(self, monkeypatch: pytest.MonkeyPatch) -> ModuleManifest:
        manifest = _colliding_secrets_manifest()
        monkeypatch.setattr(
            entry_point_module, "load_module_manifest", lambda _name: manifest
        )
        return manifest

    def test_a_claimed_setting_name_is_not_replaced_by_the_projection(
        self, manifest: ModuleManifest
    ) -> None:
        """The fallback setting keeps its value; the env-name setting stays."""
        spec = build_generic_manifest_spec("colliding_secrets_demo", {})

        assert spec.settings["COLLIDING_SECRETS_DEMO_HOST"] == (
            "https://fallback.example"
        )
        assert spec.settings["COLLIDING_SECRETS_DEMO_HOST_ENV_VAR"] == "DEMO_HOST"


# ---------------------------------------------------------------------------
# SA282: the contract-vintage id requirement is scoped by resolution
# provenance — authored sources refuse a missing id, a caller-supplied
# embedded base tolerates a historical copy.
# ---------------------------------------------------------------------------


class TestLoadModuleManifestVintageIdProvenance:
    """The vintage-id opt-out is scoped to caller-supplied bases."""

    @staticmethod
    def _write_id_less_manifest(base: Path, module: str) -> None:
        """Write a pre-id vintage manifest at ``base/<module>/module.yml``."""
        module_dir = base / module
        module_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text(
            f"name: {module}\n"
            "version: '0.1.0'\n"
            "contract_vintage:\n"
            "  minimum: '0.87.0'\n"
            "  manual_adoption_steps:\n"
            "    - 'Adopt the tooling'\n"
        )

    def test_authored_monorepo_base_refuses_an_id_less_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A monorepo (authored) read refuses a vintage without an id."""
        from quickscale_core.contracts.module_discovery import ModuleResolutionSource

        base = tmp_path / "modules"
        self._write_id_less_manifest(base, "_test_authored_vintage_mod")
        monkeypatch.setattr(entry_point_module, "get_modules_base_path", lambda: base)
        monkeypatch.setattr(
            entry_point_module,
            "get_resolution_source",
            lambda: ModuleResolutionSource.MONOREPO,
        )

        with pytest.raises(ManifestError, match="contract_vintage.id"):
            load_module_manifest("_test_authored_vintage_mod")

    def test_bundled_base_refuses_an_id_less_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bundled (authored) read refuses a vintage without an id."""
        from quickscale_core.contracts.module_discovery import ModuleResolutionSource

        base = tmp_path / "manifests"
        self._write_id_less_manifest(base, "_test_bundled_vintage_mod")
        monkeypatch.setattr(entry_point_module, "get_modules_base_path", lambda: base)
        monkeypatch.setattr(
            entry_point_module,
            "get_resolution_source",
            lambda: ModuleResolutionSource.BUNDLED,
        )

        with pytest.raises(ManifestError, match="contract_vintage.id"):
            load_module_manifest("_test_bundled_vintage_mod")

    def test_override_base_tolerates_a_pre_id_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A caller-supplied base reads a historical embedded copy."""
        from quickscale_core.contracts.module_discovery import ModuleResolutionSource

        base = tmp_path / "project" / "modules"
        self._write_id_less_manifest(base, "_test_embedded_vintage_mod")
        monkeypatch.setattr(entry_point_module, "get_modules_base_path", lambda: base)
        monkeypatch.setattr(
            entry_point_module,
            "get_resolution_source",
            lambda: ModuleResolutionSource.OVERRIDE,
        )

        manifest = load_module_manifest("_test_embedded_vintage_mod")

        assert manifest.contract_vintage is not None
        assert manifest.contract_vintage.id is None
        assert manifest.contract_vintage.minimum == "0.87.0"

    def test_override_seam_marks_the_base_as_historical(self, tmp_path: Path) -> None:
        """The public override is the explicit historical-base signal."""
        from quickscale_core.contracts import module_discovery
        from quickscale_core.contracts.module_discovery import (
            ModuleResolutionSource,
            get_resolution_source,
            set_modules_base_path,
        )

        base = tmp_path / "modules"
        self._write_id_less_manifest(base, "_test_seam_vintage_mod")
        original_override = module_discovery._modules_base_path
        try:
            set_modules_base_path(base)

            assert get_resolution_source() is ModuleResolutionSource.OVERRIDE
            manifest = load_module_manifest("_test_seam_vintage_mod")
            assert manifest.contract_vintage is not None
            assert manifest.contract_vintage.id is None
        finally:
            module_discovery._modules_base_path = original_override
