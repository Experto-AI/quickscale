"""Pytest configuration for quickscale_core tests."""

from pathlib import Path

import pytest

from quickscale_core.generator.generator import ProjectGenerator


@pytest.fixture
def sample_project_name() -> str:
    """Provide a sample project name for testing."""
    return "testproject"


@pytest.fixture
def project_name(sample_project_name: str) -> str:
    """Alias for sample_project_name for backwards compatibility."""
    return sample_project_name


@pytest.fixture
def sample_project_config() -> dict[str, str]:
    """Provide sample project configuration dictionary for testing."""
    return {
        "project_name": "testproject",
        "author": "Test Author",
        "email": "test@example.com",
        "description": "A test Django project",
    }


@pytest.fixture
def generated_project_path(tmp_path: Path, sample_project_name: str) -> Path:
    """Generate a test project and return its path.

    This fixture creates a temporary project using the ProjectGenerator
    and cleans it up after the test completes.
    """
    output_path = tmp_path / sample_project_name

    # Generate project
    generator = ProjectGenerator(theme="showcase_html")
    generator.generate(sample_project_name, output_path)

    # Return path for test assertions
    yield output_path

    # Cleanup is automatic with tmp_path


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (end-to-end workflow)"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as full end-to-end test (requires Docker, browser)"
    )


# E2E Test Fixtures


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Provide path to docker-compose file for pytest-docker."""
    return Path(__file__).parent / "docker-compose.test.yml"


@pytest.fixture(scope="session")
def postgres_service(docker_ip, docker_services):
    """Ensure PostgreSQL service is up and responsive."""
    port = docker_services.port_for("postgres", 5432)

    def is_responsive():
        try:
            import psycopg2

            conn = psycopg2.connect(
                host=docker_ip,
                port=port,
                user="test_user",
                password="test_password",
                dbname="test_db",
            )
            conn.close()
            return True
        except Exception:
            return False

    docker_services.wait_until_responsive(timeout=30.0, pause=0.5, check=is_responsive)

    return {
        "host": docker_ip,
        "port": port,
        "user": "test_user",
        "password": "test_password",
        "database": "test_db",
    }


@pytest.fixture
def postgres_url(postgres_service):
    """Provide PostgreSQL connection URL for tests."""
    return (
        f"postgresql://{postgres_service['user']}:{postgres_service['password']}"
        f"@{postgres_service['host']}:{postgres_service['port']}/{postgres_service['database']}"
    )


@pytest.fixture
def browser_context_args(browser_context_args):
    """Configure Playwright browser context for E2E tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }
