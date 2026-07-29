"""Phase 3 regression tests for the manifest-path regeneration switch.

Verifies that ``regenerate_managed_wiring`` now routes through the manifest
adapter registry (``build_manifest_wiring_spec``) while preserving the
legacy skip-unknown behaviour for discovered/forwarded module names that
have no registered adapter.

These tests complement the existing apply/remove/module-config tests that
exercise the manager indirectly through CLI commands.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from unittest.mock import patch

from quickscale_cli.utils.module_wiring_manager import regenerate_managed_wiring
from quickscale_core.manifest.entry_point import MANIFEST_ADAPTER_REGISTRY


def _write_minimal_project(
    project_path: Path,
    *,
    package_name: str = "myapp",
    modules: dict[str, dict] | None = None,
) -> None:
    """Create a minimal project layout sufficient for regenerate_managed_wiring."""
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / package_name).mkdir(exist_ok=True)
    (project_path / package_name / "settings").mkdir(exist_ok=True)
    (project_path / package_name / "settings" / "__init__.py").write_text("")

    config_payload = {
        "version": "1",
        "project": {
            "slug": package_name,
            "package": package_name,
            "theme": "showcase_react",
        },
        "docker": {"start": False},
        "modules": modules or {},
    }
    (project_path / "quickscale.yml").write_text(
        yaml.safe_dump(config_payload, sort_keys=False, default_flow_style=False)
    )


class TestRegenerateManagedWiringManifestPath:
    """Phase 3: regeneration routes through the manifest adapter registry."""

    def test_known_module_routes_through_manifest(self, tmp_path: Path) -> None:
        """A registered module (analytics) should be built via the manifest path."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        success, message = regenerate_managed_wiring(
            project, module_names=["analytics"]
        )
        assert success, f"regenerate_managed_wiring failed: {message}"

        settings_modules = project / "myapp" / "settings" / "modules.py"
        assert settings_modules.exists()
        content = settings_modules.read_text()
        assert "quickscale_modules_analytics" in content

    def test_social_module_produces_managed_files(self, tmp_path: Path) -> None:
        """Social module should produce managed quickscale_managed/ files via manifest."""
        project = tmp_path / "myapp"
        _write_minimal_project(
            project,
            modules={
                "social": {
                    "provider_allowlist": ["Twitter", "YouTube"],
                    "layout_variant": "list",
                }
            },
        )

        success, message = regenerate_managed_wiring(project, module_names=["social"])
        assert success, f"regenerate_managed_wiring failed: {message}"

        managed_init = project / "myapp" / "quickscale_managed" / "__init__.py"
        managed_urls = project / "myapp" / "quickscale_managed" / "social_urls.py"
        managed_views = project / "myapp" / "quickscale_managed" / "social_views.py"
        assert managed_init.exists(), "Managed __init__.py not written"
        assert managed_urls.exists(), "Managed social_urls.py not written"
        assert managed_views.exists(), "Managed social_views.py not written"

        views_content = managed_views.read_text()
        # The resolver normalises "Twitter" -> "x"; check for either form.
        assert "x" in views_content or "youtube" in views_content.lower()

        # SA13.1 regeneration evidence (CR-SA13.1-003): verify the generated
        # views use org_scope and avoid tenant_context/manual transaction
        # patterns — this confirms the template change propagates through the
        # full regenerate_managed_wiring pipeline to the on-disk file.
        assert "org_scope(resolved_org)" in views_content, (
            "Generated social_views.py must use org_scope() for unified "
            "tenant-context activation (SA13.1)."
        )
        assert (
            "from quickscale_modules_orgs.current_org import get_current_org, org_scope"
            in views_content
        )
        assert "get_system_org()" in views_content, (
            "Generated views must resolve System org for anonymous requests per D2."
        )
        assert "build_social_link_tree_payload()" in views_content
        assert "build_social_embeds_payload()" in views_content
        # Explicit transaction.atomic() and tenant_context must be absent
        # because org_scope() wraps atomic internally.
        assert "from django.db import transaction" not in views_content, (
            "org_scope() wraps transaction.atomic() internally."
        )
        assert "tenant_context" not in views_content, (
            "org_scope() is the unified replacement for tenant_context."
        )
        # organization_id kwarg was removed in T1.9
        assert "organization_id" not in views_content
        # No manual ContextVar management remains
        assert "set_current_org_id" not in views_content
        assert "set_db_current_org_id" not in views_content

    def test_multiple_known_modules(self, tmp_path: Path) -> None:
        """Multiple registered modules should all be built via the manifest path."""
        project = tmp_path / "myapp"
        _write_minimal_project(
            project,
            modules={
                "analytics": {"enabled": True},
                "billing": {"enabled": True},
            },
        )

        success, message = regenerate_managed_wiring(
            project, module_names=["analytics", "billing"]
        )
        assert success, f"regenerate_managed_wiring failed: {message}"

        content = (project / "myapp" / "settings" / "modules.py").read_text()
        assert "quickscale_modules_analytics" in content
        assert "quickscale_modules_billing" in content


class TestRegenerateManagedWiringSkipUnknown:
    """Phase 3: skip-unknown compatibility for non-registered modules.

    When ``regenerate_managed_wiring`` encounters a module name that has no
    manifest adapter registered (e.g. a discovered modules/ directory entry
    for a module without a manifest adapter), it should silently skip that
    module instead of raising ``ManifestAdapterNotFound``.

    Note: unknown module names in ``quickscale.yml`` are rejected by the
    config schema validator before reaching the manager.  The skip-unknown
    behaviour applies specifically to *discovered* modules from ``modules/``
    that lack a manifest adapter registration.
    """

    def test_discovered_unknown_module_is_silently_skipped(
        self, tmp_path: Path
    ) -> None:
        """A discovered module without a manifest adapter should be skipped."""
        project = tmp_path / "myapp"
        _write_minimal_project(project)

        # Create a modules/ directory with only an unknown module (no config entry).
        (project / "modules" / "custom_unknown").mkdir(parents=True)

        success, message = regenerate_managed_wiring(project)
        assert success, f"regenerate_managed_wiring failed: {message}"
        assert "regenerated" in message.lower()

    def test_mix_of_known_and_unknown_discovered_modules(self, tmp_path: Path) -> None:
        """Known discovered modules should be wired; unknown ones skipped."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Create modules/ with both a known and unknown module.
        # The known module must have a valid module.yml since the base path
        # now points at the embedded modules directory.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            analytics_yml.read_text()
        )
        (project / "modules" / "totally_unknown").mkdir(parents=True)

        success, message = regenerate_managed_wiring(project)
        assert success, f"regenerate_managed_wiring failed: {message}"

        content = (project / "myapp" / "settings" / "modules.py").read_text()
        assert "quickscale_modules_analytics" in content

    def test_discovered_modules_dir_with_unknown_module(self, tmp_path: Path) -> None:
        """Discovery from modules/ should skip entries without a manifest adapter."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Create a modules/ directory with both a known and unknown module.
        # The known module must have a valid module.yml since the base path
        # now points at the embedded modules directory.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            analytics_yml.read_text()
        )
        (project / "modules" / "custom_unknown").mkdir(parents=True)

        success, message = regenerate_managed_wiring(project)
        assert success, f"regenerate_managed_wiring failed: {message}"

        content = (project / "myapp" / "settings" / "modules.py").read_text()
        assert "quickscale_modules_analytics" in content

    def test_all_discovered_unknown_modules_still_succeeds(
        self, tmp_path: Path
    ) -> None:
        """When all discovered modules are unknown, regeneration still succeeds."""
        project = tmp_path / "myapp"
        _write_minimal_project(project)

        # Only unknown modules in modules/ directory (no config entries).
        (project / "modules" / "fake_a").mkdir(parents=True)
        (project / "modules" / "fake_b").mkdir(parents=True)

        success, message = regenerate_managed_wiring(project)
        assert success, f"regenerate_managed_wiring failed: {message}"

        # Settings file should still be written (empty module wiring).
        settings_modules = project / "myapp" / "settings" / "modules.py"
        assert settings_modules.exists()

    def test_forwarded_unknown_module_name_is_skipped(self, tmp_path: Path) -> None:
        """Explicitly forwarded unknown module names should be skipped."""
        project = tmp_path / "myapp"
        _write_minimal_project(project)

        # Pass an unknown module name explicitly (not via config).
        success, message = regenerate_managed_wiring(
            project, module_names=["nonexistent_module"]
        )
        assert success, f"regenerate_managed_wiring failed: {message}"


class TestManifestAdapterRegistryCompleteness:
    """Verify all expected modules are registered in the manifest adapter registry.

    Uses an autouse fixture to refresh managed adapters so the test is
    self-contained and does not depend on prior tests priming the registry
    via regenerate_managed_wiring (CR-SA44-REV-001).
    """

    @pytest.fixture(autouse=True)
    def _refresh_registry(self) -> None:
        """Refresh managed adapters before checking registry completeness.

        Without this, the test is order-dependent: managed-module entries
        (billing, crm, social) are only populated by
        refresh_managed_adapters(), which previously was only called on
        certain regenerate_managed_wiring code paths.
        """
        from quickscale_core.manifest.entry_point import (
            MANAGED_ADAPTER_ORIGINS,
            refresh_managed_adapters,
        )

        if MANAGED_ADAPTER_ORIGINS:
            try:
                refresh_managed_adapters()
            except Exception:
                pass  # Best-effort — may not have a modules base path

    @pytest.mark.parametrize(
        "module_name",
        [
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
        ],
    )
    def test_module_has_registered_adapter(self, module_name: str) -> None:
        """Each migrated module should have a manifest adapter registered."""
        assert module_name in MANIFEST_ADAPTER_REGISTRY, (
            f"Module '{module_name}' has no manifest adapter registered"
        )


class TestRegenerateManagedWiringEmbeddedNoMonorepo:
    """Embedded-project context: regenerate_managed_wiring succeeds outside the
    maintainer monorepo when embedded module manifests are available.
    Regression coverage for AF8-CR-002."""

    def test_outside_monorepo_with_embedded_manifests(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """regenerate_managed_wiring succeeds when get_modules_base_path raises
        ImproperlyConfigured but the project has real embedded manifests."""
        from quickscale_core.contracts import module_discovery as _md
        from quickscale_core.contracts.module_discovery import ImproperlyConfigured

        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Create an embedded analytics module with a real module.yml
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            analytics_yml.read_text()
        )

        # Clear the modules base path override so get_modules_base_path
        # attempts the monorepo path.
        original_override = _md._modules_base_path
        _md._modules_base_path = None

        try:
            # Make the monorepo path appear non-existent so
            # get_modules_base_path raises ImproperlyConfigured.
            monorepo_path = (
                Path(_md.__file__).resolve().parents[4] / "quickscale_modules"
            )
            _real_is_dir = Path.is_dir

            def _selective_is_dir(self: Path) -> bool:
                if str(self.resolve()) == str(monorepo_path.resolve()):
                    return False
                return _real_is_dir(self)

            monkeypatch.setattr(Path, "is_dir", _selective_is_dir)

            # Verify the pre-condition: no base path available
            with pytest.raises(ImproperlyConfigured):
                _md.get_modules_base_path()

            # Now call regenerate_managed_wiring — it should succeed by
            # detecting the embedded manifests and setting the base path
            # itself.
            success, message = regenerate_managed_wiring(project)
            assert success, f"regenerate_managed_wiring failed: {message}"
            assert "regenerated" in message.lower()

            # Verify managed wiring was actually written
            settings_modules = project / "myapp" / "settings" / "modules.py"
            assert settings_modules.exists()
            content = settings_modules.read_text()
            assert "quickscale_modules_analytics" in content

        finally:
            _md._modules_base_path = original_override


class TestRegenerateManagedWiringAdapterFailure:
    """regenerate_managed_wiring catches ImproperlyConfigured from adapter
    failures and returns (False, message) instead of propagating the exception.
    Regression coverage for AF7-CR-REV-001 and AF7-CR-REV-002."""

    def test_improperly_configured_caught_and_returned_as_failure(
        self, tmp_path: Path
    ) -> None:
        """When refresh_managed_adapters raises ImproperlyConfigured at
        the embedded modules base path, regenerate_managed_wiring returns
        (False, message), preserving the tuple[bool, str] return type."""
        from quickscale_core.manifest.entry_point import (
            MANIFEST_ADAPTER_REGISTRY as REGISTRY,
            MANAGED_ADAPTER_ORIGINS as ORIGINS,
        )

        # Save state before this test.
        _orig_registry = dict(REGISTRY)
        _orig_origins = set(ORIGINS)

        try:
            # Clear registry and origins, then add only a module name
            # whose Python package does not exist so that
            # refresh_managed_adapters raises ImproperlyConfigured
            # when trying to import it.
            REGISTRY.clear()
            ORIGINS.clear()
            ORIGINS.add("_test_missing_adapter")

            project = tmp_path / "myapp"
            _write_minimal_project(project, modules={"analytics": {"enabled": True}})

            # Create an embedded module.yml for the missing module so
            # _has_real_manifests is True and refresh_managed_adapters
            # is called with _test_missing_adapter's module.yml at the
            # base path.
            (project / "modules" / "_test_missing_adapter").mkdir(parents=True)
            (project / "modules" / "_test_missing_adapter" / "module.yml").write_text(
                "version: '1'\nname: _test_missing_adapter\n"
            )

            # The call to refresh_managed_adapters inside
            # regenerate_managed_wiring should raise
            # ImproperlyConfigured because
            # quickscale_modules__test_missing_adapter is not
            # importable. Our except ImproperlyConfigured handler
            # converts it to (False, message).
            success, message = regenerate_managed_wiring(project)

            assert success is False
            assert "Managed adapter wiring failed" in message
            assert "_test_missing_adapter" in message
        finally:
            REGISTRY.clear()
            REGISTRY.update(_orig_registry)
            ORIGINS.clear()
            ORIGINS.update(_orig_origins)


class TestRegenerateManagedWiringFailHard:
    """SA18.2 fail-hard: invalid analytics configuration must propagate
    through regenerate_managed_wiring instead of being silently swallowed
    (CR-SA18.2-001)."""

    def test_invalid_analytics_config_fails_through_regenerate(
        self, tmp_path: Path
    ) -> None:
        """Invalid analytics options (empty provider/host) cause
        regenerate_managed_wiring to return (False, message) instead of
        silently continuing."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Override all analytics required settings to empty values,
        # which triggers the _analytics_post_hook fail-hard validation.
        success, message = regenerate_managed_wiring(
            project,
            module_names=["analytics"],
            option_overrides={
                "analytics": {
                    "enabled": True,
                    "provider": "",
                    "posthog_api_key_env_var": "",
                    "posthog_host_env_var": "",
                    "posthog_host": "",
                }
            },
        )

        assert not success, (
            "Expected regenerate_managed_wiring to fail with invalid "
            f"analytics options, but it succeeded. Message: {message}"
        )
        assert "Analytics manifest settings" in message, (
            "Expected message about analytics settings validation failure, "
            f"got: {message}"
        )

    def test_valid_analytics_config_succeeds_with_overrides(
        self, tmp_path: Path
    ) -> None:
        """Valid analytics options still succeed through the override path,
        proving the fail-hard check does not break normal usage."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        success, message = regenerate_managed_wiring(
            project,
            module_names=["analytics"],
            option_overrides={
                "analytics": {
                    "enabled": True,
                    "provider": "posthog",
                    "posthog_api_key_env_var": "POSTHOG_API_KEY",
                    "posthog_host_env_var": "POSTHOG_HOST",
                    "posthog_host": "https://us.i.posthog.com",
                }
            },
        )

        assert success, (
            "Expected regenerate_managed_wiring to succeed with valid "
            f"analytics options, but it failed. Message: {message}"
        )


class TestRegenerateManagedWiringSkipManifestNotFound:
    """SA18.2 regression (CR-SA18.2-003): when _has_real_manifests is True,
    a registered module whose module.yml is missing from the embedded modules
    directory triggers ManifestError("Manifest file not found") which is
    silently skipped (continue), preserving the skip behaviour for legitimate
    embedded missing-manifest cases while non-"Manifest file not found"
    ManifestError cases still fail (validated in
    TestRegenerateManagedWiringFailHard)."""

    def test_registered_module_without_manifest_skipped_when_embedded(
        self, tmp_path: Path
    ) -> None:
        """When _has_real_manifests is True and a registered module's
        module.yml is absent from the embedded directory, the ManifestError
        is caught and silently skipped, preserving the skip-unknown contract."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Create modules/ with analytics (has module.yml) and blog (no module.yml).
        # At least one real manifest is needed for _has_real_manifests == True.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            analytics_yml.read_text()
        )
        # blog is in MANIFEST_ADAPTER_REGISTRY but has no module.yml here.
        (project / "modules" / "blog").mkdir(parents=True)

        success, message = regenerate_managed_wiring(project)
        assert success, f"regenerate_managed_wiring failed: {message}"
        assert "regenerated" in message.lower()

        # Verify analytics wiring was still written (blog was silently skipped).
        settings_modules = project / "myapp" / "settings" / "modules.py"
        assert settings_modules.exists()
        content = settings_modules.read_text()
        assert "quickscale_modules_analytics" in content

    def test_forwarded_registered_module_without_manifest_still_succeeds(
        self, tmp_path: Path
    ) -> None:
        """When _has_real_manifests is True and a registered module name is
        explicitly forwarded but its module.yml is absent, regeneration still
        succeeds (the ManifestError is silently skipped)."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Only analytics has module.yml; blog exists as an empty directory.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            analytics_yml.read_text()
        )
        (project / "modules" / "blog").mkdir(parents=True)

        # Forward both module names explicitly.
        success, message = regenerate_managed_wiring(
            project, module_names=["analytics", "blog"]
        )
        assert success, f"regenerate_managed_wiring failed: {message}"
        assert "regenerated" in message.lower()

        # Verify analytics wiring was written.
        content = (project / "myapp" / "settings" / "modules.py").read_text()
        assert "quickscale_modules_analytics" in content


class TestRegenerateManagedWiringPriorBasePath:
    """regenerate_managed_wiring refreshes managed adapters when a prior base
    path exists but no embedded module manifests are present.

    Regression coverage for CR-SA44-REV-001: before the fix,
    refresh_managed_adapters() was only called on the embedded-manifests
    branch.  When a prior base path was active (e.g. maintainer monorepo)
    and the project had no embedded module manifests, managed-module specs
    (social, billing, CRM) could be built against an unrefreshed registry.
    """

    def test_social_via_prior_base_path(self, tmp_path: Path) -> None:
        """A managed module (social) builds successfully when a prior base path
        is active and no embedded module manifests exist, because
        refresh_managed_adapters() is now called on the prior-base-path branch."""
        from quickscale_core.contracts import module_discovery as _md

        project = tmp_path / "myapp"
        _write_minimal_project(
            project,
            modules={
                "social": {
                    "provider_allowlist": ["x"],
                    "layout_variant": "list",
                }
            },
        )

        # Set the modules base path to the maintainer monorepo so that
        # _prior_base_path is not None and _has_real_manifests is False
        # (the test project has no modules/<name>/module.yml).
        monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"
        assert monorepo_path.is_dir(), "Maintainer monorepo must exist for this test"

        original_override = _md._modules_base_path
        _md._modules_base_path = monorepo_path

        try:
            # Verify precondition: no embedded manifests
            modules_dir = project / "modules"
            assert not modules_dir.is_dir() or not any(
                (modules_dir / entry.name / "module.yml").exists()
                for entry in modules_dir.iterdir()
                if modules_dir.is_dir()
            )

            success, message = regenerate_managed_wiring(
                project, module_names=["social"]
            )
            assert success, (
                f"regenerate_managed_wiring for social via prior base path "
                f"failed: {message}"
            )

            # Verify managed wiring was actually written.
            managed_views = project / "myapp" / "quickscale_managed" / "social_views.py"
            assert managed_views.exists(), (
                "Managed social_views.py not written via prior-base-path branch"
            )
            assert "x" in managed_views.read_text().lower() or (
                "twitter" in managed_views.read_text().lower()
            )
        finally:
            _md._modules_base_path = original_override

    def test_billing_via_prior_base_path(self, tmp_path: Path) -> None:
        """A managed module (billing) builds successfully via the prior-base-path
        branch, verifying that refresh_managed_adapters() runs for all managed
        origins before building specs."""
        from quickscale_core.contracts import module_discovery as _md

        project = tmp_path / "myapp"
        _write_minimal_project(
            project,
            modules={"billing": {"enabled": True}},
        )

        monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"
        original_override = _md._modules_base_path
        _md._modules_base_path = monorepo_path

        try:
            success, message = regenerate_managed_wiring(
                project, module_names=["billing"]
            )
            assert success, (
                f"regenerate_managed_wiring for billing via prior base path "
                f"failed: {message}"
            )

            settings_modules = project / "myapp" / "settings" / "modules.py"
            assert settings_modules.exists()
            content = settings_modules.read_text()
            assert "quickscale_modules_billing" in content
        finally:
            _md._modules_base_path = original_override


class TestRegenerateManagedWiringVersionMismatch:
    """SA117: version mismatch enforcement in regenerate_managed_wiring.

    When a loaded module manifest has a version older than the current core
    version, ``regenerate_managed_wiring`` must return ``(False, message)``
    with the dedicated mismatch message, before any ``ManifestError`` from
    the spec builder.
    """

    def test_embedded_module_with_old_version_blocks_regeneration(
        self, tmp_path: Path
    ) -> None:
        """An embedded module with version < core must be rejected."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Create an embedded analytics module with an old version.
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            'name: analytics\nversion: "0.86.0"\n'
        )

        with patch(
            "quickscale_cli.utils.module_wiring_manager.build_manifest_wiring_spec",
        ) as spy_spec:
            success, message = regenerate_managed_wiring(
                project, module_names=["analytics"]
            )

        assert success is False
        # Complete expected message including trailing period.
        assert message == (
            "Module 'analytics' version mismatch: "
            "found 0.86.0; expected core version 0.87.0."
        )
        # No spec building occurs when version mismatch is detected early.
        spy_spec.assert_not_called()

    def test_known_module_with_matching_version_succeeds(self, tmp_path: Path) -> None:
        """A module whose version matches core must still succeed."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        # Use the real analytics module.yml from the repository.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            analytics_yml.read_text()
        )

        success, message = regenerate_managed_wiring(
            project, module_names=["analytics"]
        )

        assert success, f"regenerate_managed_wiring failed: {message}"

    def test_mixed_versions_blocks_on_first_mismatch(self, tmp_path: Path) -> None:
        """When multiple modules are processed, the first version mismatch
        must block regeneration with a dedicated message (deterministic
        sorted order)."""
        project = tmp_path / "myapp"
        _write_minimal_project(
            project,
            modules={
                "analytics": {"enabled": True},
                "auth": {},
            },
        )

        # analytics has version 0.86.0 (will be processed first in sorted order).
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            'name: analytics\nversion: "0.86.0"\n'
        )
        # auth has version 0.87.0 (matching core).
        auth_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "auth"
            / "module.yml"
        )
        (project / "modules" / "auth").mkdir(parents=True)
        (project / "modules" / "auth" / "module.yml").write_text(auth_yml.read_text())

        with patch(
            "quickscale_cli.utils.module_wiring_manager.build_manifest_wiring_spec",
        ) as spy_spec:
            success, message = regenerate_managed_wiring(
                project, module_names=["analytics", "auth"]
            )

        assert success is False
        # Complete expected message including trailing period.
        assert message == (
            "Module 'analytics' version mismatch: "
            "found 0.86.0; expected core version 0.87.0."
        )
        # First-mismatch blocks spec building for all modules.
        spy_spec.assert_not_called()

    def test_unknown_module_still_skipped_before_version_check(
        self, tmp_path: Path
    ) -> None:
        """A module without a registered adapter must be skipped before the
        version check runs, preserving the skip-unknown contract."""
        project = tmp_path / "myapp"
        _write_minimal_project(project)

        (project / "modules" / "nonexistent").mkdir(parents=True)
        (project / "modules" / "nonexistent" / "module.yml").write_text(
            'name: nonexistent\nversion: "0.86.0"\n'
        )

        success, message = regenerate_managed_wiring(
            project, module_names=["nonexistent"]
        )

        # Unknown module should be skipped — regeneration succeeds with
        # no wiring written.
        assert success
        assert "regenerated" in message.lower()

    # ------------------------------------------------------------------
    # SA117a: non-canonical manifest version blocks regeneration
    # ------------------------------------------------------------------

    def test_embedded_module_with_noncanonical_version_blocks_regeneration(
        self, tmp_path: Path
    ) -> None:
        """An embedded module with a non-canonical version (leading zeros)
        must be rejected before any wiring is built."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            'name: analytics\nversion: "0.87.00"\n'
        )

        with patch(
            "quickscale_cli.utils.module_wiring_manager.build_manifest_wiring_spec",
        ) as spy_spec:
            success, message = regenerate_managed_wiring(
                project, module_names=["analytics"]
            )

        assert success is False
        # Complete expected message including trailing period.
        assert message == (
            "Module 'analytics' version mismatch: "
            "found 0.87.00; expected core version 0.87.0."
        )
        # No spec building — version rejection happens before _build_wiring_specs.
        spy_spec.assert_not_called()

    def test_embedded_module_with_whitespace_padded_version_blocks_regeneration(
        self, tmp_path: Path
    ) -> None:
        """A manifest with whitespace-padded version must be rejected."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})

        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            'name: analytics\nversion: " 0.87.0 "\n'
        )

        with patch(
            "quickscale_cli.utils.module_wiring_manager.build_manifest_wiring_spec",
        ) as spy_spec:
            success, message = regenerate_managed_wiring(
                project, module_names=["analytics"]
            )

        assert success is False
        # Exact whitespace-sensitive message: the raw " 0.87.0 " spelling
        # (leading space before 0, trailing space before semicolon) is
        # preserved verbatim without stripping or repr escaping.
        assert message == (
            "Module 'analytics' version mismatch: "
            "found  0.87.0 ; expected core version 0.87.0."
        )
        # No spec building — version rejection happens before _build_wiring_specs.
        spy_spec.assert_not_called()


class TestRegenerateManagedWiringEmptySelection:
    """SA127: empty module selection bypasses base-path preparation and adapter
    refresh. Empty selection succeeds in unconfigured contexts; non-empty
    selection still fails hard with the established error message."""

    # ------------------------------------------------------------------
    # SA127a: empty selection succeeds without base path
    # ------------------------------------------------------------------

    def test_empty_selection_succeeds_without_base_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """regenerate_managed_wiring with module_names=[] must succeed even
        when no modules base path is configured and no embedded manifests
        exist, because the empty-selection short-circuit skips base-path
        preparation and adapter refresh entirely."""
        from quickscale_core.contracts import module_discovery as _md

        project = tmp_path / "myapp"
        _write_minimal_project(project)  # No modules in config.

        # Ensure unconfigured state: no prior base path.  Also monkeypatch
        # the monorepo path to appear non-existent so get_modules_base_path
        # raises ImproperlyConfigured (simulating an installed-context project
        # outside the maintainer monorepo).
        original_override = _md._modules_base_path
        _md._modules_base_path = None

        monorepo_path = Path(_md.__file__).resolve().parents[4] / "quickscale_modules"
        _real_is_dir = Path.is_dir

        def _selective_is_dir(self: Path) -> bool:
            if str(self.resolve()) == str(monorepo_path.resolve()):
                return False
            return _real_is_dir(self)

        monkeypatch.setattr(Path, "is_dir", _selective_is_dir)

        try:
            success, message = regenerate_managed_wiring(project, module_names=[])
            assert success, (
                "Empty module selection should succeed without base path, "
                f"but got: {message}"
            )
            assert "regenerated" in message.lower()

            # Empty wiring files should still be written.
            modules_file = project / "myapp" / "settings" / "modules.py"
            assert modules_file.exists()
            content = modules_file.read_text()
            assert "MODULE_INSTALLED_APPS: list[str] = []" in content
            assert "MODULE_MIDDLEWARE: list[str] = []" in content
            assert "MODULE_SETTINGS: dict[str, object] = {}" in content

            urls_file = project / "myapp" / "urls_modules.py"
            assert urls_file.exists()
            urls_content = urls_file.read_text()
            assert (
                "PRE_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []"
                in urls_content
            )
            assert (
                "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []"
                in urls_content
            )

            # No managed files when no module specs exist.
            managed_init = project / "myapp" / "quickscale_managed" / "__init__.py"
            assert not managed_init.exists()
        finally:
            _md._modules_base_path = original_override

    # ------------------------------------------------------------------
    # SA127b: non-empty selection still fails with exact message
    # ------------------------------------------------------------------

    def test_non_empty_selection_fails_without_base_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """regenerate_managed_wiring with a non-empty module_names must still
        fail when no modules base path is configured and no embedded manifests
        exist, preserving the exact established error message."""
        from quickscale_core.contracts import module_discovery as _md

        project = tmp_path / "myapp"
        _write_minimal_project(project)  # No modules in config.

        # Ensure unconfigured state: no prior base path.  Also monkeypatch
        # the monorepo path to appear non-existent so get_modules_base_path
        # raises ImproperlyConfigured (simulating an installed-context project
        # outside the maintainer monorepo).
        original_override = _md._modules_base_path
        _md._modules_base_path = None

        monorepo_path = Path(_md.__file__).resolve().parents[4] / "quickscale_modules"
        _real_is_dir = Path.is_dir

        def _selective_is_dir(self: Path) -> bool:
            if str(self.resolve()) == str(monorepo_path.resolve()):
                return False
            return _real_is_dir(self)

        monkeypatch.setattr(Path, "is_dir", _selective_is_dir)

        try:
            success, message = regenerate_managed_wiring(
                project, module_names=["analytics"]
            )
            assert not success, (
                "Non-empty module selection should fail without base path, "
                f"but succeeded with: {message}"
            )
            assert message == (
                "Modules base path not configured and no embedded module "
                "manifests found. Run inside the maintainer monorepo, call "
                "set_modules_base_path(), or embed at least one module with "
                "a module.yml file."
            )
        finally:
            _md._modules_base_path = original_override
