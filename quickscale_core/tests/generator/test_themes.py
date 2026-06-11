"""Tests for theme system functionality"""

import os
from pathlib import Path

import pytest

from quickscale_core.contracts.module_catalog import MODULE_CATALOG, get_module_names
from quickscale_core.generator import ProjectGenerator
from quickscale_core.generator.generator import (
    REACT_THEME_OPTIONAL_FILES,
    REACT_THEME_SHARED_DJANGO_TEMPLATES,
)


class TestThemeInitialization:
    """Test theme parameter initialization"""

    def test_default_theme(self, tmp_path: Path) -> None:
        """Generator should use showcase_react as default theme"""
        generator = ProjectGenerator()
        assert generator.theme == "showcase_react"

    def test_explicit_theme(self, tmp_path: Path) -> None:
        """Generator should accept explicit theme parameter"""
        generator = ProjectGenerator(theme="showcase_html")
        assert generator.theme == "showcase_html"

    def test_invalid_theme_name(self, tmp_path: Path) -> None:
        """Generator should reject invalid theme names"""
        with pytest.raises(ValueError, match="Invalid theme 'invalid_theme'"):
            ProjectGenerator(theme="invalid_theme")

    def test_available_themes_list(self, tmp_path: Path) -> None:
        """Error message should list available themes"""
        with pytest.raises(ValueError, match="Available themes"):
            ProjectGenerator(theme="nonexistent")


class TestThemeValidation:
    """Test theme directory validation"""

    def test_showcase_html_theme_exists(self) -> None:
        """showcase_html theme directory should exist"""
        generator = ProjectGenerator(theme="showcase_html")
        theme_dir = generator.template_dir / "themes" / "showcase_html"
        assert theme_dir.exists()

    def test_htmx_theme_is_not_supported(self) -> None:
        """showcase_htmx should be rejected as an unsupported theme."""
        with pytest.raises(ValueError, match="showcase_htmx"):
            ProjectGenerator(theme="showcase_htmx")

    def test_react_theme_placeholder_exists(self) -> None:
        """showcase_react should have placeholder directory"""
        generator = ProjectGenerator(theme="showcase_html")
        theme_dir = generator.template_dir / "themes" / "showcase_react"
        assert theme_dir.exists()
        readme = theme_dir / "README.md"
        assert readme.exists()


class TestThemeTemplateResolution:
    """Test theme-specific template path resolution"""

    def test_theme_template_path_resolution(self) -> None:
        """_get_theme_template_path should resolve theme-specific templates"""
        generator = ProjectGenerator(theme="showcase_html")

        # Theme-specific template
        path = generator._get_theme_template_path("templates/base.html.j2")
        assert "themes/showcase_html" in path

    def test_theme_static_path_resolution(self) -> None:
        """_get_theme_template_path should resolve theme-specific static files"""
        generator = ProjectGenerator(theme="showcase_html")

        # Theme-specific static file
        path = generator._get_theme_template_path("static/css/style.css.j2")
        assert "themes/showcase_html" in path

    def test_common_template_fallback(self) -> None:
        """_get_theme_template_path should fall back to common templates"""
        generator = ProjectGenerator(theme="showcase_html")

        # This should fall back to root (backend templates)
        path = generator._get_theme_template_path("manage.py.j2")
        # Should not be in themes directory
        assert "themes" not in path or "manage.py.j2" in path


class TestProjectGenerationWithTheme:
    """Test complete project generation with themes"""

    def test_generate_with_default_theme(self, tmp_path: Path) -> None:
        """Generate project with default theme"""
        generator = ProjectGenerator()
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Verify React frontend and templates exist
        assert (output_path / "frontend" / "package.json").exists()
        assert (output_path / "frontend" / "vite.config.ts").exists()
        assert (output_path / "frontend" / "src" / "App.tsx").exists()
        assert (output_path / "templates" / "base.html").exists()
        assert (output_path / "templates" / "index.html").exists()

        # Verify backend files exist
        assert (output_path / "manage.py").exists()
        assert (output_path / "pyproject.toml").exists()

    def test_generate_with_explicit_theme(self, tmp_path: Path) -> None:
        """Generate project with explicit showcase_html theme"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Verify all files created
        assert (output_path / "templates" / "base.html").exists()
        assert (output_path / "templates" / "index.html").exists()
        assert (output_path / "templates" / "components" / "navigation.html").exists()
        assert (output_path / "static" / "css" / "style.css").exists()

        base_html = (output_path / "templates" / "base.html").read_text()
        index_html = (output_path / "templates" / "index.html").read_text()
        navigation_html = (
            output_path / "templates" / "components" / "navigation.html"
        ).read_text()

        assert 'class="qs-main"' in base_html
        assert 'class="qs-topbar"' in navigation_html
        assert 'class="dashboard-intro"' in index_html
        assert (
            "Your Django project has been successfully generated with QuickScale."
            in index_html
        )

    def test_generate_with_react_theme(self, tmp_path: Path) -> None:
        """Generate project with showcase_react theme"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "testproject_react"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Verify frontend structure
        assert (output_path / "frontend" / "package.json").exists()
        assert (output_path / "frontend" / "vite.config.ts").exists()
        assert (output_path / "frontend" / "src" / "App.tsx").exists()

        # Verify utils.ts exists (CRITICAL for build)
        assert (output_path / "frontend" / "src" / "lib" / "utils.ts").exists()

        # Verify Django template for React exists (serves built assets)
        assert (output_path / "templates" / "index.html").exists()
        index_html = (output_path / "templates" / "index.html").read_text()
        assert "{% load static %}" in index_html
        assert "{% static 'frontend/assets/index.js' %}" in index_html

        # Verify base.html exists (required by auth module and error pages)
        assert (output_path / "templates" / "base.html").exists()
        base_html = (output_path / "templates" / "base.html").read_text()
        assert "<!doctype html>" in base_html.lower() or "<!DOCTYPE html>" in base_html
        assert "{% block content %}" in base_html
        assert "{% block extra_css %}" in base_html
        assert "{% block extra_js %}" in base_html
        assert "{% block title %}" in base_html

        # Check Dockerfile has node parts
        dockerfile = (output_path / "Dockerfile").read_text()
        assert "FROM node:24-slim as frontend-builder" in dockerfile
        assert "pnpm run build" in dockerfile

    @pytest.mark.parametrize(
        ("theme", "project_name", "expects_frontend"),
        [
            ("showcase_html", "testproject_html", False),
            ("showcase_react", "testproject_react", True),
        ],
    )
    def test_generated_makefile_respects_frontend_presence(
        self,
        tmp_path: Path,
        theme: str,
        project_name: str,
        expects_frontend: bool,
    ) -> None:
        """Generated Makefile should guard frontend targets based on frontend presence."""
        generator = ProjectGenerator(theme=theme)
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        makefile = (output_path / "Makefile").read_text()

        if expects_frontend:
            assert (output_path / "frontend" / "package.json").exists()
            assert "cd frontend && pnpm test:coverage;" in makefile
            return

        assert not (output_path / "frontend" / "package.json").exists()
        assert "No frontend/package.json found, skipping frontend install." in makefile
        assert "No frontend/package.json found, skipping frontend lint." in makefile
        assert "No frontend/package.json found, skipping frontend format." in makefile
        assert "No frontend/package.json found, skipping frontend tests." in makefile

    def test_react_theme_vite_config_has_consistent_filenames(
        self, tmp_path: Path
    ) -> None:
        """Vite config should use consistent filenames for Django compatibility"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "testproject_react"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        vite_config = (output_path / "frontend" / "vite.config.ts").read_text()
        # Check for consistent filename config (no hashes)
        assert "entryFileNames: 'assets/[name].js'" in vite_config
        assert "assetFileNames: 'assets/[name].[ext]'" in vite_config

    def test_react_theme_production_settings_override_static_storage(
        self, tmp_path: Path
    ) -> None:
        """React theme should disable manifest URL rewriting for staticfiles storage."""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "testproject_react"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        production_settings = (
            output_path / project_name / "settings" / "production.py"
        ).read_text()
        assert 'STORAGES["staticfiles"]' in production_settings
        assert "whitenoise.storage.CompressedStaticFilesStorage" in production_settings

    def test_generated_output_matches_current_scaffold_contract(
        self, tmp_path: Path
    ) -> None:
        """Generated project structure should match the current scaffold contract."""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Broad output contract for the generated project scaffold.
        expected_files = [
            "README.md",
            "Makefile",
            "manage.py",
            "pyproject.toml",
            ".gitignore",
            ".dockerignore",
            "Dockerfile",
            "docker-compose.yml",
            "railway.json",
            ".env.example",
            "scripts/lint.sh",
            "templates/base.html",
            "templates/index.html",
            "static/css/style.css",
            "static/images/favicon.svg",
            f"{project_name}/__init__.py",
            f"{project_name}/urls.py",
            f"{project_name}/settings/base.py",
            f"{project_name}/settings/local.py",
            f"{project_name}/settings/production.py",
            "tests/__init__.py",
            "tests/conftest.py",
            ".github/workflows/ci.yml",
        ]

        for file_path in expected_files:
            assert (output_path / file_path).exists(), f"Missing file: {file_path}"

        lint_script = output_path / "scripts" / "lint.sh"
        assert os.access(lint_script, os.X_OK), (
            "scripts/lint.sh should stay executable because the generated Makefile "
            "invokes it directly"
        )


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""

    def test_generator_without_theme_parameter(self, tmp_path: Path) -> None:
        """Generator should work without theme parameter (backward compatible)"""
        # Old code: ProjectGenerator()
        generator = ProjectGenerator()
        project_name = "testproject"
        output_path = tmp_path / project_name

        # Should generate successfully with default theme
        generator.generate(project_name, output_path)
        assert output_path.exists()

    def test_generated_templates_identical_to_v060(self, tmp_path: Path) -> None:
        """Generated templates should be identical to v0.60.0"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check template content (should have same structure as v0.60.0)
        base_html = (output_path / "templates" / "base.html").read_text()
        assert "<!DOCTYPE html>" in base_html
        assert "<title>" in base_html
        assert "{% block content %}" in base_html


class TestReactThemeBuildCompatibility:
    """Test React theme TypeScript/build compatibility.

    These tests verify that the generated React frontend can be built
    without TypeScript errors, ensuring production deployments succeed.
    """

    def test_react_theme_no_unused_imports(self, tmp_path: Path) -> None:
        """Verify React theme files have no unused imports.

        This is a critical test because unused imports cause TypeScript
        compilation to fail with noUnusedLocals: true, which breaks
        Docker builds.

        Regression test for: Button import in Sidebar.tsx causing build failure.
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "testproject_react"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check key files that commonly have unused import issues
        tsx_files = [
            "frontend/src/components/layout/Sidebar.tsx",
            "frontend/src/components/layout/Navbar.tsx",
            "frontend/src/App.tsx",
        ]

        for tsx_file in tsx_files:
            filepath = output_path / tsx_file
            if filepath.exists():
                content = filepath.read_text()
                # Check each import statement
                import_lines = [
                    line
                    for line in content.split("\n")
                    if line.strip().startswith("import")
                ]
                for import_line in import_lines:
                    # Extract imported names
                    if "{" in import_line and "}" in import_line:
                        imports_part = import_line.split("{")[1].split("}")[0]
                        imports = [i.strip() for i in imports_part.split(",")]
                        for imported_name in imports:
                            # Clean up 'as' aliases
                            clean_name = imported_name.split(" as ")[0].strip()
                            if clean_name:
                                # Check if the imported name is actually used in the file
                                # (excluding the import line itself)
                                content_without_imports = "\n".join(
                                    line
                                    for line in content.split("\n")
                                    if not line.strip().startswith("import")
                                )
                                # Simple check: name should appear somewhere in the file
                                assert clean_name in content_without_imports, (
                                    f"Unused import '{clean_name}' in {tsx_file}. "
                                    f"This will cause TypeScript build to fail."
                                )

    def test_react_theme_dockerfile_correct_paths(self, tmp_path: Path) -> None:
        """Verify Dockerfile copies frontend assets correctly.

        The Dockerfile must copy built assets with correct ownership
        to avoid permission errors during collectstatic.
        """
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "testproject_react"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        dockerfile = (output_path / "Dockerfile").read_text()

        # Should have --chown for frontend assets
        assert "--chown=django:django" in dockerfile
        assert "/app/static/frontend/assets" in dockerfile

        # Should NOT copy index.html to templates (we generate Django template)
        assert "index.html /app/templates/index.html" not in dockerfile


class TestReactOptionalFilesModuleCatalogAlignment:
    """Lightweight alignment between the React gating map and the module catalog.

    ``REACT_THEME_OPTIONAL_FILES`` maps every optional React file to the
    module that gates it. If a gating module key is not present in the
    shared module catalog, ``selected_modules`` membership gating would
    silently never trigger because the key can never appear in user
    configs. This test guards that contract from drifting.
    """

    def test_all_react_optional_file_gating_modules_are_in_catalog(self) -> None:
        """Every module referenced by ``REACT_THEME_OPTIONAL_FILES`` must exist in the catalog."""
        catalog_names = set(get_module_names(include_experimental=True))
        gating_modules = set(REACT_THEME_OPTIONAL_FILES.values())

        missing = gating_modules - catalog_names
        assert not missing, (
            "REACT_THEME_OPTIONAL_FILES references gating modules that are "
            f"missing from MODULE_CATALOG: {sorted(missing)}"
        )

    def test_all_react_optional_file_gating_modules_are_ready(self) -> None:
        """Gating modules should be public-ready so apply accepts them by default."""
        ready_names = {entry.name for entry in MODULE_CATALOG if entry.ready}
        gating_modules = set(REACT_THEME_OPTIONAL_FILES.values())

        not_ready = gating_modules - ready_names
        assert not not_ready, (
            "REACT_THEME_OPTIONAL_FILES references gating modules that are "
            f"not public-ready: {sorted(not_ready)}"
        )

    def test_react_optional_files_values_match_module_catalog(self) -> None:
        """Spot-check that known gating values line up with catalog entries."""
        expected_subset = {"blog", "crm", "forms", "listings", "social"}
        actual = set(REACT_THEME_OPTIONAL_FILES.values())
        assert expected_subset.issubset(actual), (
            f"Expected {sorted(expected_subset)} to gate React optional files; "
            f"actual gating modules: {sorted(actual)}"
        )


class TestSelectedModulesReactTheme:
    """Verify React theme honours ``selected_modules`` for per-module output."""

    def test_default_selected_modules_emits_all_per_module_surfaces(
        self, tmp_path: Path
    ) -> None:
        """When ``selected_modules`` is not provided every optional surface is rendered."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_default_modules"
        generator.generate("react_default_modules", output_path)

        for rel_path in REACT_THEME_OPTIONAL_FILES:
            absolute = output_path / "frontend" / rel_path
            assert absolute.exists(), (
                f"Expected default React theme to render {rel_path} when "
                "selected_modules is not provided."
            )

    def test_empty_selected_modules_drops_every_optional_react_file(
        self, tmp_path: Path
    ) -> None:
        """An empty ``selected_modules`` list should drop every optional React file."""
        generator = ProjectGenerator(theme="showcase_react", selected_modules=[])
        output_path = tmp_path / "react_empty_modules"
        generator.generate("react_empty_modules", output_path)

        for rel_path in REACT_THEME_OPTIONAL_FILES:
            absolute = output_path / "frontend" / rel_path
            assert not absolute.exists(), (
                f"Optional React file {rel_path} should not be generated when "
                "selected_modules is empty."
            )

        # Core pages that are not module-gated must still be present so the
        # generated app remains usable with no modules selected.
        for rel_path in (
            "frontend/src/pages/Dashboard.tsx",
            "frontend/src/pages/SettingsPage.tsx",
            "frontend/src/pages/ProfilePage.tsx",
            "frontend/src/pages/NotFound.tsx",
        ):
            assert (output_path / rel_path).exists(), (
                f"Core page {rel_path} must still be generated."
            )

    def test_partial_selected_modules_keeps_only_requested_surfaces(
        self, tmp_path: Path
    ) -> None:
        """Only the requested modules should keep their per-module React surface."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm"]
        )
        output_path = tmp_path / "react_blog_crm"
        generator.generate("react_blog_crm", output_path)

        # Selected modules keep their page files
        assert (output_path / "frontend" / "src" / "pages" / "BlogPage.tsx").exists()
        assert (output_path / "frontend" / "src" / "pages" / "CrmPage.tsx").exists()

        # Unselected modules drop their gated files
        for rel_path, gating_module in REACT_THEME_OPTIONAL_FILES.items():
            if gating_module in {"blog", "crm"}:
                continue
            absolute = output_path / "frontend" / rel_path
            assert not absolute.exists(), (
                f"Optional file {rel_path} (gated by '{gating_module}') should "
                "not be generated when the module is unselected."
            )

    def test_use_modules_interface_reflects_selected_modules(
        self, tmp_path: Path
    ) -> None:
        """TypeScript interface entries in ``useModules`` should match the selection."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm", "billing"]
        )
        output_path = tmp_path / "react_use_modules"
        generator.generate("react_use_modules", output_path)

        use_modules = (
            output_path / "frontend" / "src" / "hooks" / "useModules.ts"
        ).read_text()

        modules_block = use_modules.split("interface QuickScaleModules {", 1)[1].split(
            "\n}", 1
        )[0]
        module_paths_block = use_modules.split("interface QuickScaleModulePaths {", 1)[
            1
        ].split("\n}", 1)[0]

        for module_key in ("blog", "crm", "billing"):
            assert f"{module_key}: boolean" in modules_block, (
                f"Selected module '{module_key}' missing from QuickScaleModules."
            )
        for module_key in (
            "auth",
            "listings",
            "forms",
            "storage",
            "backups",
            "notifications",
            "analytics",
            "social",
        ):
            assert f"{module_key}: boolean" not in modules_block, (
                f"Unselected module '{module_key}' should be absent from "
                "QuickScaleModules."
            )

        assert "crm: string" in module_paths_block
        assert "billing: string" in module_paths_block
        assert "social: string" not in module_paths_block

    def test_app_tsx_routes_only_emit_selected_module_paths(
        self, tmp_path: Path
    ) -> None:
        """Routes, imports, and legacy redirects in App.tsx should be module-aware."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm"]
        )
        output_path = tmp_path / "react_app_routes"
        generator.generate("react_app_routes", output_path)

        app_tsx = (output_path / "frontend" / "src" / "App.tsx").read_text()

        for kept in ("BlogPage", "CrmPage", 'path="/blog"', 'path="/crm"'):
            assert kept in app_tsx, (
                f"Expected App.tsx to reference {kept} for selected modules."
            )
        for dropped in (
            "ListingsPage",
            "FormsPage",
            'path="/listings"',
            'path="/forms"',
        ):
            assert dropped not in app_tsx, (
                f"App.tsx should not reference {dropped} when modules are not selected."
            )

    def test_sidebar_nav_reflects_selected_modules(self, tmp_path: Path) -> None:
        """Sidebar nav items should follow the same module selection rules."""
        generator = ProjectGenerator(theme="showcase_react", selected_modules=["blog"])
        output_path = tmp_path / "react_sidebar"
        generator.generate("react_sidebar", output_path)

        sidebar = (
            output_path / "frontend" / "src" / "components" / "layout" / "Sidebar.tsx"
        ).read_text()

        assert "name: 'Blog'" in sidebar
        for dropped in (
            "name: 'Listings'",
            "name: 'CRM'",
            "name: 'Forms'",
            "name: 'Billing'",
            "name: 'Social'",
        ):
            assert dropped not in sidebar, (
                f"Sidebar should not include {dropped} when its module is unselected."
            )

    def test_window_module_config_matches_selected_modules(
        self, tmp_path: Path
    ) -> None:
        """The Django-rendered React index.html should only include selected modules."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm"]
        )
        output_path = tmp_path / "react_window_config"
        generator.generate("react_window_config", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        window_config = index_html.split("window.__QUICKSCALE__ = {", 1)[1].split(
            "};", 1
        )[0]

        # Modules block only includes the selected keys
        for kept in ("blog:", "crm:"):
            assert kept in window_config, (
                f"window.__QUICKSCALE__.modules should reference {kept}."
            )
        for dropped in (
            "auth:",
            "listings:",
            "forms:",
            "storage:",
            "backups:",
            "notifications:",
            "analytics:",
            "billing:",
            "social:",
        ):
            assert dropped not in window_config, (
                f"window.__QUICKSCALE__.modules should not reference {dropped}."
            )

        # modulePaths block keeps CRM only
        assert "crm:" in window_config.split("modulePaths:", 1)[1]


class TestSharedAdminTemplates:
    """Both themes should reuse the consolidated admin override templates."""

    @pytest.mark.parametrize("theme", ["showcase_html", "showcase_react"])
    def test_both_themes_render_shared_admin_overrides(
        self, tmp_path: Path, theme: str
    ) -> None:
        """Admin index and app_index templates should appear for both themes."""
        generator = ProjectGenerator(theme=theme)
        output_path = tmp_path / f"{theme}_admin_shared"
        generator.generate(f"{theme}_admin_shared", output_path)

        for rel_template in REACT_THEME_SHARED_DJANGO_TEMPLATES:
            output_rel = Path(rel_template).with_suffix("")  # Strip .j2
            assert (output_path / output_rel).exists(), (
                f"Expected shared Django template {rel_template} to render to "
                f"{output_rel} for theme {theme}."
            )

    @pytest.mark.parametrize("theme", ["showcase_html", "showcase_react"])
    def test_shared_admin_templates_live_in_root_templates_dir(
        self, tmp_path: Path, theme: str
    ) -> None:
        """The source admin templates should live once in the shared location."""
        generator = ProjectGenerator(theme=theme)
        template_dir = generator.template_dir

        shared_admin_dir = template_dir / "templates" / "admin"
        assert (shared_admin_dir / "index.html.j2").exists()
        assert (shared_admin_dir / "app_index.html.j2").exists()

        # Theme directories should not keep duplicate admin copies.
        for theme_name in ("showcase_html", "showcase_react"):
            theme_admin_dir = (
                template_dir / "themes" / theme_name / "templates" / "admin"
            )
            assert not theme_admin_dir.exists(), (
                f"Theme {theme_name} should not have its own admin template "
                "directory after consolidation."
            )

    @pytest.mark.parametrize("theme", ["showcase_html", "showcase_react"])
    def test_admin_override_content_survives_consolidation(
        self, tmp_path: Path, theme: str
    ) -> None:
        """Generated admin templates should preserve the backup-ops behavior."""
        generator = ProjectGenerator(theme=theme)
        output_path = tmp_path / f"{theme}_admin_content"
        generator.generate(f"{theme}_admin_content", output_path)

        admin_index = (output_path / "templates" / "admin" / "index.html").read_text()
        app_index = (output_path / "templates" / "admin" / "app_index.html").read_text()

        assert "Create backup now" not in admin_index
        assert "Open backup ops" in admin_index
        assert 'app.app_label == "quickscale_modules_backups"' in admin_index
        assert (
            'action="/admin/quickscale_modules_backups/backuppolicy/ops/create/"'
            in app_index
        )
        assert "Open backup ops" in app_index
        assert 'app_label == "quickscale_modules_backups"' in app_index
