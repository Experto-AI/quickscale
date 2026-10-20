"""Focused regressions for the generated project's test entrypoints."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import quickscale_core
from quickscale_core.generator.runtime_database import runtime_db_template_context
from quickscale_core.generator.runtime_pins import (
    DJANGO_CI_MATRIX_VERSION,
    DJANGO_CONSTRAINT,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
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
        "python_constraint": PYTHON_CONSTRAINT,
        "django_constraint": DJANGO_CONSTRAINT,
        "django_ci_version": DJANGO_CI_MATRIX_VERSION,
        "postgres_version": POSTGRES_VERSION,
        "quickscale_core_pin": QUICKSCALE_CORE_PIN,
        **runtime_db_template_context("testproject"),
        "selected_modules": None,
    }
    context.update(overrides)
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

    assert "QUICKSCALE_ALLOW_BYPASSRLS=1 poetry run pytest" in output

    output_without_orgs = _render("Makefile.j2", selected_modules=["auth"])

    assert "QUICKSCALE_ALLOW_BYPASSRLS=1 poetry run pytest" not in output_without_orgs


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
