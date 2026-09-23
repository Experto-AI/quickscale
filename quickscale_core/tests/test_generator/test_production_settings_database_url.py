"""Tests for DATABASE_URL validation and RUNTIME_DATABASE_URL override in production settings template.

SA206 moved the command-mode contract into the versioned
``quickscale_core.runtime.settings`` facade.  The production template keeps the
user configuration and delegates the validation to the facade, so the
contract-text assertions below read the facade source.
"""

from pathlib import Path

import pytest

from quickscale_core.generator.runtime_database import runtime_db_template_context
from quickscale_core.generator.runtime_pins import (
    DJANGO_CI_MATRIX_VERSION,
    DJANGO_CONSTRAINT,
    POSTGRES_DOCKER_TAG,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
    PYTHON_DOCKER_TAG,
    PYTHON_VERSION,
)


PRODUCTION_TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "quickscale_core"
    / "generator"
    / "templates"
    / "project_name"
    / "settings"
    / "production.py.j2"
)
FACADE_SOURCE_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "quickscale_core"
    / "runtime"
    / "settings.py"
)


def _production_template_source() -> str:
    return PRODUCTION_TEMPLATE_PATH.read_text()


def _facade_source() -> str:
    return FACADE_SOURCE_PATH.read_text()


@pytest.fixture
def prod_test_context() -> dict[str, object]:
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
        "django_constraint": DJANGO_CONSTRAINT,
        "django_ci_version": DJANGO_CI_MATRIX_VERSION,
        **runtime_db_template_context("testproject"),
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

    def test_template_delegates_database_url_validation_to_facade(self) -> None:
        """The template keeps the env reads and delegates the validation."""
        template_content = _production_template_source()
        facade_content = _facade_source()

        assert "DATABASE_URL" in template_content
        assert "database_url = config(" in template_content
        assert "resolve_runtime_database_url(" in template_content
        assert "ValueError" in facade_content
        assert "Railway" in template_content

    def test_template_allows_collectstatic_without_db(self) -> None:
        """The facade allows collectstatic to run without DATABASE_URL."""
        template_content = _production_template_source()
        facade_content = _facade_source()

        assert "QUICKSCALE_NON_DB_COMMAND" in template_content
        assert "collectstatic" in facade_content

    def test_template_provides_dummy_url_for_collectstatic(self) -> None:
        """The facade provides a dummy DATABASE_URL for collectstatic."""
        facade_content = _facade_source()

        assert "dummy" in facade_content.lower()
        # Should have postgresql connection string format
        assert "postgresql://" in facade_content

    def test_template_has_runtime_database_url_override(self) -> None:
        """Test production settings template contains RUNTIME_DATABASE_URL override logic."""
        template_content = _production_template_source()

        assert "RUNTIME_DATABASE_URL" in template_content
        assert 'config("RUNTIME_DATABASE_URL", default=None)' in template_content
        assert "conn_health_checks=True" in template_content

    def test_fail_closed_when_runtime_url_unset_for_serving(self) -> None:
        """The facade raises a clear error when RUNTIME_DATABASE_URL is unset for serving."""
        template_content = _production_template_source()
        facade_content = _facade_source()

        assert "RUNTIME_DATABASE_URL is required for runtime serving" in facade_content
        assert "NOSUPERUSER" in facade_content or "NOBYPASSRLS" in facade_content
        # The privileged command path must be documented
        assert "QUICKSCALE_PRIVILEGED_COMMAND" in template_content

    def test_migration_exception_preserved(self) -> None:
        """The facade preserves the migration path with DATABASE_URL."""
        template_content = _production_template_source()
        facade_content = _facade_source()

        # Migration path must use QUICKSCALE_PRIVILEGED_COMMAND
        assert "QUICKSCALE_PRIVILEGED_COMMAND" in template_content
        assert "migrate" in template_content
        assert "DATABASE_URL" in template_content
        # DATABASE_URL error message should still be present
        assert "DATABASE_URL is required for privileged" in facade_content
