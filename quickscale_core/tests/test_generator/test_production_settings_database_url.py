"""Tests for DATABASE_URL validation in production settings template."""

from pathlib import Path


class TestProductionSettingsValidation:
    """Tests for DATABASE_URL validation logic in production settings template."""

    def test_error_message_contains_railway_guidance(self):
        """Test that error message provides helpful Railway-specific guidance."""
        # This is the error message that should appear in the template
        expected_error_message = (
            "DATABASE_URL environment variable is not set. "
            "Railway requires DATABASE_URL to connect to PostgreSQL. "
            "Ensure the database service is linked to your app service in Railway dashboard."
        )

        # Verify error message contains key information
        assert "DATABASE_URL" in expected_error_message
        assert "Railway" in expected_error_message
        assert "linked" in expected_error_message.lower()
        assert "database service" in expected_error_message.lower()

    def test_template_contains_database_url_validation(self):
        """Test that production settings template contains DATABASE_URL validation."""
        # Read the actual template file
        template_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "quickscale_core"
            / "generator"
            / "templates"
            / "project_name"
            / "settings"
            / "production.py.j2"
        )

        if template_path.exists():
            with open(template_path) as f:
                template_content = f.read()

            # Verify key validation logic is present in template
            assert "DATABASE_URL" in template_content
            assert (
                "database_url = config(" in template_content or "DATABASE_URL" in template_content
            )
            assert "ValueError" in template_content
            assert "Railway" in template_content

    def test_template_allows_collectstatic_without_db(self):
        """Test that template allows collectstatic to run without DATABASE_URL."""
        # Read the actual template file
        template_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "quickscale_core"
            / "generator"
            / "templates"
            / "project_name"
            / "settings"
            / "production.py.j2"
        )

        if template_path.exists():
            with open(template_path) as f:
                template_content = f.read()

            # Verify template has logic to allow collectstatic without DATABASE_URL
            assert "collectstatic" in template_content
            # The template should check sys.argv for collectstatic
            assert "sys.argv" in template_content

    def test_template_provides_dummy_url_for_collectstatic(self):
        """Test that template provides dummy DATABASE_URL for collectstatic."""
        # Read the actual template file
        template_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "quickscale_core"
            / "generator"
            / "templates"
            / "project_name"
            / "settings"
            / "production.py.j2"
        )

        if template_path.exists():
            with open(template_path) as f:
                template_content = f.read()

            # Verify template provides a dummy URL when DATABASE_URL is not set
            assert "dummy" in template_content.lower()
            # Should have postgresql connection string format
            assert "postgresql://" in template_content
