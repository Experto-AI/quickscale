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
            "theme": "showcase_html",
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
    """Verify all expected modules are registered in the manifest adapter registry."""

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
        from django.core.exceptions import ImproperlyConfigured
        from quickscale_core.contracts import module_discovery as _md

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
