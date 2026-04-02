"""Integration tests for React theme (showcase_react)

These tests verify the complete React theme generation workflow including:
- Frontend file structure
- Package.json configuration
- TypeScript configuration
- shadcn/ui setup
- Build compatibility
"""

import json
import re

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
        assert (frontend_path / ".prettierrc").exists()

        # Source structure
        assert (frontend_path / "src" / "main.tsx").exists()
        assert (frontend_path / "src" / "App.tsx").exists()
        assert (frontend_path / "src" / "index.css").exists()
        assert (frontend_path / "src" / "hooks" / "usePublicSocialSurface.ts").exists()
        assert (
            frontend_path / "src" / "components" / "social" / "PublicSocialShell.tsx"
        ).exists()
        assert (
            frontend_path / "src" / "pages" / "SocialLinkTreePublicPage.tsx"
        ).exists()
        assert (frontend_path / "src" / "pages" / "SocialEmbedsPublicPage.tsx").exists()
        assert (frontend_path / "src" / "test" / "PublicSocialPages.test.tsx").exists()

        # Components directory
        assert (frontend_path / "src" / "components").is_dir()

        # shadcn/ui lib utilities
        assert (frontend_path / "src" / "lib" / "utils.ts").exists()

    def test_react_theme_social_embeds_use_backend_owned_preview_metadata(
        self, tmp_path
    ):
        """Generated social embed pages should consume backend-owned preview fields."""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_social_embed_contract"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        social_hook = (
            output_path / "frontend" / "src" / "hooks" / "usePublicSocialSurface.ts"
        ).read_text()
        embeds_page = (
            output_path / "frontend" / "src" / "pages" / "SocialEmbedsPublicPage.tsx"
        ).read_text()

        assert "resolution_status" in social_hook
        assert "embed_url" in social_hook
        assert "thumbnail_url" in social_hook
        assert "function extractYouTubeVideoId" not in embeds_page
        assert "function extractTikTokVideoId" not in embeds_page
        assert "record.embed_url" in embeds_page
        assert "record.resolution_error" in embeds_page

    def test_react_theme_social_hook_uses_strict_safe_payload_narrowing(self, tmp_path):
        """Generated social hook should avoid unsafe recasts after narrowing payloads."""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_social_type_guard_contract"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        social_hook = (
            output_path / "frontend" / "src" / "hooks" / "usePublicSocialSurface.ts"
        ).read_text()

        social_embed_guard = social_hook.split("function isSocialEmbedRecord", 1)[
            1
        ].split("\nfunction hasBasePayload", 1)[0]
        link_tree_guard = social_hook.split("function isLinkTreePayload", 1)[1].split(
            "\nfunction isEmbedsPayload", 1
        )[0]
        embeds_guard = social_hook.split("function isEmbedsPayload", 1)[1].split(
            "\nasync function fetchPublicSocialPayload", 1
        )[0]

        assert "as Record<string, unknown>" not in social_embed_guard
        assert "'resolution_status' in value" in social_embed_guard
        assert "as Record<string, unknown>" not in link_tree_guard
        assert "'links' in value" in link_tree_guard
        assert "as Record<string, unknown>" not in embeds_guard
        assert "'embeds' in value" in embeds_guard

    def test_react_theme_prettier_config_matches_templates(self, tmp_path):
        """Prettier config should match generated React source style."""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_prettier_config_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        with open(output_path / "frontend" / ".prettierrc") as f:
            config = json.load(f)

        assert config["semi"] is False
        assert config["singleQuote"] is True

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

        package_manager = package.get("packageManager", "")
        assert re.fullmatch(r"pnpm@\d+\.\d+\.\d+", package_manager)

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
        assert "'/_quickscale'" in vite_config
        assert "'/social'" in vite_config

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

        # Should build frontend with canonical package manager
        assert "pnpm" in dockerfile
        assert re.search(r"RUN\\s+npm\\s", dockerfile) is None

        # Should copy built assets
        assert "staticfiles" in dockerfile or "static" in dockerfile
        assert "postgresql-client-18" in dockerfile
        assert "apt.postgresql.org" in dockerfile
        assert "apt.postgresql.org.asc" in dockerfile
        assert "gpg --dearmor" not in dockerfile
        assert "gnupg" not in dockerfile

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


@pytest.mark.integration
class TestReactThemeAuthUrls:
    """Test that React theme auth links match Django auth URL patterns

    The React ProfilePage contains hardcoded <a href> links to Django-served
    auth pages. These must exactly match the URL patterns defined in the auth
    module's urls.py and django-allauth, otherwise users get 404 errors.

    Regression test for: /accounts/account-delete/ vs /accounts/account/delete/
    """

    # URLs from django-allauth mounted at /accounts/
    ALLAUTH_URLS = {
        "/accounts/login/",
        "/accounts/signup/",
        "/accounts/password/change/",
        "/accounts/password/reset/",
    }

    # Custom auth module URLs (from quickscale_modules_auth/urls.py)
    CUSTOM_AUTH_URLS = {
        "/accounts/profile/",
        "/accounts/profile/edit/",
        "/accounts/account/delete/",
    }

    VALID_AUTH_URLS = ALLAUTH_URLS | CUSTOM_AUTH_URLS

    def test_profile_page_auth_urls_are_valid(self, tmp_path):
        """All hardcoded auth URLs in ProfilePage must match Django URL patterns"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_auth_urls_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        profile_page = output_path / "frontend" / "src" / "pages" / "ProfilePage.tsx"
        assert profile_page.exists(), "ProfilePage.tsx should be generated"

        content = profile_page.read_text()

        # Extract all /accounts/ hrefs from the generated file
        hrefs = re.findall(r'href="(/accounts/[^"]+)"', content)
        assert len(hrefs) > 0, "ProfilePage should contain auth links"

        for href in hrefs:
            assert href in self.VALID_AUTH_URLS, (
                f"ProfilePage contains invalid auth URL: {href}\n"
                f"Valid URLs are: {sorted(self.VALID_AUTH_URLS)}"
            )

    def test_account_delete_url_uses_slash_separator(self, tmp_path):
        """Account delete URL must use /account/delete/ not /account-delete/"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_delete_url_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        profile_page = output_path / "frontend" / "src" / "pages" / "ProfilePage.tsx"
        content = profile_page.read_text()

        # The correct URL pattern from auth module urls.py
        assert "/accounts/account/delete/" in content, (
            "ProfilePage must link to /accounts/account/delete/ "
            "(matching auth module URL pattern)"
        )

        # The incorrect hyphenated form must NOT be present
        assert "/accounts/account-delete/" not in content, (
            "ProfilePage must NOT use /accounts/account-delete/ — "
            "the correct URL is /accounts/account/delete/"
        )

    def test_all_expected_auth_links_present(self, tmp_path):
        """ProfilePage should contain links to all essential auth pages"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "react_auth_links_test"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        profile_page = output_path / "frontend" / "src" / "pages" / "ProfilePage.tsx"
        content = profile_page.read_text()

        expected_urls = [
            "/accounts/login/",
            "/accounts/signup/",
            "/accounts/profile/",
            "/accounts/password/change/",
            "/accounts/password/reset/",
            "/accounts/account/delete/",
        ]

        for url in expected_urls:
            assert url in content, f"ProfilePage missing expected auth link: {url}"


@pytest.mark.integration
class TestReactThemeModuleActivationMatrix:
    """Validate React module activation behavior for none/some/all selections."""

    APP_BACKED_MODULES = [
        "auth",
        "blog",
        "listings",
        "crm",
        "forms",
        "storage",
        "backups",
        "notifications",
        "billing",
        "teams",
    ]

    @staticmethod
    def _extract_template_module_app_map(index_html: str) -> dict[str, str]:
        """Extract module->Django app mapping from generated index.html template."""
        mapping: dict[str, str] = {}
        for module in TestReactThemeModuleActivationMatrix.APP_BACKED_MODULES:
            pattern = (
                rf"{module}:\s*\{{%\s*if\s*'([^']+)'\s*in\s*settings\.INSTALLED_APPS\s*%\}}"
                rf"true\{{%\s*else\s*%\}}false\{{%\s*endif\s*%\}}"
            )
            match = re.search(pattern, index_html)
            assert match is not None, (
                f"Missing module activation condition for '{module}' in templates/index.html"
            )
            mapping[module] = match.group(1)
        return mapping

    def test_index_template_declares_all_module_activation_conditions(self, tmp_path):
        """Generated React index template should include activation conditions for all modules."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_module_matrix"
        generator.generate("react_module_matrix", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        app_map = self._extract_template_module_app_map(index_html)

        expected = {
            module: f"quickscale_modules_{module}" for module in self.APP_BACKED_MODULES
        }
        assert app_map == expected

    @pytest.mark.parametrize(
        ("installed_apps", "expected_true"),
        [
            ([], set()),  # none
            (  # some
                [
                    "quickscale_modules_auth",
                    "quickscale_modules_blog",
                    "quickscale_modules_crm",
                    "quickscale_modules_storage",
                    "quickscale_modules_backups",
                ],
                {"auth", "blog", "crm", "storage", "backups"},
            ),
            (  # all
                [
                    "quickscale_modules_auth",
                    "quickscale_modules_blog",
                    "quickscale_modules_listings",
                    "quickscale_modules_crm",
                    "quickscale_modules_forms",
                    "quickscale_modules_storage",
                    "quickscale_modules_backups",
                    "quickscale_modules_notifications",
                    "quickscale_modules_billing",
                    "quickscale_modules_teams",
                ],
                {
                    "auth",
                    "blog",
                    "listings",
                    "crm",
                    "forms",
                    "storage",
                    "backups",
                    "notifications",
                    "billing",
                    "teams",
                },
            ),
        ],
    )
    def test_module_activation_matrix_none_some_all(
        self, tmp_path, installed_apps, expected_true
    ):
        """Module activation naming convention should support none/some/all combinations."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_module_matrix_flags"
        generator.generate("react_module_matrix_flags", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        app_map = self._extract_template_module_app_map(index_html)

        resolved_flags = {
            module: app_name in installed_apps for module, app_name in app_map.items()
        }
        expected_flags = {
            module: module in expected_true for module in self.APP_BACKED_MODULES
        }

        assert resolved_flags == expected_flags

    def test_index_template_declares_social_activation_condition_and_path(
        self, tmp_path
    ):
        """Generated React index template should expose social via settings-backed wiring."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_social_activation"
        generator.generate("react_social_activation", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()

        activation_pattern = re.compile(
            r"social:\s*\{% if settings\.QUICKSCALE_SOCIAL_LINK_TREE_ENABLED "
            r"or settings\.QUICKSCALE_SOCIAL_EMBEDS_ENABLED %\}true"
            r"\{% else %\}false\{% endif %\}"
        )
        path_pattern = re.compile(
            r'social:\s*"\{% if settings\.QUICKSCALE_SOCIAL_LINK_TREE_ENABLED %\}'
            r"/social\{% elif settings\.QUICKSCALE_SOCIAL_EMBEDS_ENABLED %\}"
            r'/social/embeds\{% else %\}/social\{% endif %\}"'
        )

        assert activation_pattern.search(index_html) is not None
        assert path_pattern.search(index_html) is not None

    def test_react_theme_storage_module_appears_in_frontend_config_and_dashboard(
        self, tmp_path
    ):
        """Generated React theme should expose storage in module config and dashboard UI."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_storage_visibility"
        generator.generate("react_storage_visibility", output_path)

        use_modules = (
            output_path / "frontend" / "src" / "hooks" / "useModules.ts"
        ).read_text()
        dashboard = (
            output_path / "frontend" / "src" / "pages" / "Dashboard.tsx"
        ).read_text()

        assert "storage: false" in use_modules
        assert "key: 'storage'" in dashboard
        assert "name: 'Storage'" in dashboard
        assert "href: '/settings'" in dashboard

    def test_react_theme_operational_modules_appear_in_config_and_navigation(
        self, tmp_path
    ):
        """Generated React theme should expose admin-backed and social modules in the UI."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_operational_modules"
        generator.generate("react_operational_modules", output_path)

        use_modules = (
            output_path / "frontend" / "src" / "hooks" / "useModules.ts"
        ).read_text()
        dashboard = (
            output_path / "frontend" / "src" / "pages" / "Dashboard.tsx"
        ).read_text()
        sidebar = (
            output_path / "frontend" / "src" / "components" / "layout" / "Sidebar.tsx"
        ).read_text()
        settings_page = (
            output_path / "frontend" / "src" / "pages" / "SettingsPage.tsx"
        ).read_text()

        assert "backups: false" in use_modules
        assert "notifications: false" in use_modules
        assert "social: false" in use_modules
        assert "modulePaths" in use_modules
        assert "social: '/social'" in use_modules

        assert "key: 'backups'" in dashboard
        assert "name: 'Backups'" in dashboard
        assert "href: '/admin/quickscale_modules_backups/backuppolicy/'" in dashboard
        assert "key: 'notifications'" in dashboard
        assert "name: 'Notifications'" in dashboard
        assert "href: '/admin/quickscale_modules_notifications/'" in dashboard
        assert "key: 'social'" in dashboard
        assert "name: 'Social'" in dashboard
        assert "modulePaths.social" in dashboard
        assert "reloadDocument={mod.reloadDocument}" in dashboard
        assert "lg:grid-cols-4" in dashboard

        assert "name: 'Social'" in sidebar
        assert "modulePaths.social" in sidebar
        assert "name: 'Notifications'" not in sidebar
        assert "name: 'Backups'" not in sidebar
        assert "reloadDocument={item.reloadDocument}" in sidebar

        assert "Storage & CDN" in settings_page
        assert "No admin config surface" in settings_page

    def test_react_theme_generates_backups_app_index_override(self, tmp_path):
        """Generated projects should expose a backup action on the admin app index."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_backups_app_index"
        generator.generate("react_backups_app_index", output_path)

        app_index_template = (
            output_path / "templates" / "admin" / "app_index.html"
        ).read_text()

        assert (
            'action="/admin/quickscale_modules_backups/backuppolicy/ops/create/"'
            in app_index_template
        )
        assert "Create backup now" in app_index_template
        assert "/admin/quickscale_modules_backups/backuppolicy/" in app_index_template
        assert 'app_label == "quickscale_modules_backups"' in app_index_template

    def test_react_theme_generates_backups_admin_index_override(self, tmp_path):
        """Generated projects should expose backup actions on the admin root index."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_backups_admin_index"
        generator.generate("react_backups_admin_index", output_path)

        admin_index_template = (
            output_path / "templates" / "admin" / "index.html"
        ).read_text()

        assert "Create backup now" not in admin_index_template
        assert "Open backup ops" in admin_index_template
        assert 'app.app_label == "quickscale_modules_backups"' in admin_index_template

    def test_react_theme_reserves_public_social_pages(self, tmp_path):
        """Generated React projects should reserve /social routes ahead of the SPA catch-all."""
        project_name = "react_social_public_routes"
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / project_name
        generator.generate(project_name, output_path)

        urls_py = (output_path / project_name / "urls.py").read_text()
        base_template = (output_path / "templates" / "base.html").read_text()
        link_tree_template = (
            output_path / "templates" / "social" / "link_tree.html"
        ).read_text()
        embeds_template = (
            output_path / "templates" / "social" / "embeds.html"
        ).read_text()

        social_route = (
            're_path(\n        r"^social/?$",\n'
            '        TemplateView.as_view(template_name="social/link_tree.html"),'
        )
        embeds_route = (
            're_path(\n        r"^social/embeds/?$",\n'
            '        TemplateView.as_view(template_name="social/embeds.html"),'
        )

        assert social_route in urls_py
        assert embeds_route in urls_py
        assert urls_py.index('r"^social/?$"') < urls_py.index(
            're_path(r".*", TemplateView.as_view(template_name="index.html"))'
        )
        assert 'href="/social"' in base_template
        assert 'href="/social/embeds"' in base_template
        assert 'id="root" class="qs-social-react-shell"' in link_tree_template
        assert "Social module not active" in link_tree_template
        assert (
            "{% if settings.QUICKSCALE_SOCIAL_LINK_TREE_ENABLED or "
            "settings.QUICKSCALE_SOCIAL_EMBEDS_ENABLED %}"
        ) in link_tree_template
        assert "frontend/assets/index.css" in link_tree_template
        assert "frontend/assets/index.js" in link_tree_template
        assert "surface: 'link_tree'" in link_tree_template
        assert "endpoint: '/_quickscale/social/'" in link_tree_template
        assert 'id="root" class="qs-social-react-shell"' in embeds_template
        assert "Social module not active" in embeds_template
        assert (
            "{% if settings.QUICKSCALE_SOCIAL_LINK_TREE_ENABLED or "
            "settings.QUICKSCALE_SOCIAL_EMBEDS_ENABLED %}"
        ) in embeds_template
        assert "frontend/assets/index.css" in embeds_template
        assert "frontend/assets/index.js" in embeds_template
        assert "surface: 'embeds'" in embeds_template
        assert "endpoint: '/_quickscale/social/embeds/'" in embeds_template

    def test_react_routes_cover_all_module_navigation_targets(self, tmp_path):
        """React router should include routes for every module link exposed by the UI."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_route_matrix"
        generator.generate("react_route_matrix", output_path)

        app_tsx = (output_path / "frontend" / "src" / "App.tsx").read_text()

        for path in ["/blog", "/listings", "/crm", "/billing", "/teams", "/profile"]:
            assert f'path="{path}"' in app_tsx, f"Missing route for {path}"

    def test_react_theme_generates_billing_and_teams_pages(self, tmp_path):
        """Billing/Teams page templates should be generated for all-module compatibility."""
        generator = ProjectGenerator(theme="showcase_react")
        output_path = tmp_path / "react_module_pages"
        generator.generate("react_module_pages", output_path)

        assert (output_path / "frontend" / "src" / "pages" / "BillingPage.tsx").exists()
        assert (output_path / "frontend" / "src" / "pages" / "TeamsPage.tsx").exists()
