"""Tests for theme system functionality"""

from pathlib import Path

import pytest

from quickscale_core.generator import ProjectGenerator
from quickscale_core.generator.generator import (
    REACT_THEME_SHARED_DJANGO_TEMPLATES,
)


class TestThemeInitialization:
    """Test theme parameter initialization"""

    def test_default_theme(self, tmp_path: Path) -> None:
        """Generator should use showcase_react as default theme"""
        generator = ProjectGenerator()
        assert generator.theme == "showcase_react"

    def test_invalid_theme_name(self, tmp_path: Path) -> None:
        """Generator should reject invalid theme names"""
        with pytest.raises(ValueError, match="Invalid theme 'invalid_theme'"):
            ProjectGenerator(theme="invalid_theme")

    def test_available_themes_list(self, tmp_path: Path) -> None:
        """Error message should list available themes (only showcase_react remains)"""
        with pytest.raises(ValueError, match="Available themes"):
            ProjectGenerator(theme="nonexistent")

    def test_showcase_html_is_rejected(self) -> None:
        """showcase_html should be rejected as a retired theme."""
        with pytest.raises(ValueError, match="showcase_html"):
            ProjectGenerator(theme="showcase_html")


class TestThemeValidation:
    """Test theme directory validation"""

    def test_htmx_theme_is_not_supported(self) -> None:
        """showcase_htmx should be rejected as an unsupported theme."""
        with pytest.raises(ValueError, match="showcase_htmx"):
            ProjectGenerator(theme="showcase_htmx")

    def test_react_theme_directory_exists(self) -> None:
        """showcase_react theme directory should exist"""
        generator = ProjectGenerator(theme="showcase_react")
        theme_dir = generator.template_dir / "themes" / "showcase_react"
        assert theme_dir.exists()


class TestThemeTemplateResolution:
    """Test theme-specific template path resolution"""

    def test_common_template_fallback(self) -> None:
        """_get_theme_template_path should fall back to common templates"""
        generator = ProjectGenerator(theme="showcase_react")

        # This template lives in common/templates/admin/ (not in any theme dir),
        # so _get_theme_template_path should resolve it via the common fallback.
        path = generator._get_theme_template_path("templates/admin/index.html.j2")
        assert "common" in path
        assert "index.html.j2" in path


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

    def test_generated_makefile_respects_frontend_presence(
        self,
        tmp_path: Path,
    ) -> None:
        """Generated Makefile should include frontend targets for React theme."""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "testproject_react"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        makefile = (output_path / "Makefile").read_text()

        assert (output_path / "frontend" / "package.json").exists()
        assert "cd frontend && pnpm test:coverage;" in makefile

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


class TestSelectedModulesReactTheme:
    """Verify that SA105 removed selected_modules-driven frontend source omission.

    After SA105, all module source files are emitted as dormant files regardless
    of the selected_modules parameter. Runtime gating via window.__QUICKSCALE__.
    """

    OPTIONAL_REL_PATHS: tuple[str, ...] = (
        "src/pages/BlogPage.tsx",
        "src/pages/CrmPage.tsx",
        "src/pages/FormsPage.tsx",
        "src/pages/ListingsPage.tsx",
        "src/pages/SocialLinkTreePublicPage.tsx",
        "src/pages/SocialEmbedsPublicPage.tsx",
        "src/components/forms/FormRenderer.tsx",
        "src/components/forms/FormFieldRenderer.tsx",
        "src/components/forms/FormSuccess.tsx",
        "src/hooks/useFormSchema.ts",
    )

    # Authoritative path-to-module mapping for dormant files.
    PATH_TO_MODULE: dict[str, str] = {
        "src/pages/BlogPage.tsx": "blog",
        "src/pages/CrmPage.tsx": "crm",
        "src/pages/FormsPage.tsx": "forms",
        "src/pages/ListingsPage.tsx": "listings",
        "src/pages/SocialLinkTreePublicPage.tsx": "social",
        "src/pages/SocialEmbedsPublicPage.tsx": "social",
        "src/components/forms/FormRenderer.tsx": "forms",
        "src/components/forms/FormFieldRenderer.tsx": "forms",
        "src/components/forms/FormSuccess.tsx": "forms",
        "src/hooks/useFormSchema.ts": "forms",
    }

    # Expected first-line banner for each dormant file.
    # Each banner is module-specific, static (no Jinja interpolation), and
    # explains the file is inert unless the corresponding module flag is true
    # at runtime — React.lazy-loaded, tree-shaken when unused, safe to leave.
    _BANNER_PREFIX_BLOG = "// DORMANT: Blog module surface. Inert unless modules.blog is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."
    _BANNER_PREFIX_CRM = "// DORMANT: CRM module surface. Inert unless modules.crm is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."
    _BANNER_PREFIX_FORMS = "// DORMANT: Forms module surface. Inert unless modules.forms is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."
    _BANNER_PREFIX_LISTINGS = "// DORMANT: Listings module surface. Inert unless modules.listings is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."
    _BANNER_PREFIX_SOCIAL_LINK_TREE = "// DORMANT: Social link-tree surface. Inert unless modules.social is true and publicPage.surface === 'link_tree' at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."
    _BANNER_PREFIX_SOCIAL_EMBEDS = "// DORMANT: Social embeds surface. Inert unless modules.social is true and publicPage.surface === 'embeds' at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."
    _BANNER_PREFIX_FORMS_COMPONENT = "// DORMANT: Forms module component. Inert unless modules.forms is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."
    _BANNER_PREFIX_FORMS_HOOK = "// DORMANT: Forms module hook. Inert unless modules.forms is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant."

    BANNER_PREFIXES: dict[str, str] = {
        "src/pages/BlogPage.tsx": _BANNER_PREFIX_BLOG,
        "src/pages/CrmPage.tsx": _BANNER_PREFIX_CRM,
        "src/pages/FormsPage.tsx": _BANNER_PREFIX_FORMS,
        "src/pages/ListingsPage.tsx": _BANNER_PREFIX_LISTINGS,
        "src/pages/SocialLinkTreePublicPage.tsx": _BANNER_PREFIX_SOCIAL_LINK_TREE,
        "src/pages/SocialEmbedsPublicPage.tsx": _BANNER_PREFIX_SOCIAL_EMBEDS,
        "src/components/forms/FormRenderer.tsx": _BANNER_PREFIX_FORMS_COMPONENT,
        "src/components/forms/FormFieldRenderer.tsx": _BANNER_PREFIX_FORMS_COMPONENT,
        "src/components/forms/FormSuccess.tsx": _BANNER_PREFIX_FORMS_COMPONENT,
        "src/hooks/useFormSchema.ts": _BANNER_PREFIX_FORMS_HOOK,
    }

    def test_default_selected_modules_emits_all_dormant_surfaces(
        self, tmp_path: Path
    ) -> None:
        """When ``selected_modules`` is not provided every module surface is rendered."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_default_modules"
        generator.generate("react_default_modules", output_path)

        for rel_path in self.OPTIONAL_REL_PATHS:
            absolute = output_path / "frontend" / rel_path
            assert absolute.exists(), (
                f"Expected default React theme to render {rel_path}."
            )

    def test_empty_selected_modules_emits_all_dormant_files(
        self, tmp_path: Path
    ) -> None:
        """After SA105, an empty ``selected_modules`` list still emits all module files as dormant."""
        generator = ProjectGenerator(theme="showcase_react", selected_modules=[])
        output_path = tmp_path / "react_empty_modules"
        generator.generate("react_empty_modules", output_path)

        # All optional files are emitted as dormant files regardless of selection
        for rel_path in self.OPTIONAL_REL_PATHS:
            absolute = output_path / "frontend" / rel_path
            assert absolute.exists(), (
                f"Dormant file {rel_path} should be generated even when "
                "selected_modules is empty after SA105."
            )

        # All modules appear in the QuickScaleModules interface
        use_modules = (
            output_path / "frontend" / "src" / "hooks" / "useModules.ts"
        ).read_text()
        modules_interface = use_modules.split("interface QuickScaleModules {", 1)[
            1
        ].split("\n}", 1)[0]
        for module_key in ("auth", "blog", "crm", "listings", "social", "analytics"):
            assert f"{module_key}: boolean" in modules_interface, (
                f"Module '{module_key}' must appear in QuickScaleModules after SA105."
            )

        # QuickScaleModulePaths includes all known paths
        module_paths_interface = use_modules.split(
            "interface QuickScaleModulePaths {", 1
        )[1].split("\n}", 1)[0]
        assert "crm: string" in module_paths_interface
        assert "social: string" in module_paths_interface
        assert "analytics: string" in module_paths_interface

        # Core pages are always generated
        for rel_path in (
            "frontend/src/pages/Dashboard.tsx",
            "frontend/src/pages/SettingsPage.tsx",
            "frontend/src/pages/ProfilePage.tsx",
            "frontend/src/pages/NotFound.tsx",
        ):
            assert (output_path / rel_path).exists(), (
                f"Core page {rel_path} must still be generated."
            )

    def test_partial_selected_modules_also_emits_dormant_files(
        self, tmp_path: Path
    ) -> None:
        """After SA105, partial selection still emits all dormant module files."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm"]
        )
        output_path = tmp_path / "react_blog_crm"
        generator.generate("react_blog_crm", output_path)

        # All module pages exist as dormant files
        for rel_path in self.OPTIONAL_REL_PATHS:
            absolute = output_path / "frontend" / rel_path
            assert absolute.exists(), (
                f"Optional file {rel_path} should be generated as dormant "
                "regardless of selected_modules after SA105."
            )

    def test_use_modules_interface_always_all_modules(self, tmp_path: Path) -> None:
        """After SA105, QuickScaleModules always includes every module."""
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

        # All modules always present in the interface
        for module_key in (
            "auth",
            "blog",
            "crm",
            "listings",
            "forms",
            "storage",
            "backups",
            "notifications",
            "analytics",
            "billing",
            "social",
        ):
            assert f"{module_key}: boolean" in modules_block, (
                f"Module '{module_key}' must always appear in QuickScaleModules after SA105."
            )

        # All known module paths are always present
        assert "crm: string" in module_paths_block
        assert "social: string" in module_paths_block
        assert "analytics: string" in module_paths_block
        # D1 Option B: billing path removed from module paths until session-sync contract exists
        assert "billing: string" not in module_paths_block

    def test_always_all_modules_in_default_config_and_interface(
        self, tmp_path: Path
    ) -> None:
        """After SA105, all modules are unconditionally typed and defaulted."""
        # --- Empty selection ---
        empty_gen = ProjectGenerator(theme="showcase_react", selected_modules=[])
        empty_out = tmp_path / "react_all_modules_empty"
        empty_gen.generate("react_all_modules_empty", empty_out)

        empty_modules = (
            empty_out / "frontend" / "src" / "hooks" / "useModules.ts"
        ).read_text()

        modules_iface = empty_modules.split("interface QuickScaleModules {", 1)[
            1
        ].split("\n}", 1)[0]
        for module_key in ("auth", "blog", "crm", "listings", "analytics"):
            assert f"{module_key}: boolean" in modules_iface, (
                f"Module '{module_key}' must be typed in QuickScaleModules "
                "even when selected_modules=[] after SA105."
            )

        # After SA107, defaultConfig is removed — validation is fail-hard at runtime.

    def test_app_tsx_always_includes_all_imports_and_routes(
        self, tmp_path: Path
    ) -> None:
        """After SA105, App.tsx uses React.lazy for module pages and gates routes on runtime flags."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm"]
        )
        output_path = tmp_path / "react_app_routes"
        generator.generate("react_app_routes", output_path)

        app_tsx = (output_path / "frontend" / "src" / "App.tsx").read_text()

        # Module pages use React.lazy (dynamic import, not static import)
        for page in ("BlogPage", "CrmPage", "ListingsPage", "FormsPage"):
            assert f"const {page} = lazy(() => import(" in app_tsx, (
                f"App.tsx should use React.lazy for {page} after SA105."
            )
        # Core pages are still statically imported
        assert "import { Dashboard }" in app_tsx
        assert "import { NotFound }" in app_tsx
        assert "import { SettingsPage }" in app_tsx
        assert "import { ProfilePage }" in app_tsx

        # Routes are conditionally gated with runtime flags
        assert '{modules.blog && <Route path="/blog"' in app_tsx
        assert '{modules.crm && <Route path="/crm"' in app_tsx
        assert '{modules.listings && <Route path="/listings"' in app_tsx
        assert '{modules.forms && <Route path="/forms"' in app_tsx

        # Suspense wrapper is used
        assert "<Suspense fallback={<div>Loading…</div>}>" in app_tsx

        # useModules hook is imported
        assert "useModules" in app_tsx

    def test_sidebar_always_includes_all_nav_items(self, tmp_path: Path) -> None:
        """After SA105, all nav items are always present (runtime gating via modules.* flags)."""
        generator = ProjectGenerator(theme="showcase_react", selected_modules=["blog"])
        output_path = tmp_path / "react_sidebar"
        generator.generate("react_sidebar", output_path)

        sidebar = (
            output_path / "frontend" / "src" / "components" / "layout" / "Sidebar.tsx"
        ).read_text()

        # All nav items always present in the template
        assert "name: 'Blog'" in sidebar
        assert "name: 'Listings'" in sidebar
        assert "name: 'CRM'" in sidebar
        assert "name: 'Forms'" in sidebar
        assert "name: 'Social'" in sidebar
        # Billing nav entry excluded (D1 Option B)
        assert "name: 'Billing'" not in sidebar

    def test_social_imports_and_render_always_present(self, tmp_path: Path) -> None:
        """After SA105, renderQuickScaleRoot is imported from the extracted seam."""
        # --- Empty selection still has social dispatch ---
        empty_gen = ProjectGenerator(theme="showcase_react", selected_modules=[])
        empty_out = tmp_path / "react_no_social_main"
        empty_gen.generate("react_no_social_main", empty_out)

        empty_main = (empty_out / "frontend" / "src" / "main.tsx").read_text()

        # main.tsx imports renderQuickScaleRoot from the extracted seam
        assert (
            "import { renderQuickScaleRoot } from './renderQuickScaleRoot'"
            in empty_main
        ), "main.tsx must import renderQuickScaleRoot from extracted seam after SA105."

        # renderQuickScaleRoot is used in the render tree with surface
        # After SA107, surface is read from the validated config, not directly from the seam.
        assert (
            "renderQuickScaleRoot(quickScaleConfig.publicPage?.surface)" in empty_main
        ), "renderQuickScaleRoot must be called with surface from validated config."

    def test_window_config_always_includes_all_modules(self, tmp_path: Path) -> None:
        """After SA105, the Django-rendered index.html always emits all module flags."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm"]
        )
        output_path = tmp_path / "react_window_config"
        generator.generate("react_window_config", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        window_config = index_html.split("window.__QUICKSCALE__ = {", 1)[1].split(
            "};", 1
        )[0]

        # All modules are always listed
        for module in (
            "auth:",
            "blog:",
            "crm:",
            "listings:",
            "forms:",
            "storage:",
            "backups:",
            "notifications:",
            "analytics:",
            "billing:",
            "social:",
        ):
            assert module in window_config, (
                f"window.__QUICKSCALE__.modules should reference {module} after SA105."
            )

        # modulePaths block always has all paths
        module_paths_section = window_config.split("modulePaths:", 1)[1]
        assert "crm:" in module_paths_section
        assert "social:" in module_paths_section
        assert "analytics:" in module_paths_section

    # ── Dormant-file banner verification ───────────────────────────────

    def test_generated_dormant_file_banners(self, tmp_path: Path) -> None:
        """Every generated dormant file starts with its module-specific banner."""
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["blog", "crm"]
        )
        output_path = tmp_path / "react_banners"
        generator.generate("react_banners", output_path)

        for rel_path, expected_banner in self.BANNER_PREFIXES.items():
            absolute = output_path / "frontend" / rel_path
            assert absolute.exists(), f"Expected dormant file {rel_path} to exist."
            first_line = absolute.read_text().splitlines()[0]
            assert first_line == expected_banner, (
                f"File {rel_path} expected first-line banner:\n"
                f"  {expected_banner!r}\n"
                f"  got {first_line!r}"
            )

    def test_dormant_file_byte_identity_across_selections(self, tmp_path: Path) -> None:
        """Dormant files are byte-identical regardless of selected_modules."""
        selections = [
            (None, "default"),
            ([], "empty"),
            (["blog", "crm"], "partial"),
        ]
        variants: dict[str, dict[str, bytes]] = {}

        for selected_modules, label in selections:
            gen = ProjectGenerator(
                theme="showcase_react", selected_modules=selected_modules
            )
            out = tmp_path / f"react_byte_id_{label}"
            gen.generate(f"react_byte_id_{label}", out)
            files: dict[str, bytes] = {}
            for rel_path in self.OPTIONAL_REL_PATHS:
                files[rel_path] = (out / "frontend" / rel_path).read_bytes()
            variants[label] = files

        # All variants must produce identical byte content for every dormant file
        baseline = variants["default"]
        for label, files in variants.items():
            for rel_path in self.OPTIONAL_REL_PATHS:
                assert files[rel_path] == baseline[rel_path], (
                    f"Dormant file {rel_path} differs between selected_modules="
                    f"{label!r} and selected_modules=None (baseline)."
                )

    # ── Static main.tsx source-shape assertions ───────────────────────
    # Moved from test_templates.py TestSelectedModulesTemplateSafety (SA105).

    _MAIN_REACT_LAZY_PAGES = {
        "SocialEmbedsPublicPage",
        "SocialLinkTreePublicPage",
    }

    def test_generated_main_tsx_imports_render_quick_scale_root(
        self, tmp_path: Path
    ) -> None:
        """After SA105, generated main.tsx imports renderQuickScaleRoot from the extracted seam."""
        generator = ProjectGenerator(theme="showcase_react", selected_modules=[])
        output_path = tmp_path / "react_main_src"
        generator.generate("react_main_src", output_path)

        content = (output_path / "frontend" / "src" / "main.tsx").read_text()

        # Imports from the extracted seam
        assert (
            "import { renderQuickScaleRoot } from './renderQuickScaleRoot'" in content
        ), (
            "Generated main.tsx must import renderQuickScaleRoot from the extracted seam."
        )
        # Uses it with surface (from validated config after SA107)
        assert (
            "renderQuickScaleRoot(quickScaleConfig.publicPage?.surface)" in content
        ), (
            "Generated main.tsx must call renderQuickScaleRoot with surface from validated config."
        )
        # No inline lazy social variable declarations remain in main.tsx
        assert "const SocialEmbedsPublicPage" not in content, (
            "Generated main.tsx must not define lazy social imports inline."
        )
        assert "const SocialLinkTreePublicPage" not in content, (
            "Generated main.tsx must not define lazy social imports inline."
        )

    def test_generated_render_quick_scale_root_tsx_social_lazy_imports(
        self, tmp_path: Path
    ) -> None:
        """Generated renderQuickScaleRoot.tsx has lazy imports and dispatch logic."""
        generator = ProjectGenerator(theme="showcase_react", selected_modules=[])
        output_path = tmp_path / "react_root_dispatch"
        generator.generate("react_root_dispatch", output_path)

        content = (
            output_path / "frontend" / "src" / "renderQuickScaleRoot.tsx"
        ).read_text()

        # React.lazy used for social pages
        for page in self._MAIN_REACT_LAZY_PAGES:
            assert f"const {page} = lazy(() => import(" in content, (
                f"renderQuickScaleRoot.tsx must use React.lazy for {page} after SA105."
            )
            assert ".then((m) => ({ default: m." in content, (
                "renderQuickScaleRoot.tsx must use the then/default pattern for lazy imports."
            )

        # Surface dispatch logic
        assert (
            "function renderQuickScaleRoot(surface?: PublicSocialSurface)" in content
        ), "renderQuickScaleRoot must take the surface parameter."
        assert (
            "const Page = surface === 'link_tree' ? SocialLinkTreePublicPage : SocialEmbedsPublicPage"
            in content
        ), "renderQuickScaleRoot must dispatch based on surface value."
        assert "<Suspense fallback={<div>Loading…</div>}>" in content, (
            "renderQuickScaleRoot must wrap lazy pages in Suspense."
        )


class TestSharedAdminTemplates:
    """Both themes should reuse the consolidated admin override templates."""

    def test_react_missing_shared_template_not_in_mapping(self, tmp_path: Path) -> None:
        """A missing template file simply won't appear in the emission mapping.

        With the SA90 mapping-driven approach, templates are discovered via
        filesystem enumeration, not hardcoded lists, so a missing file is
        simply absent from the mapping and never rendered.
        """
        # The mapping for the React theme should NOT include a path for a
        # nonexistent template — it will be absent without error.
        from pathlib import Path

        import quickscale_core
        from quickscale_core.generator import get_generator_emission_mapping

        template_dir = Path(quickscale_core.__file__).parent / "generator" / "templates"
        mapping = get_generator_emission_mapping(template_dir, theme="showcase_react")

        # A nonexistent template path is simply absent from the mapping
        assert "templates/admin/nonexistent_template.html" not in mapping

    def test_react_theme_renders_shared_admin_overrides(self, tmp_path: Path) -> None:
        """Admin index and app_index templates should appear for React theme."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_admin_shared"
        generator.generate("react_admin_shared", output_path)

        for rel_template in REACT_THEME_SHARED_DJANGO_TEMPLATES:
            output_rel = Path(rel_template).with_suffix("")  # Strip .j2
            assert (output_path / output_rel).exists(), (
                f"Expected shared Django template {rel_template} to render to "
                f"{output_rel} for theme showcase_react."
            )

    def test_shared_admin_templates_live_in_root_templates_dir(
        self, tmp_path: Path
    ) -> None:
        """The source admin templates should live once in the shared location."""
        generator = ProjectGenerator(theme="showcase_react")
        template_dir = generator.template_dir

        shared_admin_dir = template_dir / "templates" / "admin"
        assert (shared_admin_dir / "index.html.j2").exists()
        assert (shared_admin_dir / "app_index.html.j2").exists()

        # Theme directory should not keep duplicate admin copies.
        theme_admin_dir = (
            template_dir / "themes" / "showcase_react" / "templates" / "admin"
        )
        assert not theme_admin_dir.exists(), (
            "Theme showcase_react should not have its own admin template "
            "directory after consolidation."
        )

    def test_admin_override_content_survives_consolidation(
        self, tmp_path: Path
    ) -> None:
        """Generated admin templates should preserve the backup-ops behavior."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_admin_content"
        generator.generate("react_admin_content", output_path)

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
