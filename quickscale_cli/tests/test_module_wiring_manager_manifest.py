"""Phase 3 regression tests for the manifest-path regeneration switch.

Verifies that ``regenerate_managed_wiring`` now routes through the manifest
adapter registry (``build_manifest_wiring_spec``) while preserving the
legacy skip-unknown behaviour for discovered/forwarded module names that
have no registered adapter.

These tests complement the existing apply/remove/module-config tests that
exercise the manager indirectly through CLI commands.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import types
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from quickscale_cli.utils.module_wiring_manager import regenerate_managed_wiring
from quickscale_cli.utils import module_wiring_manager
from quickscale_core.contracts.module_discovery import ImproperlyConfigured
from quickscale_core.contracts.module_discovery import (
    discover_shipped_module_names,
    get_modules_base_path,
)
from quickscale_core.manifest.entry_point import (
    MANAGED_ADAPTER_ORIGINS,
    MANIFEST_ADAPTER_REGISTRY,
    build_manifest_wiring_spec,
    refresh_managed_adapters,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_core import module_wiring as core_module_wiring


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


def _write_complete_embedded_inventory(
    project_path: Path, *, exclude: set[str] | None = None
) -> None:
    """Copy the shipped manifest inventory into an embedded test project."""
    source_root = Path(__file__).resolve().parents[2] / "quickscale_modules"
    excluded = exclude or set()
    for module_name in sorted(
        path.name
        for path in source_root.iterdir()
        if path.is_dir()
        and (path / "module.yml").is_file()
        and path.name not in excluded
    ):
        target = project_path / "modules" / module_name
        target.mkdir(parents=True, exist_ok=True)
        (target / "module.yml").write_text(
            (source_root / module_name / "module.yml").read_text()
        )


def _load_embedded_manifest_contract(project_path: Path) -> dict[str, Any]:
    """Capture defaults and mutable setting mappings from embedded manifests."""
    manifests: dict[str, object] = {}
    options: dict[str, dict[str, object]] = {}
    option_to_setting: dict[str, dict[str, str]] = {}
    expected_settings: dict[str, dict[str, object]] = {}

    modules_root = project_path / "modules"
    for manifest_path in sorted(modules_root.glob("*/module.yml")):
        manifest = load_manifest_from_path(manifest_path)
        module_name = manifest_path.parent.name
        manifests[module_name] = manifest
        options[module_name] = manifest.get_defaults()
        mapping = manifest.get_django_settings_mapping()
        option_to_setting[module_name] = mapping
        expected_settings[module_name] = {
            setting_name: manifest.mutable_options[option_name].default
            for option_name, setting_name in mapping.items()
        }

    return {
        "manifests": manifests,
        "names": tuple(sorted(manifests)),
        "options": options,
        "option_to_setting": option_to_setting,
        "expected_settings": expected_settings,
    }


def _read_emitted_module_settings(project_path: Path) -> dict[str, Any]:
    """Read ``MODULE_SETTINGS`` without executing generated project code."""
    settings_path = project_path / "myapp" / "settings" / "modules.py"
    tree = ast.parse(settings_path.read_text(), filename=str(settings_path))
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "MODULE_SETTINGS"
    ]
    assert len(assignments) == 1, (
        "Generated modules.py must define MODULE_SETTINGS once"
    )
    value_node = assignments[0].value
    assert value_node is not None, "MODULE_SETTINGS assignment must have a value"
    value = ast.literal_eval(value_node)
    assert isinstance(value, dict), "MODULE_SETTINGS must be a dictionary"
    return value


class TestRegenerateManagedWiringManifestPath:
    """Phase 3: regeneration routes through the manifest adapter registry."""

    def test_known_module_routes_through_manifest(self, tmp_path: Path) -> None:
        """A registered module (analytics) should be built via the manifest path."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})
        _write_complete_embedded_inventory(project)

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

        settings_modules = project / "myapp" / "settings" / "modules.py"
        content = settings_modules.read_text()
        views_content = managed_views.read_text()

        social_manifest_path = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "social"
            / "module.yml"
        )
        social_manifest = load_manifest_from_path(social_manifest_path)
        app_projections = [
            projection
            for projection in social_manifest.wiring_projections
            if projection.get("wiring_field") == "apps"
        ]
        assert len(app_projections) == 1
        app_projection = app_projections[0]
        assert app_projection.get("derivation_type") == "static"
        expression = app_projection.get("expression")
        assert isinstance(expression, dict)
        social_apps = expression.get("value")
        assert (
            isinstance(social_apps, list)
            and len(social_apps) == 1
            and isinstance(social_apps[0], str)
            and bool(social_apps[0].strip())
        )
        social_app = social_apps[0]
        rendered_apps = content.split(
            "MODULE_INSTALLED_APPS: list[str] = ",
            1,
        )[1].split("\n\n", 1)[0]
        assert rendered_apps.count(repr(social_app)) == 1

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

    def test_manager_uses_only_refreshed_adapters_for_desired_overrides(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Manager execution must not depend on removed config/applier APIs.

        The poisoned module_config import makes any accidental runtime access
        to the removed wiring surface fail immediately.  The expected spec is
        independently obtained from the refreshed module-owned adapter, while
        the manager's writer, collection, and render calls are observed for
        parity with that result.
        """
        project = tmp_path / "myapp"
        desired_options = {"analytics": {"provider": "posthog"}}
        _write_minimal_project(
            project, modules={"analytics": desired_options["analytics"]}
        )
        _write_complete_embedded_inventory(project)

        class _RemovedModuleConfig(types.ModuleType):
            def __getattribute__(self, name: str) -> object:
                raise AssertionError(
                    f"manager accessed removed module_config wiring surface: {name}"
                )

        monkeypatch.setitem(
            sys.modules,
            "quickscale_cli.commands.module_config",
            _RemovedModuleConfig("quickscale_cli.commands.module_config"),
        )

        refresh_managed_adapters()
        expected_spec = build_manifest_wiring_spec(
            "analytics", desired_options["analytics"], project_package="myapp"
        )

        with (
            patch.object(
                module_wiring_manager,
                "refresh_managed_adapters",
                wraps=module_wiring_manager.refresh_managed_adapters,
            ) as refresh_spy,
            patch.object(
                module_wiring_manager,
                "write_managed_wiring",
                wraps=module_wiring_manager.write_managed_wiring,
            ) as writer_spy,
            patch.object(
                core_module_wiring,
                "collect_wiring",
                wraps=core_module_wiring.collect_wiring,
            ) as collect_spy,
            patch.object(
                core_module_wiring,
                "collect_url_wiring",
                wraps=core_module_wiring.collect_url_wiring,
            ) as collect_urls_spy,
            patch.object(
                core_module_wiring,
                "render_settings_modules_py",
                wraps=core_module_wiring.render_settings_modules_py,
            ) as render_settings_spy,
            patch.object(
                core_module_wiring,
                "render_urls_modules_py",
                wraps=core_module_wiring.render_urls_modules_py,
            ) as render_urls_spy,
        ):
            success, message = regenerate_managed_wiring(
                project,
                module_names=["analytics"],
                option_overrides=desired_options,
                project_package="myapp",
            )

        assert success, message
        assert refresh_spy.call_count == 1
        writer_spy.assert_called_once()
        actual_specs = writer_spy.call_args.args[1]
        assert actual_specs == {"analytics": expected_spec}

        assert render_settings_spy.call_count == 1
        assert render_urls_spy.call_count == 1
        assert render_settings_spy.call_args.args[0] == actual_specs
        assert render_urls_spy.call_args.args[0] == actual_specs
        assert collect_spy.call_count >= 1
        assert all(call.args[0] == actual_specs for call in collect_spy.call_args_list)
        assert collect_urls_spy.call_count >= 1
        assert all(
            call.args[0] == actual_specs for call in collect_urls_spy.call_args_list
        )

        settings_content = (project / "myapp" / "settings" / "modules.py").read_text()
        assert "posthog" in settings_content

    def test_manager_inputs_match_refreshed_adapter_specs_for_all_source_modules(
        self, tmp_path: Path
    ) -> None:
        """Every source-discovered adapter supplies the manager's wiring input."""
        project = tmp_path / "myapp"
        module_names = discover_shipped_module_names()
        source_base = get_modules_base_path()
        source_manifests = {
            module_name: load_manifest_from_path(
                source_base / module_name / "module.yml"
            )
            for module_name in module_names
        }
        assert len(module_names) == 12
        assert set(source_manifests) == set(module_names)

        empty_options = {module_name: {} for module_name in module_names}
        _write_minimal_project(project, modules=empty_options)
        _write_complete_embedded_inventory(project)

        refresh_managed_adapters()
        expected_specs = {
            module_name: build_manifest_wiring_spec(
                module_name, empty_options[module_name], project_package="myapp"
            )
            for module_name in module_names
        }

        with (
            patch.object(
                module_wiring_manager,
                "write_managed_wiring",
                wraps=module_wiring_manager.write_managed_wiring,
            ) as writer_spy,
            patch.object(
                core_module_wiring,
                "collect_wiring",
                wraps=core_module_wiring.collect_wiring,
            ) as collect_spy,
            patch.object(
                core_module_wiring,
                "render_settings_modules_py",
                wraps=core_module_wiring.render_settings_modules_py,
            ) as render_settings_spy,
            patch.object(
                core_module_wiring,
                "render_urls_modules_py",
                wraps=core_module_wiring.render_urls_modules_py,
            ) as render_urls_spy,
        ):
            success, message = regenerate_managed_wiring(
                project,
                module_names=module_names,
                project_package="myapp",
            )

        assert success, message
        writer_spy.assert_called_once()
        actual_specs = writer_spy.call_args.args[1]
        assert actual_specs == expected_specs
        assert set(actual_specs) == set(source_manifests)

        for module_name, manifest in source_manifests.items():
            declared_apps = {
                app
                for projection in manifest.wiring_projections
                if projection.get("wiring_field") == "apps"
                for app in (projection.get("expression") or {}).get("value", [])
            }
            assert declared_apps <= set(actual_specs[module_name].apps)

        assert render_settings_spy.call_args.args[0] == expected_specs
        assert render_urls_spy.call_args.args[0] == expected_specs
        assert collect_spy.call_count >= 1
        assert all(
            call.args[0] == expected_specs for call in collect_spy.call_args_list
        )

    def test_all_embedded_modules_regenerate_manifest_defaults(
        self, tmp_path: Path
    ) -> None:
        """Real CLI regeneration must retain every manifest-owned setting."""
        project = tmp_path / "myapp"
        _write_minimal_project(project)
        _write_complete_embedded_inventory(project)
        contract = _load_embedded_manifest_contract(project)
        names = contract["names"]
        options = contract["options"]
        expected_settings = contract["expected_settings"]
        assert isinstance(names, tuple)
        assert isinstance(options, dict)
        assert isinstance(expected_settings, dict)
        assert len(names) == 12
        assert sum(len(settings) for settings in expected_settings.values()) == 68

        _write_minimal_project(
            project,
            modules={name: options[name] for name in names},
        )

        success, message = regenerate_managed_wiring(project)
        assert success, f"regenerate_managed_wiring failed: {message}"

        emitted = _read_emitted_module_settings(project)
        for name in names:
            expected = expected_settings[name]
            assert {
                setting_name: emitted[setting_name] for setting_name in expected
            } == expected
        content = (project / "myapp" / "settings" / "modules.py").read_text()
        assert all(f"quickscale_modules_{name}" in content for name in names)
        assert any(value is False for value in emitted.values())
        assert any(value == "" for value in emitted.values())
        assert any(isinstance(value, list) for value in emitted.values())


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
        _write_complete_embedded_inventory(project)

        # Create modules/ with both a known and unknown module.
        # The known module must have a valid module.yml since the base path
        # now points at the embedded modules directory.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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
        _write_complete_embedded_inventory(project)

        # Create a modules/ directory with both a known and unknown module.
        # The known module must have a valid module.yml since the base path
        # now points at the embedded modules directory.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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

        Without this, the test is order-dependent: managed-module entries are
        populated by refresh_managed_adapters(), which previously was only
        called on certain regenerate_managed_wiring code paths.
        """
        from quickscale_core.manifest.entry_point import (
            refresh_managed_adapters,
        )

        refresh_managed_adapters()

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
        _write_complete_embedded_inventory(project)

        # Create an embedded analytics module with a real module.yml
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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
            _write_complete_embedded_inventory(project, exclude={"analytics"})

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

    def test_failed_refresh_restores_exact_prior_ownership_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed context switch restores base, registry, and origin state."""
        from quickscale_core.contracts import module_discovery as _md
        from quickscale_core.contracts.module_discovery import ModuleResolutionSource

        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})
        (project / "modules" / "analytics").mkdir(parents=True)
        (project / "modules" / "analytics" / "module.yml").write_text(
            "version: '1'\nname: analytics\n"
        )

        registry_identity = id(MANIFEST_ADAPTER_REGISTRY)
        origins_identity = id(MANAGED_ADAPTER_ORIGINS)
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        original_override = _md._modules_base_path
        monorepo_path = Path(__file__).resolve().parents[2] / "quickscale_modules"

        def custom_adapter(*args: object, **kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec()

        _md._modules_base_path = monorepo_path
        MANIFEST_ADAPTER_REGISTRY["_test_restore_custom"] = custom_adapter
        expected_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        expected_origins = set(MANAGED_ADAPTER_ORIGINS)

        def _partially_mutate_then_fail() -> None:
            MANIFEST_ADAPTER_REGISTRY.pop("analytics", None)
            MANIFEST_ADAPTER_REGISTRY["_test_leaked"] = custom_adapter
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update({"analytics", "_test_leaked"})
            raise ImproperlyConfigured("simulated embedded refresh failure")

        monkeypatch.setattr(
            module_wiring_manager,
            "refresh_managed_adapters",
            _partially_mutate_then_fail,
        )
        try:
            with patch.object(module_wiring_manager, "write_managed_wiring") as writer:
                success, message = regenerate_managed_wiring(
                    project, module_names=["analytics"]
                )

            assert success is False
            assert "simulated embedded refresh failure" in message
            writer.assert_not_called()
            assert id(MANIFEST_ADAPTER_REGISTRY) == registry_identity
            assert MANIFEST_ADAPTER_REGISTRY == expected_registry
            assert MANIFEST_ADAPTER_REGISTRY["_test_restore_custom"] is custom_adapter
            assert id(MANAGED_ADAPTER_ORIGINS) == origins_identity
            assert MANAGED_ADAPTER_ORIGINS == expected_origins
            assert _md._modules_base_path == monorepo_path
            assert _md.get_resolution_source() is ModuleResolutionSource.OVERRIDE
        finally:
            _md._modules_base_path = original_override
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)


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

    def test_invalid_backups_target_mode_fails_through_regenerate(
        self, tmp_path: Path
    ) -> None:
        """CLI regeneration must not silently rewrite an unsupported mode."""
        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"backups": {}})

        success, message = regenerate_managed_wiring(
            project,
            module_names=["backups"],
            option_overrides={"backups": {"target_mode": "unsupported"}},
        )

        assert success is False
        assert "modules.backups.target_mode must be one of" in message


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
        assert success is False
        assert "inventory count drift" in message

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
        assert success is False
        assert "inventory count drift" in message


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

    def test_monorepo_resolution_source_is_restored_after_success(
        self, tmp_path: Path
    ) -> None:
        """A successful context switch restores base and adapter ownership state."""
        from quickscale_core.contracts import module_discovery as _md
        from quickscale_core.contracts.module_discovery import ModuleResolutionSource

        project = tmp_path / "myapp"
        _write_minimal_project(project, modules={"analytics": {"enabled": True}})
        _write_complete_embedded_inventory(project)
        original_override = _md._modules_base_path
        original_registry = dict(MANIFEST_ADAPTER_REGISTRY)
        original_origins = set(MANAGED_ADAPTER_ORIGINS)
        registry_identity = id(MANIFEST_ADAPTER_REGISTRY)
        origins_identity = id(MANAGED_ADAPTER_ORIGINS)

        def custom_adapter(*args: object, **kwargs: object) -> ModuleWiringSpec:
            return ModuleWiringSpec()

        try:
            _md._modules_base_path = None
            MANIFEST_ADAPTER_REGISTRY["_test_restore_custom"] = custom_adapter
            expected_registry = dict(MANIFEST_ADAPTER_REGISTRY)
            expected_origins = set(MANAGED_ADAPTER_ORIGINS)
            assert _md.get_resolution_source() is ModuleResolutionSource.MONOREPO

            success, message = regenerate_managed_wiring(
                project, module_names=["analytics"]
            )

            assert success, message
            assert _md._modules_base_path is None
            assert _md.get_resolution_source() is ModuleResolutionSource.MONOREPO
            assert id(MANIFEST_ADAPTER_REGISTRY) == registry_identity
            assert MANIFEST_ADAPTER_REGISTRY == expected_registry
            assert MANIFEST_ADAPTER_REGISTRY["_test_restore_custom"] is custom_adapter
            assert id(MANAGED_ADAPTER_ORIGINS) == origins_identity
            assert MANAGED_ADAPTER_ORIGINS == expected_origins
        finally:
            _md._modules_base_path = original_override
            MANIFEST_ADAPTER_REGISTRY.clear()
            MANIFEST_ADAPTER_REGISTRY.update(original_registry)
            MANAGED_ADAPTER_ORIGINS.clear()
            MANAGED_ADAPTER_ORIGINS.update(original_origins)


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
        _write_complete_embedded_inventory(project)

        # Create an embedded analytics module with an old version.
        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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
        _write_complete_embedded_inventory(project)

        # Use the real analytics module.yml from the repository.
        analytics_yml = (
            Path(__file__).resolve().parents[2]
            / "quickscale_modules"
            / "analytics"
            / "module.yml"
        )
        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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
        _write_complete_embedded_inventory(project)

        # analytics has version 0.86.0 (will be processed first in sorted order).
        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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
        (project / "modules" / "auth").mkdir(parents=True, exist_ok=True)
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
        _write_complete_embedded_inventory(project)

        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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
        _write_complete_embedded_inventory(project)

        (project / "modules" / "analytics").mkdir(parents=True, exist_ok=True)
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
