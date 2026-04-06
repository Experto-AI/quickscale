"""Test error page generation and custom error handlers.

This module ensures:
1. Error templates (404.html, 500.html) are generated
2. Custom error handler views (views.py) are generated
3. Error handlers are configured in urls.py
4. Error pages avoid placeholder-module leakage while keeping current guidance
"""

from pathlib import Path


class TestErrorPageGeneration:
    """Test that error page templates are generated correctly"""

    def test_404_template_generated(self, generated_project_path: Path) -> None:
        """Test that 404.html template is generated"""
        template_404 = generated_project_path / "templates" / "404.html"
        assert template_404.exists(), "404.html template should be generated"

    def test_500_template_generated(self, generated_project_path: Path) -> None:
        """Test that 500.html template is generated"""
        template_500 = generated_project_path / "templates" / "500.html"
        assert template_500.exists(), "500.html template should be generated"

    def test_404_template_content(self, generated_project_path: Path) -> None:
        """Test that 404.html contains expected content"""
        template_404 = generated_project_path / "templates" / "404.html"
        content = template_404.read_text()

        # Verify structure
        assert "404" in content, "Should display 404 error code"
        assert "Page Not Found" in content, "Should have user-friendly title"

        # Verify module hints are present
        assert "accounts/" in content, "Should detect auth module URLs"
        assert "billing/" not in content, "Should not surface billing placeholders"
        assert "teams/" not in content, "Should not surface teams placeholders"

        # Verify installation instructions
        assert "quickscale.yml" in content, "Should reference the plan/apply config"
        assert "quickscale apply" in content, "Should provide apply guidance"
        assert "quickscale embed --module" not in content, (
            "Should not provide legacy embed commands"
        )

    def test_500_template_content(self, generated_project_path: Path) -> None:
        """Test that 500.html contains expected content"""
        template_500 = generated_project_path / "templates" / "500.html"
        content = template_500.read_text()

        # Verify structure
        assert "500" in content, "Should display 500 error code"
        assert "Server Error" in content, "Should have user-friendly title"
        assert "homepage" in content.lower(), "Should have link to homepage"


class TestErrorHandlerViews:
    """Test that custom error handler views are generated"""

    def test_views_file_generated(
        self, generated_project_path: Path, project_name: str
    ) -> None:
        """Test that views.py is generated"""
        views_file = generated_project_path / project_name / "views.py"
        assert views_file.exists(), "views.py should be generated"

    def test_views_contain_404_handler(
        self, generated_project_path: Path, project_name: str
    ) -> None:
        """Test that views.py contains custom 404 handler"""
        views_file = generated_project_path / project_name / "views.py"
        content = views_file.read_text()

        assert "def custom_404_view" in content, "Should have custom_404_view function"
        assert "request: HttpRequest" in content, "Should have proper type hints"
        assert "exception: Exception" in content, "Should accept exception parameter"
        assert "render(request, " in content and '"404.html"' in content, (
            "Should render 404.html"
        )
        assert "status=404" in content, "Should return 404 status code"
        assert "request_path" in content, "Should pass request path to template"

    def test_views_contain_500_handler(
        self, generated_project_path: Path, project_name: str
    ) -> None:
        """Test that views.py contains custom 500 handler"""
        views_file = generated_project_path / project_name / "views.py"
        content = views_file.read_text()

        assert "def custom_500_view" in content, "Should have custom_500_view function"
        assert "render(request, " in content and '"500.html"' in content, (
            "Should render 500.html"
        )
        assert "status=500" in content, "Should return 500 status code"


class TestErrorHandlerConfiguration:
    """Test that error handlers are configured in urls.py"""

    def test_handler404_configured(
        self, generated_project_path: Path, project_name: str
    ) -> None:
        """Test that handler404 is configured in urls.py"""
        urls_file = generated_project_path / project_name / "urls.py"
        content = urls_file.read_text()

        assert "handler404" in content, "Should configure handler404"
        assert f'"{project_name}.views.custom_404_view"' in content, (
            "Should point to custom_404_view"
        )

    def test_handler500_configured(
        self, generated_project_path: Path, project_name: str
    ) -> None:
        """Test that handler500 is configured in urls.py"""
        urls_file = generated_project_path / project_name / "urls.py"
        content = urls_file.read_text()

        assert "handler500" in content, "Should configure handler500"
        assert f'"{project_name}.views.custom_500_view"' in content, (
            "Should point to custom_500_view"
        )

    def test_debug_404_routes_exclude_placeholder_modules(
        self, generated_project_path: Path, project_name: str
    ) -> None:
        """Test that HTML starter debug routes only keep shipped auth guidance."""
        urls_file = generated_project_path / project_name / "urls.py"
        content = urls_file.read_text()

        assert 're_path(r"^accounts/.*", custom_404_view)' in content, (
            "Should keep auth-specific debug guidance"
        )
        assert 're_path(r"^billing/.*", custom_404_view)' not in content, (
            "Should not add billing placeholder debug routes"
        )
        assert 're_path(r"^teams/.*", custom_404_view)' not in content, (
            "Should not add teams placeholder debug routes"
        )


class TestModuleInstallationHints:
    """Test that 404 page provides helpful module installation hints"""

    def test_auth_module_hint(self, generated_project_path: Path) -> None:
        """Test that 404 page detects auth module URLs and provides hints"""
        template_404 = generated_project_path / "templates" / "404.html"
        content = template_404.read_text()

        # Should detect /accounts/ URLs
        assert "accounts/" in content, "Should check for accounts/ in request path"
        assert "Looking for authentication" in content, (
            "Should provide auth-specific hint"
        )
        assert "quickscale.yml" in content, (
            "Should point auth guidance at the config file"
        )
        assert "quickscale apply" in content, (
            "Should keep auth guidance on the apply workflow"
        )

    def test_placeholder_module_hints_removed(
        self, generated_project_path: Path
    ) -> None:
        """Test that billing and teams placeholders do not leak into 404 output."""
        template_404 = generated_project_path / "templates" / "404.html"
        content = template_404.read_text()

        assert "billing/" not in content, "Should not check for billing/ routes"
        assert "teams/" not in content, "Should not check for teams/ routes"
        assert "Billing Module" not in content, (
            "Should not mention placeholder billing guidance"
        )
        assert "Teams Module" not in content, (
            "Should not mention placeholder teams guidance"
        )
        assert "quickscale embed --module" not in content, (
            "Should remove legacy embed guidance entirely"
        )

    def test_generic_404_guidance(self, generated_project_path: Path) -> None:
        """Test that 404 page provides generic guidance for other URLs"""
        template_404 = generated_project_path / "templates" / "404.html"
        content = template_404.read_text()

        # Should provide generic help for non-module URLs
        assert "Check the URL for typos" in content, "Should suggest checking for typos"
        assert "homepage" in content.lower(), "Should suggest returning to homepage"
        assert "quickscale.yml" in content, "Should reference the config workflow"
        assert "quickscale apply" in content, "Should reference apply"
        assert "urls.py" in content, "Should mention URL configuration"


class TestErrorPageStyling:
    """Test that error pages have proper styling"""

    def test_404_has_styling(self, generated_project_path: Path) -> None:
        """Test that 404.html includes CSS styling"""
        template_404 = generated_project_path / "templates" / "404.html"
        content = template_404.read_text()

        assert "<style>" in content, "Should include inline CSS"
        assert ".error-container" in content, "Should have error container styles"
        assert ".error-code" in content, "Should have error code styles"
        assert ".module-hint" in content, "Should have module hint styles"
        assert ".error-help" in content, "Should have help section styles"

    def test_500_has_styling(self, generated_project_path: Path) -> None:
        """Test that 500.html includes CSS styling"""
        template_500 = generated_project_path / "templates" / "500.html"
        content = template_500.read_text()

        assert "<style>" in content, "Should include inline CSS"
        assert ".error-container" in content, "Should have error container styles"
        assert ".error-code" in content, "Should have error code styles"


class TestErrorPageUserExperience:
    """Test that error pages provide good user experience"""

    def test_404_has_navigation(self, generated_project_path: Path) -> None:
        """Test that 404 page has navigation back to homepage"""
        template_404 = generated_project_path / "templates" / "404.html"
        content = template_404.read_text()

        assert 'href="/"' in content, "Should have link to homepage"
        assert "Go to Homepage" in content or "homepage" in content.lower(), (
            "Should have clear homepage navigation"
        )

    def test_500_has_navigation(self, generated_project_path: Path) -> None:
        """Test that 500 page has navigation and recovery options"""
        template_500 = generated_project_path / "templates" / "500.html"
        content = template_500.read_text()

        assert 'href="/"' in content, "Should have link to homepage"
        assert "refresh" in content.lower() or "reload" in content.lower(), (
            "Should suggest refreshing the page"
        )

    def test_error_pages_extend_base(self, generated_project_path: Path) -> None:
        """Test that error pages extend the base template"""
        for template_name in ["404.html", "500.html"]:
            template_file = generated_project_path / "templates" / template_name
            content = template_file.read_text()

            assert '{% extends "base.html" %}' in content, (
                f"{template_name} should extend base.html template"
            )
            assert "{% block" in content, f"{template_name} should use template blocks"
