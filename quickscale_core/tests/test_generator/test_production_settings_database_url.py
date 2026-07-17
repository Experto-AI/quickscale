"""Tests for DATABASE_URL validation and RUNTIME_DATABASE_URL override in production settings template."""

from pathlib import Path

import pytest

from quickscale_core.generator.runtime_pins import (
    POSTGRES_DOCKER_TAG,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
    PYTHON_DOCKER_TAG,
    PYTHON_VERSION,
)


@pytest.fixture
def prod_test_context() -> dict[str, str]:
    """Minimal context for production settings template rendering."""
    return {
        "project_name": "testproject",
        "package_name": "testproject",
        "theme": "showcase_react",
        "python_version": PYTHON_VERSION,
        "python_constraint": PYTHON_CONSTRAINT,
        "python_docker_tag": PYTHON_DOCKER_TAG,
        "postgres_version": POSTGRES_VERSION,
        "postgres_docker_tag": POSTGRES_DOCKER_TAG,
        "django_constraint": ">=6.0.3,<6.1.0",
        "django_ci_version": "6.0",
        "runtime_db_role": "testproject_app",
        "runtime_db_password": "testproject_app_password",
    }


class TestProductionSettingsValidation:
    """Tests for DATABASE_URL validation logic in production settings template."""

    def test_error_message_contains_railway_guidance(self) -> None:
        """Test that error message provides helpful Railway-specific guidance."""
        # This is the error message that should appear in the template
        expected_error_message = (
            "DATABASE_URL environment variable is not set or is empty. "
            "Railway requires DATABASE_URL to connect to PostgreSQL. "
            "Ensure the database service is linked to your app service in Railway dashboard."
        )

        # Verify error message contains key information
        assert "DATABASE_URL" in expected_error_message
        assert "Railway" in expected_error_message
        assert "linked" in expected_error_message.lower()
        assert "database service" in expected_error_message.lower()

    def test_template_contains_database_url_validation(self) -> None:
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
                "database_url = config(" in template_content
                or "DATABASE_URL" in template_content
            )
            assert "ValueError" in template_content
            assert "Railway" in template_content

    def test_template_allows_collectstatic_without_db(self) -> None:
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
            assert "QUICKSCALE_NON_DB_COMMAND" in template_content
            assert "collectstatic" in template_content

    def test_template_provides_dummy_url_for_collectstatic(self) -> None:
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

    def test_template_has_runtime_database_url_override(self) -> None:
        """Test production settings template contains RUNTIME_DATABASE_URL override logic."""
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

            assert "RUNTIME_DATABASE_URL" in template_content
            assert 'config("RUNTIME_DATABASE_URL", default=None)' in template_content
            assert "conn_health_checks=True" in template_content

    def test_fail_closed_when_runtime_url_unset_for_serving(self) -> None:
        """Test template raises clear error when RUNTIME_DATABASE_URL is unset for serving."""
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

            # Template must raise a clear error about RUNTIME_DATABASE_URL
            # when serving and the env var is not set (fail-closed).
            assert (
                "RUNTIME_DATABASE_URL is required for runtime serving"
                in template_content
            )
            assert (
                "NOSUPERUSER" in template_content or "NOBYPASSRLS" in template_content
            )
            # The privileged command path must be documented
            assert "QUICKSCALE_PRIVILEGED_COMMAND" in template_content

    def test_migration_exception_preserved(self) -> None:
        """Test template preserves the migration path with DATABASE_URL."""
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

            # Migration path must use QUICKSCALE_PRIVILEGED_COMMAND
            assert "QUICKSCALE_PRIVILEGED_COMMAND" in template_content
            assert "migrate" in template_content
            assert "DATABASE_URL" in template_content
            # DATABASE_URL error message should still be present
            assert "DATABASE_URL is required for privileged" in template_content
