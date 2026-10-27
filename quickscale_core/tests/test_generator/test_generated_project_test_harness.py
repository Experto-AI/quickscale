"""Focused regressions for the generated project's test entrypoints."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import quickscale_core
from quickscale_core.generator.runtime_database import runtime_db_template_context
from quickscale_core.generator.runtime_pins import (
    DJANGO_CI_MATRIX_VERSION,
    DJANGO_CONSTRAINT,
    POSTGRES_PATCH_VERSION,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
    PYTHON_PATCH_VERSION,
    PYTHON_VERSION,
    QUICKSCALE_CORE_PIN,
)


def _render(template_name: str, **overrides: object) -> str:
    """Render one generated-project template with the generator's sample context."""
    core_dir = Path(quickscale_core.__file__).resolve().parent
    environment = Environment(
        loader=FileSystemLoader(str(core_dir / "generator" / "templates"))
    )
    context: dict[str, object] = {
        "project_name": "testproject",
        "package_name": "testproject",
        "theme": "showcase_react",
        "python_version": PYTHON_VERSION,
        "python_patch_version": PYTHON_PATCH_VERSION,
        "python_constraint": PYTHON_CONSTRAINT,
        "django_constraint": DJANGO_CONSTRAINT,
        "django_ci_version": DJANGO_CI_MATRIX_VERSION,
        "postgres_version": POSTGRES_VERSION,
        "postgres_patch_version": POSTGRES_PATCH_VERSION,
        "quickscale_core_pin": QUICKSCALE_CORE_PIN,
        **runtime_db_template_context("testproject"),
        "selected_modules": None,
    }
    context.update(overrides)
    from quickscale_core.generator.project_blocks import render_project_block_content

    blocks = render_project_block_content(
        context.get("selected_modules"), package_name="testproject"
    )
    context.update(
        {
            "module_make": blocks.make,
            "module_ci_test_env": blocks.ci_test_env,
            "module_ci_steps": blocks.ci_steps,
            "module_ci_jobs": blocks.ci_jobs,
            "module_compose_environment": blocks.compose_environment,
        }
    )
    return environment.get_template(template_name).render(context)


def _ci_step(output: str, name: str, next_name: str) -> str:
    """Return the rendered CI step between two step names."""
    return output.split(name, 1)[1].split(next_name, 1)[0]


def test_pytest_configuration_collects_only_project_tests() -> None:
    """The generated suite must not collect the embedded modules' own tests."""
    output = _render("pyproject.toml.j2")

    assert 'testpaths = ["tests"]' in output


def test_makefile_test_target_allows_the_test_database_role() -> None:
    """A project with orgs needs the BYPASSRLS test escape hatch on `make test`."""
    output = _render("Makefile.j2", selected_modules=["auth", "orgs"])

    assert "QUICKSCALE_TEST_ENV := QUICKSCALE_ALLOW_BYPASSRLS=1" in output
    assert "$(QUICKSCALE_TEST_ENV) poetry run pytest" in output

    output_without_orgs = _render("Makefile.j2", selected_modules=["auth"])

    assert "QUICKSCALE_ALLOW_BYPASSRLS" not in output_without_orgs
    # The generic recipe still runs; the managed variable expands to nothing.
    assert "$(QUICKSCALE_TEST_ENV) poetry run pytest" in output_without_orgs


def test_tenant_isolation_target_migration_uses_the_privileged_command() -> None:
    """The target's prerequisite migration needs the sanctioned orgs exemption."""
    output = _render("Makefile.j2", selected_modules=["auth", "orgs"])

    assert (
        "RUNTIME_DATABASE_URL='' QUICKSCALE_PRIVILEGED_COMMAND=migrate "
        "poetry run python manage.py migrate" in output
    )


def test_readme_direct_pytest_commands_allow_the_test_database_role() -> None:
    """A direct pytest command must carry the same test-only allowance."""
    output = _render("README.md.j2")

    assert "QUICKSCALE_ALLOW_BYPASSRLS=1 poetry run pytest" in output


def test_ci_test_and_migration_steps_allow_the_test_database_role() -> None:
    """The generated CI must pass the same escape hatch its test role needs."""
    output = _render("github/workflows/ci.yml.j2", selected_modules=["auth", "orgs"])

    test_step = _ci_step(output, "Run tests with coverage", "Upload coverage")
    assert "pytest --cov=testproject" in test_step
    assert 'QUICKSCALE_ALLOW_BYPASSRLS: "1"' in test_step

    migration_step = _ci_step(output, "Run migrations", "Run tenant isolation")
    assert 'QUICKSCALE_ALLOW_BYPASSRLS: "1"' in migration_step

    output_without_orgs = _render(
        "github/workflows/ci.yml.j2", selected_modules=["auth"]
    )
    test_step_without_orgs = _ci_step(
        output_without_orgs, "Run tests with coverage", "Upload coverage"
    )
    assert "QUICKSCALE_ALLOW_BYPASSRLS" not in test_step_without_orgs
    assert "Run migrations" not in output_without_orgs


def test_ci_frontend_job_has_no_job_level_guard() -> None:
    """GitHub rejects hashFiles at job scope, so the job must run unconditionally."""
    output = _render("github/workflows/ci.yml.j2")

    assert "frontend-lint:" in output
    assert "if: ${{ hashFiles('frontend/package.json')" not in output
    job_header = output.split("  frontend-lint:", 1)[1].split("    steps:", 1)[0]
    assert "if:" not in job_header
    for command in ("pnpm lint", "pnpm type-check", "pnpm test:coverage"):
        assert command in output.split("  frontend-lint:", 1)[1]


def test_makefile_tenant_isolation_target_requires_the_runtime_role() -> None:
    """The behavioural isolation target runs only with a required runtime role."""
    output = _render("Makefile.j2", selected_modules=["auth", "orgs"])

    assert "test-tenant-isolation:" in output
    assert (
        "QUICKSCALE_REQUIRE_TENANT_ISOLATION=1 poetry run pytest "
        "tests/test_tenant_isolation.py -m tenant_isolation -o addopts=" in output
    )

    output_without_orgs = _render("Makefile.j2", selected_modules=["auth"])

    assert "test-tenant-isolation:" not in output_without_orgs


def test_ci_tenant_isolation_lane_provisions_and_runs_the_restricted_role() -> None:
    """The generated lane migrates once, creates the role, then runs the suite."""
    output = _render("github/workflows/ci.yml.j2", selected_modules=["auth", "orgs"])

    assert "  tenant-isolation:" in output
    job = output.split("  tenant-isolation:", 1)[1].split("  frontend-lint:", 1)[0]
    assert (
        "CREATE ROLE quickscale_test_runtime LOGIN CREATEDB NOSUPERUSER "
        "NOBYPASSRLS NOCREATEROLE;" in job
    )
    assert "ALTER ROLE quickscale_test_runtime" in job
    assert (
        "RUNTIME_DATABASE_URL: postgres://quickscale_test_runtime@localhost:5432/postgres"
        in job
    )
    assert "make test-tenant-isolation" in job
    assert "QUICKSCALE_ALLOW_BYPASSRLS" not in job
    assert (
        job.index("Run migrations once")
        < job.index("Create restricted runtime role")
        < job.index("Run two-organization isolation test")
    )

    migration_step = _ci_step(
        job, "Run migrations once", "Create restricted runtime role"
    )
    assert 'RUNTIME_DATABASE_URL: ""' in migration_step
    assert "QUICKSCALE_PRIVILEGED_COMMAND: migrate" in migration_step

    output_without_orgs = _render(
        "github/workflows/ci.yml.j2", selected_modules=["auth"]
    )

    assert "tenant-isolation:" not in output_without_orgs


def test_generated_tenant_isolation_test_fails_when_the_role_is_absent() -> None:
    """The rendered suite fails, rather than skips, in the required lane."""
    output = _render("tests/test_tenant_isolation.py.j2")

    compile(output, "tests/test_tenant_isolation.py", "exec")
    assert "pytest.fail(" in output
    assert "The lane must fail, not skip" in output
    assert (
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        in output
    )
    assert "user=request.user, organization=organization" in output
    assert "organization=organization" in output
    assert 'create(name="Org A", slug="org-a")' in output
    assert 'create(name="Org B", slug="org-b")' in output


def test_generated_conftest_registers_and_deselects_the_isolation_marker() -> None:
    """The generated harness keeps the lane out of the ordinary test run."""
    output = _render("tests/conftest.py.j2")

    compile(output, "tests/conftest.py", "exec")
    assert "pytest_collection_modifyitems" in output
    assert "tenant_isolation" in output
    assert "QUICKSCALE_REQUIRE_TENANT_ISOLATION" in output
