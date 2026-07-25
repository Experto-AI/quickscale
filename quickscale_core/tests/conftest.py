"""Pytest configuration for quickscale_core tests."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def _isolate_poetry_cache_per_worker() -> None:
    """Give each xdist worker its own Poetry cache to avoid global-lock contention.

    The e2e/runtime tests shell out to ``poetry lock``/``poetry install`` in
    generated projects (see ``test_generated_project_runtime.py`` and
    ``test_e2e_full_workflow.py``). Under ``-n auto`` many workers hit Poetry's
    shared global cache lock (``~/.cache/pypoetry``) at once and serialize or
    deadlock, wedging the whole run and leaving orphaned ``poetry`` processes.
    A per-worker cache dir removes the contention. Runs at conftest import time
    so the env var is set before any test shells out. Honors an explicit
    ``POETRY_CACHE_DIR`` override and is a no-op outside xdist.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker or "POETRY_CACHE_DIR" in os.environ:
        return
    cache_dir = Path(tempfile.gettempdir()) / f"qs-poetry-cache-{worker}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["POETRY_CACHE_DIR"] = str(cache_dir)


_isolate_poetry_cache_per_worker()


def _build_docker_compose_project_name() -> str:
    """Build a Docker Compose project name from environment context.

    Outside xdist, returns the base name from ``QS_E2E_COMPOSE_PROJECT_NAME``
    or a Docker-valid fallback (``qscaletest``). Under xdist, appends the
    worker ID with a ``-`` separator so workers each get an isolated Compose
    project and avoid container name collisions.
    """
    base = os.environ.get("QS_E2E_COMPOSE_PROJECT_NAME", "qscaletest")
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        return f"{base}-{worker}"
    return base


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    """Provide a Docker Compose project name unique per xdist worker.

    Overrides pytest-docker's default project name so each xdist worker
    gets its own Compose namespace.  The base comes from the
    ``QS_E2E_COMPOSE_PROJECT_NAME`` env var (fallback: ``qscaletest``);
    under xdist the ``PYTEST_XDIST_WORKER`` (e.g. ``gw0``) is appended.
    """
    return _build_docker_compose_project_name()


@pytest.fixture(autouse=True)
def _skip_generator_poetry_lock(request: pytest.FixtureRequest) -> None:
    """Stop ``generate()`` from shelling out to real ``poetry lock`` in the unit lane.

    The generator runs ``poetry lock`` as part of project generation (see
    ``generator._generate_poetry_lock``). Every generator unit test that drives
    real ``generate()`` therefore spawns a network ``poetry lock`` (up to 300s);
    run in parallel they deadlock on Poetry's global cache lock and wedge the
    suite. ``QS_SKIP_POETRY_LOCK`` makes the generator skip that step.

    Applied per test by marker (not argv sniffing — ``-m "not e2e"`` contains the
    substring "e2e"): e2e tests need real generation + install, so the flag is
    cleared for them; every other test runs hermetically without touching Poetry.
    """
    if request.node.get_closest_marker("e2e"):
        os.environ.pop("QS_SKIP_POETRY_LOCK", None)
    else:
        os.environ["QS_SKIP_POETRY_LOCK"] = "1"


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
    from quickscale_core.generator.generator import ProjectGenerator

    output_path = tmp_path / sample_project_name

    # Generate project
    generator = ProjectGenerator(theme="showcase_react")
    generator.generate(sample_project_name, output_path)

    # Return path for test assertions
    yield output_path

    # Cleanup is automatic with tmp_path


def _generate_unique_db_name() -> str:
    """Generate a unique database name for per-test database isolation."""
    import uuid

    return f"qs_test_{uuid.uuid4().hex[:12]}"


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
def unique_db_name() -> str:
    """Generate a unique database name for per-test isolation."""
    return _generate_unique_db_name()


@pytest.fixture
def per_test_db(postgres_service, unique_db_name):
    """Create a unique PostgreSQL database and drop it after the test.

    Uses the session-scoped docker PostgreSQL container but creates an
    isolated database per requesting test, eliminating cross-test
    contamination from shared fixed database names.
    """
    import psycopg2

    host = postgres_service["host"]
    port = postgres_service["port"]
    user = postgres_service["user"]
    password = postgres_service["password"]
    db_name = unique_db_name

    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname="postgres",
    )
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{db_name}"')

    yield {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": db_name,
    }

    # Teardown: terminate connections and drop the database
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pg_stat_activity.pid) "
            "FROM pg_stat_activity "
            "WHERE pg_stat_activity.datname = %s "
            "AND pid <> pg_backend_pid()",
            (db_name,),
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')

    conn.close()


@pytest.fixture
def postgres_url(per_test_db):
    """Provide PostgreSQL connection URL with a unique per-test database."""
    return (
        f"postgresql://{per_test_db['user']}:{per_test_db['password']}"
        f"@{per_test_db['host']}:{per_test_db['port']}/{per_test_db['database']}"
    )


@pytest.fixture
def browser_context_args(browser_context_args):
    """Configure Playwright browser context for E2E tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }
