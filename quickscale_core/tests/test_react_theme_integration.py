"""Integration tests for React theme (showcase_react)

These tests verify the complete React theme generation workflow including:
- Frontend file structure
- Package.json configuration
- TypeScript configuration
- shadcn/ui setup
- Build compatibility
"""

import json

import pytest

from quickscale_core.generator import ProjectGenerator


@pytest.mark.integration
class TestReactThemeGeneration:
    """Test complete React theme project generation"""

    def test_react_theme_generates_complete_frontend_structure(self, tmp_path):
        """React theme should generate complete frontend structure"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_integration_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        frontend_path = output_path / "frontend"

        # Core frontend files
        assert (frontend_path / "package.json").exists()
        assert (frontend_path / "vite.config.ts").exists()
        assert (frontend_path / "tsconfig.json").exists()
        assert (frontend_path / "tailwind.config.js").exists()
        assert (frontend_path / "postcss.config.js").exists()
        assert (frontend_path / "components.json").exists()

        # Source structure
        assert (frontend_path / "src" / "main.tsx").exists()
        assert (frontend_path / "src" / "App.tsx").exists()
        assert (frontend_path / "src" / "index.css").exists()

        # Components directory
        assert (frontend_path / "src" / "components").is_dir()

        # shadcn/ui lib utilities
        assert (frontend_path / "src" / "lib" / "utils.ts").exists()

    def test_react_theme_package_json_has_required_dependencies(self, tmp_path):
        """Package.json should have all required dependencies"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_deps_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        package_json_path = output_path / "frontend" / "package.json"
        assert package_json_path.exists()

        with open(package_json_path) as f:
            package = json.load(f)

        # Core React dependencies
        deps = package.get("dependencies", {})
        assert "react" in deps
        assert "react-dom" in deps
        assert "react-router-dom" in deps

        # State management
        assert "@tanstack/react-query" in deps
        assert "zustand" in deps

        # UI dependencies (shadcn/ui stack)
        assert "class-variance-authority" in deps
        assert "clsx" in deps
        assert "tailwind-merge" in deps
        assert "lucide-react" in deps

        # Forms
        assert "react-hook-form" in deps
        assert "@hookform/resolvers" in deps
        assert "zod" in deps

        # Animation
        assert "motion" in deps

        # Dev dependencies
        dev_deps = package.get("devDependencies", {})
        assert "typescript" in dev_deps
        assert "vite" in dev_deps
        assert "@vitejs/plugin-react" in dev_deps
        assert "vitest" in dev_deps
        assert "@playwright/test" in dev_deps
        assert "tailwindcss" in dev_deps

    def test_react_theme_vite_config_correct(self, tmp_path):
        """Vite config should have correct settings for Django integration"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_vite_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        vite_config = (output_path / "frontend" / "vite.config.ts").read_text()

        # Should use React plugin
        assert "@vitejs/plugin-react" in vite_config
        assert "react()" in vite_config

        # Should have build output configured for Django
        assert "outDir" in vite_config or "build" in vite_config

        # Should have consistent filenames for Django static files
        assert "entryFileNames" in vite_config
        assert "assetFileNames" in vite_config

    def test_react_theme_tsconfig_correct(self, tmp_path):
        """TypeScript config should have correct settings"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_ts_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        tsconfig_path = output_path / "frontend" / "tsconfig.json"
        assert tsconfig_path.exists()

        content = tsconfig_path.read_text()

        # Should have strict mode enabled
        assert '"strict": true' in content or '"strict":true' in content

        # Should have JSX support
        assert '"jsx"' in content
        assert "react" in content.lower()

        # Should have path aliases
        assert '"paths"' in content or '"baseUrl"' in content

    def test_react_theme_shadcn_components_json_correct(self, tmp_path):
        """components.json should have correct shadcn/ui configuration"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_shadcn_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        components_json_path = output_path / "frontend" / "components.json"
        assert components_json_path.exists()

        with open(components_json_path) as f:
            components = json.load(f)

        # Should have style configured
        assert "style" in components

        # Should have aliases configured
        assert "aliases" in components

    def test_react_theme_django_template_configured(self, tmp_path):
        """Django template should be configured to serve React app"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_django_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check Django template exists
        index_html = output_path / "templates" / "index.html"
        assert index_html.exists()

        content = index_html.read_text()

        # Should use Django static tags
        assert "{% load static %}" in content

        # Should reference built frontend assets
        assert "static" in content
        assert "frontend" in content

    def test_react_theme_dockerfile_includes_frontend_build(self, tmp_path):
        """Dockerfile should include frontend build stage"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_docker_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        dockerfile = (output_path / "Dockerfile").read_text()

        # Should have node build stage
        assert "node" in dockerfile.lower()

        # Should build frontend
        assert "npm" in dockerfile or "pnpm" in dockerfile

        # Should copy built assets
        assert "staticfiles" in dockerfile or "static" in dockerfile

    def test_react_theme_scripts_configured(self, tmp_path):
        """Package.json scripts should be properly configured"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_scripts_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        with open(output_path / "frontend" / "package.json") as f:
            package = json.load(f)

        scripts = package.get("scripts", {})

        # Essential scripts
        assert "dev" in scripts
        assert "build" in scripts
        assert "test" in scripts
        assert "lint" in scripts

        # Dev script should use vite
        assert "vite" in scripts["dev"]

        # Build script should include TypeScript check
        assert "tsc" in scripts["build"] or "typescript" in scripts["build"]


@pytest.mark.integration
class TestReactThemeRadixUIComponents:
    """Test Radix UI component dependencies"""

    def test_radix_ui_components_included(self, tmp_path):
        """Required Radix UI components should be in dependencies"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_radix_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        with open(output_path / "frontend" / "package.json") as f:
            package = json.load(f)

        deps = package.get("dependencies", {})

        # Essential Radix UI primitives for shadcn/ui
        radix_components = [
            "@radix-ui/react-slot",
            "@radix-ui/react-dialog",
            "@radix-ui/react-dropdown-menu",
            "@radix-ui/react-label",
            "@radix-ui/react-tabs",
            "@radix-ui/react-toast",
            "@radix-ui/react-tooltip",
        ]

        for component in radix_components:
            assert component in deps, f"Missing Radix UI component: {component}"


@pytest.mark.integration
class TestReactThemeTestingSetup:
    """Test testing infrastructure for React theme"""

    def test_vitest_configured(self, tmp_path):
        """Vitest should be properly configured"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_vitest_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        frontend_path = output_path / "frontend"

        # Vitest should be in dev dependencies
        with open(frontend_path / "package.json") as f:
            package = json.load(f)

        dev_deps = package.get("devDependencies", {})
        assert "vitest" in dev_deps
        assert "@vitest/coverage-v8" in dev_deps

        # Testing library should be present
        assert "@testing-library/react" in dev_deps
        assert "@testing-library/jest-dom" in dev_deps

    def test_playwright_configured(self, tmp_path):
        """Playwright should be configured for E2E tests"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_playwright_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        with open(output_path / "frontend" / "package.json") as f:
            package = json.load(f)

        dev_deps = package.get("devDependencies", {})
        assert "@playwright/test" in dev_deps

        # Test script should exist
        scripts = package.get("scripts", {})
        assert "test:e2e" in scripts


@pytest.mark.integration
class TestReactThemeBaseTemplate:
    """Test base.html template for React theme

    The React theme needs a base.html Django template for server-rendered
    pages (auth module pages, error pages). This prevents TemplateDoesNotExist
    errors when allauth or error handlers render Django templates.
    """

    def test_react_theme_generates_base_html(self, tmp_path):
        """React theme should generate base.html for server-rendered pages"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_base_html_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        base_html = output_path / "templates" / "base.html"
        assert base_html.exists(), (
            "React theme must generate templates/base.html for auth module "
            "and error page compatibility"
        )

    def test_react_base_html_has_required_blocks(self, tmp_path):
        """base.html should provide blocks expected by auth module"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_blocks_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        content = (output_path / "templates" / "base.html").read_text()

        # Auth module base.html extends "base.html" and expects these blocks
        required_blocks = ["title", "extra_css", "content", "extra_js"]
        for block in required_blocks:
            assert f"{{% block {block} %}}" in content, (
                f"base.html missing '{{% block {block} %}}' — "
                f"required by auth module templates"
            )

    def test_react_base_html_is_valid_html(self, tmp_path):
        """base.html should be a valid standalone HTML document"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_html_valid_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        content = (output_path / "templates" / "base.html").read_text()

        assert "<!doctype html>" in content.lower() or "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<head>" in content or "<head " in content
        assert "</head>" in content
        assert "<body>" in content or "<body " in content
        assert "</body>" in content

    def test_react_base_html_has_static_tag(self, tmp_path):
        """base.html should use Django static template tag"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_static_tag_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        content = (output_path / "templates" / "base.html").read_text()
        assert "{% load static %}" in content

    def test_react_base_html_has_messages_support(self, tmp_path):
        """base.html should display Django messages"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_messages_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        content = (output_path / "templates" / "base.html").read_text()
        assert "{% if messages %}" in content
        assert "{% for message in messages %}" in content

    def test_react_base_html_has_back_to_app_link(self, tmp_path):
        """base.html should have navigation back to React app"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_nav_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        content = (output_path / "templates" / "base.html").read_text()
        # Should have a link back to the root (React SPA)
        assert 'href="/"' in content

    def test_error_pages_compatible_with_react_base_html(self, tmp_path):
        """404 and 500 error pages should work with React theme base.html"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_errors_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Both error pages extend base.html
        for error_page in ["404.html", "500.html"]:
            error_path = output_path / "templates" / error_page
            assert error_path.exists(), f"{error_page} should exist"
            content = error_path.read_text()
            assert '{% extends "base.html" %}' in content
            assert "{% block content %}" in content

        # Verify base.html exists so the extends chain works
        assert (output_path / "templates" / "base.html").exists()
