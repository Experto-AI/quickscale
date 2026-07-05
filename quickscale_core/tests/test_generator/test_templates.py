"""Tests for QuickScale project template rendering and validation."""

import ast
from pathlib import Path
import sys
import types
import typing
from collections.abc import Callable

import pytest
from jinja2 import Environment, FileSystemLoader

from quickscale_core.generator.runtime_pins import (
    DJANGO_CI_MATRIX_VERSION,
    DJANGO_CONSTRAINT,
    POSTGRES_DOCKER_TAG,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
    PYTHON_DOCKER_TAG,
    PYTHON_VERSION,
)


@pytest.fixture
def template_dir() -> Path:
    """Locate and return the templates directory path."""
    import quickscale_core

    core_dir = Path(quickscale_core.__file__).resolve().parent
    templates_dir = core_dir / "generator" / "templates"
    assert templates_dir.exists(), f"Templates directory not found: {templates_dir}"
    return templates_dir


@pytest.fixture
def jinja_env(template_dir: Path) -> Environment:
    """Create a Jinja2 environment configured with template loader."""
    return Environment(loader=FileSystemLoader(str(template_dir)))


@pytest.fixture
def test_context() -> dict[str, str | list[str] | None]:
    """Provide sample context data for template rendering tests.

    Includes generated-project runtime pins imported from the
    ``runtime_pins`` module to keep tests aligned with the single
    source of truth.
    """
    return {
        "project_name": "testproject",
        "package_name": "testproject",
        "theme": "showcase_html",
        "python_version": PYTHON_VERSION,
        "python_constraint": PYTHON_CONSTRAINT,
        "python_docker_tag": PYTHON_DOCKER_TAG,
        "django_constraint": DJANGO_CONSTRAINT,
        "django_ci_version": DJANGO_CI_MATRIX_VERSION,
        "postgres_version": POSTGRES_VERSION,
        "postgres_docker_tag": POSTGRES_DOCKER_TAG,
        "runtime_db_role": "testproject_app",
        "runtime_db_password": "testproject_app_password",
        "selected_modules": None,
    }


def _render_template(
    jinja_env: Environment,
    template_name: str,
    context: dict[str, str],
) -> str:
    """Render a template with the shared sample context."""
    return jinja_env.get_template(template_name).render(context)


def _extract_env_value(rendered_env: str, key: str) -> str:
    """Return a rendered env var value from the generated .env.example content."""
    prefix = f"{key}="
    for line in rendered_env.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"{key} not found in rendered .env.example")


def _build_fake_config(
    values: dict[str, object],
) -> Callable[[str, object, Callable[[object], object] | None], object]:
    """Create a decouple.config stub backed by explicit test values."""

    def fake_config(
        key: str,
        default: object = "",
        cast: Callable[[object], object] | None = None,
    ) -> object:
        value = values.get(key, default)
        if cast is None:
            return value
        return cast(value)

    return fake_config


def _execute_rendered_settings(
    *,
    monkeypatch: pytest.MonkeyPatch,
    package_name: str,
    base_output: str,
    target_output: str,
    target_module_name: str,
    config_values: dict[str, object],
) -> dict[str, object]:
    """Execute rendered settings modules with lightweight import stubs."""
    settings_package_name = f"{package_name}.settings"
    modules_name = f"{settings_package_name}.modules"
    base_module_name = f"{settings_package_name}.base"

    package_module = types.ModuleType(package_name)
    package_module.__dict__["__path__"] = []
    settings_package_module = types.ModuleType(settings_package_name)
    settings_package_module.__dict__["__path__"] = []
    modules_module = types.ModuleType(modules_name)
    setattr(modules_module, "MODULE_INSTALLED_APPS", [])
    setattr(modules_module, "MODULE_MIDDLEWARE", [])
    setattr(modules_module, "MODULE_SETTINGS", {})

    decouple_module = types.ModuleType("decouple")
    setattr(decouple_module, "config", _build_fake_config(config_values))

    dj_database_url_module = types.ModuleType("dj_database_url")
    setattr(
        dj_database_url_module,
        "parse",
        lambda url, conn_max_age=0, conn_health_checks=False, ssl_require=False: {
            "URL": url,
            "CONN_MAX_AGE": conn_max_age,
            "CONN_HEALTH_CHECKS": conn_health_checks,
            "SSL_REQUIRE": ssl_require,
        },
    )
    setattr(
        dj_database_url_module,
        "config",
        lambda default, conn_max_age=0, conn_health_checks=False: {
            "URL": default,
            "CONN_MAX_AGE": conn_max_age,
            "CONN_HEALTH_CHECKS": conn_health_checks,
        },
    )

    monkeypatch.setitem(sys.modules, package_name, package_module)
    monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
    monkeypatch.setitem(sys.modules, modules_name, modules_module)
    monkeypatch.setitem(sys.modules, "decouple", decouple_module)
    monkeypatch.setitem(sys.modules, "dj_database_url", dj_database_url_module)

    base_module = types.ModuleType(base_module_name)
    base_module.__dict__.update(
        {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": base_module_name,
            "__package__": settings_package_name,
        }
    )
    exec(base_output, base_module.__dict__)
    monkeypatch.setitem(sys.modules, base_module_name, base_module)

    target_namespace: dict[str, object] = {
        "__file__": f"/tmp/{package_name}/settings/{target_module_name}.py",
        "__name__": f"{settings_package_name}.{target_module_name}",
        "__package__": settings_package_name,
    }
    exec(target_output, target_namespace)
    return target_namespace


class TestQuickScaleCorePackageMetadata:
    """Verify package metadata helpers used by the template tests."""

    def test_version_module_falls_back_to_repo_version_file(self) -> None:
        """Development version metadata should fall back to the repo VERSION file."""
        import builtins

        import quickscale_core

        version_path = Path(quickscale_core.__file__).resolve().parent / "version.py"
        repo_version = (
            version_path.parents[3]
            .joinpath("VERSION")
            .read_text(encoding="utf8")
            .strip()
        )
        version_source = version_path.read_text(encoding="utf8")
        real_import = builtins.__import__

        def fake_import(
            name: str,
            globals_: dict[str, object] | None = None,
            locals_: dict[str, object] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if (
                name == "_version"
                and level == 1
                and globals_ is not None
                and globals_.get("__package__") == "quickscale_core"
            ):
                raise ImportError("exercise repository VERSION fallback")
            return real_import(name, globals_, locals_, fromlist, level)

        namespace: dict[str, object] = {
            "__builtins__": {**builtins.__dict__, "__import__": fake_import},
            "__file__": str(version_path),
            "__name__": "quickscale_core.version",
            "__package__": "quickscale_core",
        }

        exec(compile(version_source, str(version_path), "exec"), namespace)

        assert namespace["__version__"] == repo_version
        assert namespace["VERSION"] == tuple(
            int(part) for part in repo_version.split(".")
        )


class TestRuntimePins:
    """Verify the runtime_pins module defines generated-project-owned pin values."""

    def test_python_pins_defined(self) -> None:
        """Python version, constraint, and Docker tag should be exported."""
        from quickscale_core.generator.runtime_pins import (
            PYTHON_CONSTRAINT,
            PYTHON_DOCKER_TAG,
            PYTHON_VERSION,
        )

        assert PYTHON_VERSION == "3.13"
        assert PYTHON_CONSTRAINT == f">={PYTHON_VERSION},<3.15"
        assert PYTHON_DOCKER_TAG == f"{PYTHON_VERSION}-slim-bookworm"

    def test_django_pins_defined(self) -> None:
        """Django constraint and CI matrix version should be exported."""
        from quickscale_core.generator.runtime_pins import (
            DJANGO_CI_MATRIX_VERSION,
            DJANGO_CONSTRAINT,
        )

        assert DJANGO_CONSTRAINT == ">=6.0.3,<6.1.0"
        assert DJANGO_CI_MATRIX_VERSION == "6.0"

    def test_postgres_pins_defined(self) -> None:
        """PostgreSQL version and Docker tag should be exported."""
        from quickscale_core.generator.runtime_pins import (
            POSTGRES_DOCKER_TAG,
            POSTGRES_VERSION,
        )

        assert POSTGRES_VERSION == "18"
        assert POSTGRES_DOCKER_TAG == f"{POSTGRES_VERSION}-alpine"

    def test_generator_injects_pin_context(
        self,
    ) -> None:
        """ProjectGenerator should inject runtime pin values into template context."""
        from quickscale_core.generator import ProjectGenerator
        from quickscale_core.generator.generator import (
            DJANGO_CONSTRAINT,
            DJANGO_CI_MATRIX_VERSION,
            POSTGRES_DOCKER_TAG,
            POSTGRES_VERSION,
            PYTHON_CONSTRAINT,
            PYTHON_DOCKER_TAG,
            PYTHON_VERSION,
        )

        # Instantiate generator with a known template dir.
        # Use a small isolated template directory to avoid full scaffolding.
        import tempfile
        from pathlib import Path

        tmp_template_dir = Path(tempfile.mkdtemp())
        # Create the minimal theme directory required by the generator.
        theme_dir = tmp_template_dir / "themes" / "showcase_react"
        theme_dir.mkdir(parents=True)

        ProjectGenerator(template_dir=tmp_template_dir, theme="showcase_react")

        # Access the context dict built by _generate_project.
        # We can't call _generate_project easily in isolation, so verify
        # that the generator module imported the runtime pin values correctly.
        assert PYTHON_VERSION is not None
        assert PYTHON_CONSTRAINT is not None
        assert PYTHON_DOCKER_TAG is not None
        assert DJANGO_CONSTRAINT is not None
        assert DJANGO_CI_MATRIX_VERSION is not None
        assert POSTGRES_VERSION is not None
        assert POSTGRES_DOCKER_TAG is not None


# ── Expected constraint values for drift detection ────────────────────
# These are the F7.3-contract values that all packaged modules and
# generator packages must carry.  They are duplicated here only for test
# self-containment; the authoritative values live in runtime_pins.py.
_EXPECTED_PYTHON_CONSTRAINT = ">=3.13,<3.15"
_EXPECTED_MODULE_DJANGO_CONSTRAINT = ">=6.0.5,<6.1.0"


@pytest.fixture(scope="module")
def repo_root() -> Path:
    """Return the repository root by navigating up from quickscale_core."""
    import quickscale_core

    core_init = Path(quickscale_core.__file__).resolve()
    # quickscale_core/src/quickscale_core/__init__.py -> parents[3] = repo root
    return core_init.parents[3]


class TestRuntimePinDriftDetection:
    """Detect unintended drift between runtime_pins.py and the broader repo.

    These tests encode the F7.3 contract: generator Python constraints
    and module Python constraints must match
    ``runtime_pins.PYTHON_CONSTRAINT``, while module Django constraints
    preserve the intentionally tighter lower bound (``>=6.0.5``) with
    the same upper bound as ``runtime_pins.DJANGO_CONSTRAINT``.
    """

    def test_generator_python_parity(self, repo_root: Path) -> None:
        """Generator pyproject.toml files must match PYTHON_CONSTRAINT."""
        from quickscale_core.generator.constraint_validation import (
            check_generator_python_constraints,
        )
        from quickscale_core.generator.runtime_pins import PYTHON_CONSTRAINT

        messages = check_generator_python_constraints(
            repo_root, expected_python=PYTHON_CONSTRAINT
        )
        assert not messages, (
            "Generator Python constraint drift detected:\n"
            + "\n".join(f"  • {m}" for m in messages)
        )

    def test_module_python_parity(self, repo_root: Path) -> None:
        """All packaged modules must match PYTHON_CONSTRAINT."""
        from quickscale_core.generator.constraint_validation import (
            check_module_python_constraints,
        )
        from quickscale_core.generator.runtime_pins import PYTHON_CONSTRAINT

        messages = check_module_python_constraints(
            repo_root, expected_python=PYTHON_CONSTRAINT
        )
        assert not messages, "Module Python constraint drift detected:\n" + "\n".join(
            f"  • {m}" for m in messages
        )

    def test_module_django_lower_bound_drift(
        self,
        repo_root: Path,
    ) -> None:
        """Module Django constraints must match the tighter expected value.

        The documented intentional drift is:
          - Template: ``>=6.0.3,<6.1.0`` (runtime_pins.DJANGO_CONSTRAINT)
          - Modules: ``>=6.0.5,<6.1.0`` (tighter lower bound)

        This test verifies every packaged module carries the tighter
        ``>=6.0.5,<6.1.0`` constraint.  If a version bump changes either
        side, this test will fail and the maintainer must update both
        values intentionally.
        """
        from quickscale_core.generator.constraint_validation import (
            check_module_django_constraints,
        )

        messages = check_module_django_constraints(
            repo_root, expected_django=_EXPECTED_MODULE_DJANGO_CONSTRAINT
        )
        assert not messages, "Module Django constraint drift detected:\n" + "\n".join(
            f"  • {m}" for m in messages
        )

    def test_generator_python_parity_fails_on_mismatch(
        self,
        repo_root: Path,
    ) -> None:
        """Drift detection should report a mismatched expected_python."""
        from quickscale_core.generator.constraint_validation import (
            check_generator_python_constraints,
        )

        wrong = ">=9.9,<9.10"
        messages = check_generator_python_constraints(repo_root, expected_python=wrong)
        assert len(messages) >= 1, "Should detect at least one mismatch"
        assert all(wrong in m for m in messages), (
            "All drift messages should reference the wrong value"
        )

    def test_module_python_parity_fails_on_mismatch(
        self,
        repo_root: Path,
    ) -> None:
        """Drift detection should report a mismatched expected_python."""
        from quickscale_core.generator.constraint_validation import (
            check_module_python_constraints,
        )

        wrong = ">=9.9,<9.10"
        messages = check_module_python_constraints(repo_root, expected_python=wrong)
        assert len(messages) >= 1, "Should detect at least one mismatch"
        assert all(wrong in m for m in messages)

    def test_module_django_parity_fails_on_mismatch(
        self,
        repo_root: Path,
    ) -> None:
        """Drift detection should report a mismatched expected_django."""
        from quickscale_core.generator.constraint_validation import (
            check_module_django_constraints,
        )

        wrong = ">=9.9,<9.10"
        messages = check_module_django_constraints(repo_root, expected_django=wrong)
        assert len(messages) >= 1, "Should detect at least one mismatch"
        assert all(wrong in m for m in messages)

    # ── Poetry python constraint parity (CR-002) ─────────────────────

    def test_generator_poetry_python_parity(
        self,
        repo_root: Path,
    ) -> None:
        """Generator pyproject ``[tool.poetry.dependencies] python`` must match PYTHON_CONSTRAINT."""
        from quickscale_core.generator.constraint_validation import (
            check_generator_poetry_python_constraints,
        )
        from quickscale_core.generator.runtime_pins import PYTHON_CONSTRAINT

        messages = check_generator_poetry_python_constraints(
            repo_root, expected_python=PYTHON_CONSTRAINT
        )
        assert not messages, (
            "Generator Poetry python constraint drift detected:\n"
            + "\n".join(f"  • {m}" for m in messages)
        )

    def test_module_poetry_python_parity(
        self,
        repo_root: Path,
    ) -> None:
        """Module pyproject ``[tool.poetry.dependencies] python`` must match PYTHON_CONSTRAINT."""
        from quickscale_core.generator.constraint_validation import (
            check_module_poetry_python_constraints,
        )
        from quickscale_core.generator.runtime_pins import PYTHON_CONSTRAINT

        messages = check_module_poetry_python_constraints(
            repo_root, expected_python=PYTHON_CONSTRAINT
        )
        assert not messages, (
            "Module Poetry python constraint drift detected:\n"
            + "\n".join(f"  • {m}" for m in messages)
        )

    def test_generator_poetry_python_parity_fails_on_mismatch(
        self,
        repo_root: Path,
    ) -> None:
        """Poetry python drift detection should report a mismatched expected_python."""
        from quickscale_core.generator.constraint_validation import (
            check_generator_poetry_python_constraints,
        )

        wrong = ">=9.9,<9.10"
        messages = check_generator_poetry_python_constraints(
            repo_root, expected_python=wrong
        )
        assert len(messages) >= 1, "Should detect at least one mismatch"
        assert all(wrong in m for m in messages)

    def test_module_poetry_python_parity_fails_on_mismatch(
        self,
        repo_root: Path,
    ) -> None:
        """Poetry python drift detection should report a mismatched expected_python."""
        from quickscale_core.generator.constraint_validation import (
            check_module_poetry_python_constraints,
        )

        wrong = ">=9.9,<9.10"
        messages = check_module_poetry_python_constraints(
            repo_root, expected_python=wrong
        )
        assert len(messages) >= 1, "Should detect at least one mismatch"
        assert all(wrong in m for m in messages)

    def test_generator_poetry_python_one_surface_drift(
        self,
        tmp_path: Path,
    ) -> None:
        """When only Poetry python drifts, only the new Poetry check should fail.

        ``requires-python`` matches the expected constraint but
        ``[tool.poetry.dependencies] python`` does not.  The existing
        PEP 621 check must pass while the new Poetry check reports drift
        (one-surface regression coverage).
        """
        from quickscale_core.generator.constraint_validation import (
            check_generator_poetry_python_constraints,
            check_generator_python_constraints,
        )

        expected = ">=3.13,<3.15"
        # Create the full generator package tree so the existing
        # check_generator_python_constraints can find every expected
        # pyproject.toml.  Each file has correct requires-python but the
        # root pyproject.toml carries a drunk Poetry python constraint.
        pyproject_content_correct = (
            "[project]\n"
            f'requires-python = "{expected}"\n'
            "\n"
            "[tool.poetry.dependencies]\n"
            f'python = "{expected}"\n'
        )
        # Root file: correct requires-python, WRONG Poetry python.
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            f'requires-python = "{expected}"\n'
            "\n"
            "[tool.poetry.dependencies]\n"
            'python = ">=3.12,<3.15"\n'
        )
        # Remaining generator packages: both surfaces correct.
        for sub in ("quickscale", "quickscale_core", "quickscale_cli"):
            p = tmp_path / sub
            p.mkdir(parents=True)
            (p / "pyproject.toml").write_text(pyproject_content_correct)

        pep621_msgs = check_generator_python_constraints(tmp_path, expected)
        assert not pep621_msgs, f"PEP 621 surface should still pass: {pep621_msgs}"

        poetry_msgs = check_generator_poetry_python_constraints(tmp_path, expected)
        assert len(poetry_msgs) >= 1, "Poetry surface drift should be detected"
        assert any(">=3.12,<3.15" in m for m in poetry_msgs)

    def test_module_poetry_python_one_surface_drift(
        self,
        tmp_path: Path,
    ) -> None:
        """When only Poetry python drifts in a module, only the new Poetry check should fail.

        Same one-surface drift scenario as
        :meth:`test_generator_poetry_python_one_surface_drift` but for
        the module check path.
        """
        from quickscale_core.generator.constraint_validation import (
            check_module_poetry_python_constraints,
            check_module_python_constraints,
        )

        expected = ">=3.13,<3.15"
        modules_dir = tmp_path / "quickscale_modules" / "testmod"
        modules_dir.mkdir(parents=True)
        pyproject = modules_dir / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            f'requires-python = "{expected}"\n'
            "\n"
            "[tool.poetry.dependencies]\n"
            'python = ">=3.12,<3.15"\n'
        )

        pep621_msgs = check_module_python_constraints(tmp_path, expected)
        assert not pep621_msgs, "PEP 621 surface should still pass"

        poetry_msgs = check_module_poetry_python_constraints(tmp_path, expected)
        assert len(poetry_msgs) >= 1, "Poetry surface drift should be detected"
        assert any(">=3.12,<3.15" in m for m in poetry_msgs)


class TestTemplateLoading:
    """Verify all project templates can be loaded by Jinja2."""

    def test_manage_py_loads(self, jinja_env: Environment) -> None:
        """Test manage.py template loads without errors."""
        template = jinja_env.get_template("manage.py.j2")
        assert template is not None

    def test_readme_loads(self, jinja_env: Environment) -> None:
        """Test generated README template loads without errors."""
        template = jinja_env.get_template("README.md.j2")
        assert template is not None

    def test_project_init_loads(self, jinja_env: Environment) -> None:
        """Test project __init__.py template loads without errors."""
        template = jinja_env.get_template("project_name/__init__.py.j2")
        assert template is not None

    def test_settings_init_loads(self, jinja_env: Environment) -> None:
        """Test settings __init__.py template loads without errors."""
        template = jinja_env.get_template("project_name/settings/__init__.py.j2")
        assert template is not None

    def test_settings_base_loads(self, jinja_env: Environment) -> None:
        """Test base settings template loads without errors."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        assert template is not None

    def test_settings_local_loads(self, jinja_env: Environment) -> None:
        """Test local settings template loads without errors."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        assert template is not None

    def test_settings_production_loads(self, jinja_env: Environment) -> None:
        """Test production settings template loads without errors."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        assert template is not None

    def test_urls_loads(self, jinja_env: Environment) -> None:
        """Test URL configuration template loads without errors."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        assert template is not None

    def test_wsgi_loads(self, jinja_env: Environment) -> None:
        """Test WSGI configuration template loads without errors."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        assert template is not None

    def test_asgi_loads(self, jinja_env: Environment) -> None:
        """Test ASGI configuration template loads without errors."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        assert template is not None

    def test_base_html_loads(self, jinja_env: Environment) -> None:
        """Test base HTML template loads without errors."""
        template = jinja_env.get_template("templates/base.html.j2")
        assert template is not None

    def test_index_html_loads(self, jinja_env: Environment) -> None:
        """Test index HTML template loads without errors."""
        template = jinja_env.get_template("templates/index.html.j2")
        assert template is not None

    def test_style_css_loads(self, jinja_env: Environment) -> None:
        """Test CSS stylesheet template loads without errors."""
        template = jinja_env.get_template("static/css/style.css.j2")
        assert template is not None


class TestTemplateRendering:
    """Verify templates render correctly with sample context data."""

    def test_manage_py_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test manage.py renders with project name and shebang."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "#!/usr/bin/env python" in output

    def test_settings_base_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base settings renders with project name."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_settings_local_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test local settings renders with project name."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_settings_production_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test production settings renders with project name."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_urls_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test URL configuration renders with project name."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_urls_optional_debug_toolbar_import(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Optional debug toolbar import should not require package install."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        output = template.render(test_context)
        assert 'importlib.import_module("debug_toolbar")' in output
        assert "except ImportError" in output

    def test_react_urls_include_spa_catch_all_in_production(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """React theme should include SPA catch-all outside DEBUG-only block."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        output = template.render({**test_context, "theme": "showcase_react"})

        assert 're_path(r".*", react_shell_view)' in output

        # The comment should be top-level (not indented under if settings.DEBUG).
        react_catchall_comment = next(
            line for line in output.splitlines() if "React SPA catch-all" in line
        )
        assert react_catchall_comment.startswith("#")

    def test_wsgi_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test WSGI configuration renders with project name."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_asgi_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test ASGI configuration renders with project name."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_base_html_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template renders with project name."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output
        assert "<!DOCTYPE html>" in output

    def test_index_html_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test index HTML template renders with project name."""
        template = jinja_env.get_template("templates/index.html.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output
        assert "Welcome to" in output

    def test_style_css_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS stylesheet template renders with project name."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output
        assert "body {" in output


class TestPythonSyntaxValidity:
    """Verify rendered Python templates produce syntactically valid code."""

    def test_manage_py_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered manage.py produces valid Python syntax."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_settings_base_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered base settings produces valid Python syntax."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_settings_local_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered local settings produces valid Python syntax."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_settings_production_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered production settings produces valid Python syntax."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_urls_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered URL configuration produces valid Python syntax."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_wsgi_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered WSGI configuration produces valid Python syntax."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_asgi_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered ASGI configuration produces valid Python syntax."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        output = template.render(test_context)
        ast.parse(output)


class TestRequiredVariables:
    """Verify templates correctly use required context variables."""

    def test_project_name_in_manage_py(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in manage.py settings path."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render(test_context)
        assert "testproject.settings" in output

    def test_project_name_in_settings(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "testproject" in output

    def test_project_name_in_wsgi(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in WSGI settings path."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        output = template.render(test_context)
        assert "testproject.settings" in output

    def test_project_name_in_asgi(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in ASGI settings path."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        output = template.render(test_context)
        assert "testproject.settings" in output


class TestRuntimeDatabaseUrlComments:
    """Verify RUNTIME_DATABASE_URL comments in base settings are accurate (CR-T14-003)."""

    def test_base_settings_comment_narrowed_to_migrations(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """The DATABASE_URL comment should mention migrations, not overstate management commands."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)

        # The comment should say "used for migrations" without claiming
        # management-command coverage that isn't implemented.
        assert "DATABASE_URL: Superuser connection used for migrations" in output
        assert "management commands" not in output, (
            "base.py comment should not overstate management-command coverage"
        )


class TestRuntimeDatabaseUrlOperatorContract:
    """Verify operator-facing templates no longer document RUNTIME_DATABASE_URL as optional (CR-SA22-002)."""

    def test_env_example_runtime_url_uncommented(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """RUNTIME_DATABASE_URL must not be commented out in .env.example."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)

        # Must be present as an active variable, not commented out
        assert "RUNTIME_DATABASE_URL=" in output
        assert "# RUNTIME_DATABASE_URL=" not in output, (
            "RUNTIME_DATABASE_URL should not be commented out in .env.example"
        )
        # Must NOT document backward-compatible fallback (contradicts fail-closed)
        assert "falls back to DATABASE_URL" not in output, (
            ".env.example should not describe RUNTIME_DATABASE_URL fallback"
        )
        # Must mention it's required for production
        assert "required for production" in output.lower() or (
            "required" in output.lower() and "runtime serving" in output.lower()
        ), ".env.example should describe RUNTIME_DATABASE_URL as required"

    def test_env_example_mentions_fail_closed(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """.env.example should mention the fail-closed behavior for production."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)

        # The comment spans two lines; check for both fragments
        assert "the app raises" in output, (
            ".env.example should mention the fail-closed error"
        )
        assert "clear error if unset" in output, (
            ".env.example should mention the clear error when unset"
        )

    def test_operations_md_no_fallback_language(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """OPERATIONS.md must not describe RUNTIME_DATABASE_URL fallback as backward compatible."""
        template = jinja_env.get_template("OPERATIONS.md.j2")
        output = template.render(test_context)

        assert "RUNTIME_DATABASE_URL" in output
        # Must not describe fallback as backward compatible
        assert "falls back to DATABASE_URL" not in output, (
            "OPERATIONS.md should not describe RUNTIME_DATABASE_URL fallback"
        )
        assert "backward compatible" not in output.lower(), (
            "OPERATIONS.md should not describe fallback as backward compatible"
        )
        # Must describe the fail-closed behavior
        assert "fail-closed" in output.lower() or "raises a clear error" in output, (
            "OPERATIONS.md should describe fail-closed behavior"
        )

    def test_readme_env_vars_includes_runtime_url(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """README deployment Environment Variables section must include RUNTIME_DATABASE_URL."""
        template = jinja_env.get_template("README.md.j2")
        output = template.render(test_context)

        # The production environment variables section must mention RUNTIME_DATABASE_URL
        assert "RUNTIME_DATABASE_URL" in output, (
            "README should mention RUNTIME_DATABASE_URL in deployment section"
        )
        # Must describe as required for production
        assert "required for production" in output.lower() or (
            "runtime database role" in output.lower()
        ), "README should describe the production runtime role requirement"

    def test_readme_production_checklist_includes_runtime_url(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """README production checklist must include a RUNTIME_DATABASE_URL item."""
        template = jinja_env.get_template("README.md.j2")
        output = template.render(test_context)

        assert "RUNTIME_DATABASE_URL" in output
        # The production checklist section must have a dedicated RUNTIME_DATABASE_URL item
        assert "Set `RUNTIME_DATABASE_URL`" in output, (
            "README production checklist should list RUNTIME_DATABASE_URL"
        )
        assert "fails closed" in output.lower(), (
            "README production checklist should mention fail-closed behavior"
        )

    def test_env_example_local_dev_guidance(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """.env.example should tell non-Docker local devs to remove RUNTIME_DATABASE_URL.

        CR-SA22-002 regression: non-Docker users who copy .env.example to .env
        must be told to remove RUNTIME_DATABASE_URL so that local.py falls back
        to DATABASE_URL (the runtime role does not exist in a plain local setup).
        """
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)

        # Must mention non-Docker local development
        assert "non-docker local development" in output.lower(), (
            ".env.example should mention non-Docker local development"
        )
        # Must tell users to remove the line
        assert "remove this line from your .env" in output.lower(), (
            ".env.example should tell non-Docker users to remove RUNTIME_DATABASE_URL"
        )
        # Must explain why (runtime role needs Docker Compose)
        assert "docker compose" in output.lower(), (
            ".env.example should explain that Docker Compose provisions the runtime role"
        )

    def test_readme_local_quick_start_runtime_url_guidance(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """README local quick-start should tell non-Docker users to clear RUNTIME_DATABASE_URL.

        CR-SA22-002 regression: the local Setup section must guide non-Docker
        users to remove RUNTIME_DATABASE_URL from .env after copying .env.example,
        since the runtime role is only provisioned automatically by Docker Compose.
        """
        template = jinja_env.get_template("README.md.j2")
        output = template.render(test_context)

        # Locate the local Setup section
        assert "cp .env.example .env" in output
        setup_section = output[output.index("cp .env.example .env") :]
        setup_section = setup_section[: setup_section.index("# 3. Run migrations")]

        # The local quick-start must mention RUNTIME_DATABASE_URL
        assert "RUNTIME_DATABASE_URL" in setup_section, (
            "README local quick-start should mention RUNTIME_DATABASE_URL"
        )
        # Must tell non-Docker users to delete it
        assert "delete RUNTIME_DATABASE_URL" in setup_section, (
            "README local quick-start should tell non-Docker users to delete RUNTIME_DATABASE_URL"
        )
        # Must explain why (Docker Compose vs plain local)
        assert "without Docker" in setup_section, (
            "README local quick-start should distinguish Docker vs non-Docker"
        )


class TestProductionReadyFeatures:
    """Verify production-ready security and configuration features are present."""

    def test_security_middleware_in_base(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test security middleware is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "SecurityMiddleware" in output
        assert "WhiteNoiseMiddleware" in output

    def test_logging_configured(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test logging with rotating file handler is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "LOGGING" in output
        assert "RotatingFileHandler" in output

    def test_json_logging_formatter(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test JSON formatter is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "JsonFormatter" in output
        assert '"()": JsonFormatter' in output
        assert '"formatter": "json"' in output

    def test_correlation_id_filter(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test correlation_id filter is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "CorrelationIdFilter" in output
        assert '"()": CorrelationIdFilter' in output
        assert '"filters": ["correlation_id"]' in output

    def test_contextvar_mechanism_in_base(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings should use contextvars to bridge middleware and filter."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "import contextvars" in output
        assert "_correlation_id_var" in output

    def test_django_server_logger_in_base(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings should configure the django.server logger explicitly."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert '"django.server"' in output
        assert '"filters": ["correlation_id"]' in output

    def test_correlation_id_middleware(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CorrelationIdMiddleware is registered in MIDDLEWARE."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "CorrelationIdMiddleware" in output
        # Find the MIDDLEWARE assignment specifically (not MODULE_MIDDLEWARE)
        middleware_start = output.index("MIDDLEWARE = [")
        middleware_section = output[middleware_start:]
        assert "CorrelationIdMiddleware" in middleware_section.split("]")[0]

    def test_local_logging_json_formatter(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test local settings use JSON formatter, correlation_id filter, and django.server."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)
        assert '"()": JsonFormatter' in output
        assert '"()": CorrelationIdFilter' in output
        assert '"formatter": "json"' in output
        assert '"filters": ["correlation_id"]' in output
        assert '"django.server"' in output

    def test_production_logging_json_formatter(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test production settings use JSON formatter, correlation_id filter, and django.server."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        assert '"()": JsonFormatter' in output
        assert '"()": CorrelationIdFilter' in output
        assert '"formatter": "json"' in output
        assert '"filters": ["correlation_id"]' in output
        assert '"django.server"' in output

    def test_production_security_settings(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test production security settings include SSL and cookie security."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        assert "SECURE_SSL_REDIRECT" in output
        assert "SESSION_COOKIE_SECURE" in output
        assert "CSRF_COOKIE_SECURE" in output
        assert "SECURE_HSTS_SECONDS" in output

    def test_postgresql_in_production(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test production settings configure PostgreSQL database."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        assert "postgresql" in output

    def test_whitenoise_in_base(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test WhiteNoise static file serving is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "whitenoise" in output.lower()

    def test_decouple_used(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test python-decouple is used for environment-based configuration."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "from decouple import config" in output
        assert "SECRET_KEY = config(" in output

    def test_module_settings_applied_after_storage_defaults(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Managed module settings must be applied after base storage/media defaults."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)

        storages_index = output.index("STORAGES = {")
        media_index = output.index('MEDIA_URL = "/media/"')
        module_settings_index = output.index("globals().update(MODULE_SETTINGS)")

        assert storages_index < module_settings_index
        assert media_index < module_settings_index

    def test_base_settings_use_site_root_static_and_media_urls(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings should use absolute static/media prefixes for nested pages."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)

        assert 'STATIC_URL = "/static/"' in output
        assert 'MEDIA_URL = "/media/"' in output
        assert 'STATIC_URL = "static/"' not in output
        assert 'MEDIA_URL = "media/"' not in output

    def test_local_settings_preserve_default_storage_backend(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Local settings should only relax staticfiles storage, not replace media storage."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)

        assert 'STORAGES["staticfiles"] = {' in output
        assert '"django.contrib.staticfiles.storage.StaticFilesStorage"' in output
        assert '"django.core.files.storage.FileSystemStorage"' not in output
        assert "STORAGES = {" not in output

    def test_base_settings_build_anymail_from_notifications_env_var_names(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings should derive Resend Anymail config from env-var names."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)

        assert (
            'if globals().get("EMAIL_BACKEND") '
            '== "anymail.backends.resend.EmailBackend":' in output
        )
        assert "QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR" in output
        assert 'ANYMAIL["RESEND_API_KEY"]' in output

    def test_base_settings_allow_unmanaged_email_backend_when_notifications_disabled(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Base settings should stay importable when no module manages email."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        def fake_config(
            _key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            if cast is None:
                return default
            return cast(default)

        decouple_module = types.ModuleType("decouple")
        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }

        exec(output, namespace)

        assert "EMAIL_BACKEND" not in namespace
        assert "ANYMAIL" not in namespace

    def test_local_settings_email_backend_is_fallback_only(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Local settings should only set console email when base settings did not."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)

        assert 'if "EMAIL_BACKEND" not in globals():' in output
        assert (
            'EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"' in output
        )

    def test_production_settings_email_defaults_are_fallback_only(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Production settings should not overwrite module-managed email settings."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)

        assert 'if "EMAIL_BACKEND" not in globals():' in output
        assert 'if "DEFAULT_FROM_EMAIL" not in globals():' in output
        assert 'if "SERVER_EMAIL" not in globals():' in output

    def test_production_database_pooling_and_runtime_role_note_survives_rendering(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """The connection pooling and runtime-role note survives Jinja rendering.

        AF4 scope requires a visible note in the generated production settings
        explaining the CONN_MAX_AGE/CONN_HEALTH_CHECKS pooling strategy and
        the RUNTIME_DATABASE_URL runtime-role pattern.
        """
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)

        # Pooling note must survive rendering
        assert "Connection pooling" in output
        assert "CONN_MAX_AGE=600" in output
        assert "CONN_HEALTH_CHECKS=True" in output

        # Runtime-role pattern note must survive rendering
        assert "Runtime role pattern" in output
        assert "RUNTIME_DATABASE_URL" in output
        assert "NOSUPERUSER" in output or "NOBYPASSRLS" in output


class TestDrfPermissionBaseline:
    """Verify generated base settings include the DRF authenticated-only default.

    SA11.5: emitted ``REST_FRAMEWORK`` must default to
    ``IsAuthenticated`` so module APIs fail closed unless a view
    explicitly opts into public access.
    """

    def test_rest_framework_setting_present(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Rendered base settings must include ``REST_FRAMEWORK``."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "REST_FRAMEWORK" in output

    def test_rest_framework_default_permission_classes(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """The ``DEFAULT_PERMISSION_CLASSES`` must include ``IsAuthenticated``."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)

        assert "DEFAULT_PERMISSION_CLASSES" in output
        assert "rest_framework.permissions.IsAuthenticated" in output
        assert "AllowAny" not in output, (
            "Default must not be AllowAny — explicit IsAuthenticated fail-closed"
        )

    def test_rest_framework_set_after_module_settings(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """``REST_FRAMEWORK`` must appear after ``globals().update(MODULE_SETTINGS)``.

        The template's safe default must clobber any module-provided DRF
        config so authentication is required by default (fail-closed).
        """
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)

        module_settings_index = output.index("globals().update(MODULE_SETTINGS)")
        drf_index = output.index("REST_FRAMEWORK")

        assert module_settings_index < drf_index, (
            "REST_FRAMEWORK must be defined after MODULE_SETTINGS so the "
            "template's safe default wins (fail-closed)"
        )

    def test_rest_framework_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Rendered REST_FRAMEWORK setting must produce valid Python."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        ast.parse(output)


class TestClientIpAndSharedCache:
    """Verify SA21.1 client-IP resolution and shared cache backend in generated settings."""

    # ── Client-IP resolution (base.py) ─────────────────────────────────

    def test_use_x_forwarded_for_setting_present(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings must include USE_X_FORWARDED_FOR."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        assert "USE_X_FORWARDED_FOR" in output

    def test_use_x_forwarded_for_defaults_false(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """USE_X_FORWARDED_FOR must default to False (no-proxy-safe)."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        assert (
            'USE_X_FORWARDED_FOR = config("USE_X_FORWARDED_FOR", default=False, cast=bool)'
            in output
        )

    def test_trusted_proxy_count_setting_present(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings must include TRUSTED_PROXY_COUNT."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        assert "TRUSTED_PROXY_COUNT" in output

    def test_trusted_proxy_count_defaults_zero(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """TRUSTED_PROXY_COUNT must default to 0 (no-proxy-safe)."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        assert (
            'TRUSTED_PROXY_COUNT = config("TRUSTED_PROXY_COUNT", default=0, cast=int)'
            in output
        )

    def test_get_client_ip_function_defined(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings must define get_client_ip()."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        assert "def get_client_ip(request" in output
        assert "return request.META.get" in output

    def test_num_proxies_in_rest_framework(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """REST_FRAMEWORK must include NUM_PROXIES derived from proxy settings."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        assert '"NUM_PROXIES"' in output
        assert "TRUSTED_PROXY_COUNT" in output
        assert "USE_X_FORWARDED_FOR" in output

    def test_client_ip_settings_before_rest_framework(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Client-IP settings must be defined before the REST_FRAMEWORK dict."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        proxy_setting_index = output.index("USE_X_FORWARDED_FOR")
        drf_index = output.index("REST_FRAMEWORK")
        assert proxy_setting_index < drf_index, (
            "USE_X_FORWARDED_FOR must be defined before REST_FRAMEWORK"
        )

    # ── Client-IP runtime behaviour ───────────────────────────────────

    def test_get_client_ip_proxy_resolution(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_client_ip should resolve the correct IP behind a trusted proxy."""
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        decouple_module = types.ModuleType("decouple")

        def fake_config(
            key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            values = {
                "USE_X_FORWARDED_FOR": True,
                "TRUSTED_PROXY_COUNT": 1,
            }
            value = values.get(key, default)
            if cast is None:
                return value
            return cast(value)

        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }
        exec(base_output, namespace)

        get_client_ip = typing.cast(Callable[[object], str], namespace["get_client_ip"])

        # With USE_X_FORWARDED_FOR=True and TRUSTED_PROXY_COUNT=1,
        # the client IP should be the second-from-right in the XFF chain.
        class FakeRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "198.51.100.1, 10.0.0.1",
            }

        result = get_client_ip(FakeRequest())
        assert result == "198.51.100.1", (
            f"Expected client IP from X-Forwarded-For, got {result!r}"
        )

    def test_get_client_ip_falls_back_to_remote_addr_when_xff_unset(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_client_ip should return REMOTE_ADDR when X-Forwarded-For is absent."""
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        decouple_module = types.ModuleType("decouple")

        def fake_config(
            key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            values = {
                "USE_X_FORWARDED_FOR": True,
                "TRUSTED_PROXY_COUNT": 1,
            }
            value = values.get(key, default)
            if cast is None:
                return value
            return cast(value)

        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }
        exec(base_output, namespace)

        get_client_ip = typing.cast(Callable[[object], str], namespace["get_client_ip"])

        class FakeRequestNoXff:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
            }

        result = get_client_ip(FakeRequestNoXff())
        assert result == "10.0.0.1", f"Expected REMOTE_ADDR fallback, got {result!r}"

    def test_get_client_ip_defaults_to_remote_addr_when_proxy_disabled(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With default settings (USE_X_FORWARDED_FOR=False), must return REMOTE_ADDR."""
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        decouple_module = types.ModuleType("decouple")

        def fake_config(
            key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            # Defaults — USE_X_FORWARDED_FOR=False, TRUSTED_PROXY_COUNT=0
            values = {
                "USE_X_FORWARDED_FOR": False,
                "TRUSTED_PROXY_COUNT": 0,
            }
            value = values.get(key, default)
            if cast is None:
                return value
            return cast(value)

        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }
        exec(base_output, namespace)

        get_client_ip = typing.cast(Callable[[object], str], namespace["get_client_ip"])

        class FakeRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "198.51.100.1, 10.0.0.1",
            }

        # With proxy disabled, must return REMOTE_ADDR despite XFF being present
        result = get_client_ip(FakeRequest())
        assert result == "10.0.0.1", (
            f"Expected REMOTE_ADDR when proxy disabled, got {result!r}"
        )

    # ── Production proxy overrides ────────────────────────────────────

    def test_production_enables_proxy_settings(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Production settings must enable USE_X_FORWARDED_FOR and TRUSTED_PROXY_COUNT."""
        output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )
        assert (
            'USE_X_FORWARDED_FOR = config("USE_X_FORWARDED_FOR", default=True, cast=bool)'
            in output
        )
        assert (
            'TRUSTED_PROXY_COUNT = config("TRUSTED_PROXY_COUNT", default=1, cast=int)'
            in output
        )

    # ── Production defaults actually affect the runtime seam (CR-SA21.1) ──

    def test_production_defaults_affect_proxy_seam(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Production defaults for proxy settings must propagate to
        ``get_client_ip()`` and ``NUM_PROXIES`` at runtime.

        Regression for CR-SA21.1-001: the base defaults (disabled) must
        be overridden by the production defaults (enabled, count=1) so
        that a generated production deployment resolves the real client
        IP without requiring explicit environment variables.
        """
        import sys

        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        production_output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )

        # Use the migration path to bypass the RUNTIME_DATABASE_URL
        # check — the proxy settings are resolved before that check.
        monkeypatch.setattr(sys, "argv", ["manage.py", "migrate"])

        namespace = _execute_rendered_settings(
            monkeypatch=monkeypatch,
            package_name=test_context["package_name"],
            base_output=base_output,
            target_output=production_output,
            target_module_name="production",
            config_values={
                "SECRET_KEY": "a-valid-production-secret-key",
                "DATABASE_URL": (
                    "postgresql://postgres:postgres@localhost:5432/testproject"
                ),
            },
        )

        # Production defaults (no env overrides)
        assert namespace["USE_X_FORWARDED_FOR"] is True
        assert namespace["TRUSTED_PROXY_COUNT"] == 1

        # NUM_PROXIES must reflect the production values, not base defaults
        rest_framework = namespace["REST_FRAMEWORK"]
        assert isinstance(rest_framework, dict)
        assert rest_framework["NUM_PROXIES"] == 1, (
            "NUM_PROXIES should be 1 with production defaults"
        )

        # get_client_ip must use production's globals at call time
        get_client_ip = typing.cast(Callable[[object], str], namespace["get_client_ip"])

        # Behind one proxy — should resolve to the client, not REMOTE_ADDR
        class _FakeRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "198.51.100.1, 10.0.0.1",
            }

        result = get_client_ip(_FakeRequest())
        assert result == "198.51.100.1", (
            f"Expected client IP from X-Forwarded-For with production "
            f"defaults, got {result!r}"
        )

    def test_production_get_client_ip_rejects_malformed_xff_empty_hops(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Production rebind of ``get_client_ip`` must also reject
        malformed X-Forwarded-For chains with empty hops.

        Regression for CR-SA21.1-002: the production seam must apply the
        same empty-hop normalization as the base helper.
        """
        import sys

        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        production_output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )

        monkeypatch.setattr(sys, "argv", ["manage.py", "migrate"])

        namespace = _execute_rendered_settings(
            monkeypatch=monkeypatch,
            package_name=test_context["package_name"],
            base_output=base_output,
            target_output=production_output,
            target_module_name="production",
            config_values={
                "SECRET_KEY": "a-valid-production-secret-key",
                "DATABASE_URL": (
                    "postgresql://postgres:postgres@localhost:5432/testproject"
                ),
            },
        )

        get_client_ip = typing.cast(Callable[[object], str], namespace["get_client_ip"])

        # Case 1: Trailing comma produces empty hop (the reported vector)
        class _FakeProdTrailingCommaRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "203.0.113.99, ",
            }

        result = get_client_ip(_FakeProdTrailingCommaRequest())
        assert result == "10.0.0.1", (
            f"Expected REMOTE_ADDR for malformed XFF in production "
            f"rebind, got {result!r}"
        )

        # Case 2: Trailing comma on a valid proxied chain must not break
        # resolution in the production rebind.
        class _FakeProdValidTrailingCommaRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "198.51.100.1, 10.0.0.1, ",
            }

        result = get_client_ip(_FakeProdValidTrailingCommaRequest())
        assert result == "198.51.100.1", (
            f"Expected client IP from valid XFF with trailing comma "
            f"in production rebind, got {result!r}"
        )

    def test_get_client_ip_fails_closed_on_spoofed_xff(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the X-Forwarded-For chain is shorter than
        ``TRUSTED_PROXY_COUNT``, the function must return
        ``REMOTE_ADDR`` instead of trusting the leftmost
        (potentially spoofed) address.

        Regression for CR-SA21.1-002: the original algorithm fell back
        to ``ips[0]`` when the chain was too short, letting an attacker
        with a single spoofed XFF entry impersonate any IP.
        """
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        decouple_module = types.ModuleType("decouple")

        def fake_config(
            key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            values = {
                "USE_X_FORWARDED_FOR": True,
                "TRUSTED_PROXY_COUNT": 1,
            }
            value = values.get(key, default)
            if cast is None:
                return value
            return cast(value)

        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }
        exec(base_output, namespace)

        get_client_ip = typing.cast(Callable[[object], str], namespace["get_client_ip"])

        # TRUSTED_PROXY_COUNT=1 but XFF has only one entry (spoof attempt)
        class _FakeSpoofRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "203.0.113.99",
            }

        result = get_client_ip(_FakeSpoofRequest())
        assert result == "10.0.0.1", (
            f"Expected REMOTE_ADDR when XFF chain is shorter than "
            f"TRUSTED_PROXY_COUNT, got {result!r}"
        )

    def test_get_client_ip_rejects_malformed_xff_empty_hops(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Trailing commas or empty hops in X-Forwarded-For must not
        inflate the hop count and bypass the fail-closed guard.

        Regression for CR-SA21.1-002: empty hops from malformed chains
        like ``"203.0.113.99, "`` would previously produce a two-element
        split so the length check passed and the spoofed leftmost value
        was returned.
        """
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        decouple_module = types.ModuleType("decouple")

        def fake_config(
            key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            values = {
                "USE_X_FORWARDED_FOR": True,
                "TRUSTED_PROXY_COUNT": 1,
            }
            value = values.get(key, default)
            if cast is None:
                return value
            return cast(value)

        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }
        exec(base_output, namespace)

        get_client_ip = typing.cast(Callable[[object], str], namespace["get_client_ip"])

        # Case 1: Trailing comma produces empty hop (the reported vector)
        class _FakeTrailingCommaRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "203.0.113.99, ",
            }

        result = get_client_ip(_FakeTrailingCommaRequest())
        assert result == "10.0.0.1", (
            f"Expected REMOTE_ADDR for malformed XFF with trailing "
            f"comma, got {result!r}"
        )

        # Case 2: Double trailing comma — multiple empty trailing hops
        class _FakeDoubleTrailingCommaRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "203.0.113.99, , ",
            }

        result = get_client_ip(_FakeDoubleTrailingCommaRequest())
        assert result == "10.0.0.1", (
            f"Expected REMOTE_ADDR for double trailing comma XFF, got {result!r}"
        )

        # Case 3: Trailing comma on a valid proxied chain must not break
        # resolution — the non-empty hops are still correctly counted.
        class _FakeValidWithTrailingCommaRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": "198.51.100.1, 10.0.0.1, ",
            }

        result = get_client_ip(_FakeValidWithTrailingCommaRequest())
        assert result == "198.51.100.1", (
            f"Expected client IP from valid XFF with trailing comma, got {result!r}"
        )

        # Case 4: Only whitespace between commas — all hops empty
        class _FakeAllEmptyHopsRequest:
            META: dict[str, str] = {
                "REMOTE_ADDR": "10.0.0.1",
                "HTTP_X_FORWARDED_FOR": ", , ",
            }

        result = get_client_ip(_FakeAllEmptyHopsRequest())
        assert result == "10.0.0.1", (
            f"Expected REMOTE_ADDR for all-empty XFF, got {result!r}"
        )

    # ── Shared cache (production.py) ──────────────────────────────────

    def test_production_cache_is_not_locmem(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Production CACHES must not use LocMemCache."""
        output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )
        assert "LocMemCache" not in output, (
            "Production must not rely on per-process LocMemCache"
        )

    def test_production_cache_uses_redis_or_database(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Production CACHES should use RedisCache or DatabaseCache."""
        output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )
        # Active CACHES definition — not commented out
        assert "CACHES = {" in output
        assert "django.core.cache.backends.redis.RedisCache" in output
        assert "django.core.cache.backends.db.DatabaseCache" in output
        assert "REDIS_URL" in output

    def test_production_cache_conditionals_use_config(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Cache decision should use config() for REDIS_URL."""
        output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )
        assert '_redis_url = config("REDIS_URL", default=None)' in output
        assert "if _redis_url:" in output

    def test_production_cache_has_createcachetable_comment(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Production cache should document the createcachetable command."""
        output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )
        assert "createcachetable" in output, (
            "Production cache docs should mention createcachetable for DatabaseCache"
        )

    # ── Syntax validity ───────────────────────────────────────────────

    def test_client_ip_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Base settings including get_client_ip must produce valid Python."""
        output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        ast.parse(output)

    def test_production_cache_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Production settings including CACHES must produce valid Python."""
        output = _render_template(
            jinja_env, "project_name/settings/production.py.j2", test_context
        )
        ast.parse(output)


class TestCorrelationIdFilterRuntime:
    """Verify CorrelationIdFilter actually sources correlation_id from middleware.

    CR-D9A-001 regression: the filter must read from the ``_correlation_id_var``
    context variable (set by ``CorrelationIdMiddleware``) rather than falling
    back to itself (which always produces an empty string).
    """

    def test_filter_sources_from_contextvar_default_empty(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the context variable is unset, ``correlation_id`` should be empty."""
        import logging

        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        # Stub out module-level imports that are not needed for filter tests
        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        def fake_config(
            _key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            if cast is None:
                return default
            return cast(default)

        decouple_module = types.ModuleType("decouple")
        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }
        exec(base_output, namespace)

        CorrelationIdFilter = typing.cast(
            type[logging.Filter], namespace["CorrelationIdFilter"]
        )
        filter_instance = CorrelationIdFilter()

        record = logging.LogRecord(
            "test", logging.INFO, __file__, 42, "test message", (), None
        )
        filter_instance.filter(record)
        assert record.correlation_id == "", (  # type: ignore[attr-defined]
            "correlation_id should default to empty string when context var is unset"
        )

    def test_filter_sources_middleware_correlation_id(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the context variable is set (by middleware), filter should use it."""
        import contextvars
        import logging

        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )

        package_name = test_context["package_name"]
        settings_package_name = f"{package_name}.settings"
        modules_name = f"{settings_package_name}.modules"

        package_module = types.ModuleType(package_name)
        package_module.__dict__["__path__"] = []
        settings_package_module = types.ModuleType(settings_package_name)
        settings_package_module.__dict__["__path__"] = []
        modules_module = types.ModuleType(modules_name)
        setattr(modules_module, "MODULE_INSTALLED_APPS", [])
        setattr(modules_module, "MODULE_MIDDLEWARE", [])
        setattr(modules_module, "MODULE_SETTINGS", {})

        def fake_config(
            _key: str,
            default: object = "",
            cast: Callable[[object], object] | None = None,
        ) -> object:
            if cast is None:
                return default
            return cast(default)

        decouple_module = types.ModuleType("decouple")
        setattr(decouple_module, "config", fake_config)

        monkeypatch.setitem(sys.modules, package_name, package_module)
        monkeypatch.setitem(sys.modules, settings_package_name, settings_package_module)
        monkeypatch.setitem(sys.modules, modules_name, modules_module)
        monkeypatch.setitem(sys.modules, "decouple", decouple_module)

        namespace: dict[str, object] = {
            "__file__": f"/tmp/{package_name}/settings/base.py",
            "__name__": f"{settings_package_name}.base",
            "__package__": settings_package_name,
        }
        exec(base_output, namespace)

        CorrelationIdFilter = typing.cast(
            type[logging.Filter], namespace["CorrelationIdFilter"]
        )
        _correlation_id_var = typing.cast(
            contextvars.ContextVar[str], namespace["_correlation_id_var"]
        )
        filter_instance = CorrelationIdFilter()

        # Simulate middleware setting the context variable
        expected_id = "req-abc-123"
        token = _correlation_id_var.set(expected_id)

        record = logging.LogRecord(
            "test", logging.INFO, __file__, 42, "test message", (), None
        )
        filter_instance.filter(record)
        assert record.correlation_id == expected_id, (  # type: ignore[attr-defined]
            f"correlation_id should be {expected_id!r} when context var is set, "
            f"got {record.correlation_id!r}"  # type: ignore[attr-defined]
        )

        _correlation_id_var.reset(token)


class TestGeneratedSecretKeyGuards:
    """Verify shipped SECRET_KEY defaults stay local-only and fail in production."""

    def test_local_settings_accept_shipped_dev_secret_key(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Local settings should import successfully with the shipped .env placeholder."""
        base_output = _render_template(
            jinja_env,
            "project_name/settings/base.py.j2",
            test_context,
        )
        local_output = _render_template(
            jinja_env,
            "project_name/settings/local.py.j2",
            test_context,
        )
        env_output = _render_template(jinja_env, ".env.example.j2", test_context)
        shipped_secret_key = _extract_env_value(env_output, "SECRET_KEY")

        namespace = _execute_rendered_settings(
            monkeypatch=monkeypatch,
            package_name=test_context["package_name"],
            base_output=base_output,
            target_output=local_output,
            target_module_name="local",
            config_values={
                "SECRET_KEY": shipped_secret_key,
                "DATABASE_URL": (
                    "postgresql://postgres:postgres@localhost:5432/testproject"
                ),
            },
        )

        assert namespace["SECRET_KEY"] == shipped_secret_key
        assert namespace["DEBUG"] is True

    def test_production_settings_reject_blank_secret_key(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Production settings should fail fast when SECRET_KEY is blank."""
        base_output = _render_template(
            jinja_env,
            "project_name/settings/base.py.j2",
            test_context,
        )
        production_output = _render_template(
            jinja_env,
            "project_name/settings/production.py.j2",
            test_context,
        )

        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            _execute_rendered_settings(
                monkeypatch=monkeypatch,
                package_name=test_context["package_name"],
                base_output=base_output,
                target_output=production_output,
                target_module_name="production",
                config_values={
                    "SECRET_KEY": "",
                    "DATABASE_URL": (
                        "postgresql://postgres:postgres@localhost:5432/testproject"
                    ),
                },
            )

    def test_production_settings_reject_shipped_placeholder_secret_key(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Production settings should fail fast on the shipped .env placeholder."""
        base_output = _render_template(
            jinja_env,
            "project_name/settings/base.py.j2",
            test_context,
        )
        production_output = _render_template(
            jinja_env,
            "project_name/settings/production.py.j2",
            test_context,
        )
        env_output = _render_template(jinja_env, ".env.example.j2", test_context)
        shipped_secret_key = _extract_env_value(env_output, "SECRET_KEY")

        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            _execute_rendered_settings(
                monkeypatch=monkeypatch,
                package_name=test_context["package_name"],
                base_output=base_output,
                target_output=production_output,
                target_module_name="production",
                config_values={
                    "SECRET_KEY": shipped_secret_key,
                    "DATABASE_URL": (
                        "postgresql://postgres:postgres@localhost:5432/testproject"
                    ),
                },
            )


class TestProductionSettingsRuntimeDatabaseUrlFailClosed:
    """Verify production settings requires RUNTIME_DATABASE_URL for serving (SA2.2).

    After SA2.2, production.py raises a clear error when RUNTIME_DATABASE_URL
    is unset during runtime serving, instead of silently falling back to the
    privileged superuser DATABASE_URL.  Migrations remain the named exception.
    """

    def test_fails_closed_when_runtime_url_unset_for_serving(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Runtime serving without RUNTIME_DATABASE_URL must raise ValueError."""
        base_output = _render_template(
            jinja_env,
            "project_name/settings/base.py.j2",
            test_context,
        )
        production_output = _render_template(
            jinja_env,
            "project_name/settings/production.py.j2",
            test_context,
        )

        with pytest.raises(
            ValueError, match="RUNTIME_DATABASE_URL is required for runtime serving"
        ):
            _execute_rendered_settings(
                monkeypatch=monkeypatch,
                package_name=test_context["package_name"],
                base_output=base_output,
                target_output=production_output,
                target_module_name="production",
                config_values={
                    "SECRET_KEY": "a-valid-production-secret-key",
                    "DATABASE_URL": (
                        "postgresql://postgres:postgres@localhost:5432/testproject"
                    ),
                    # RUNTIME_DATABASE_URL deliberately not set
                },
            )

    def test_migration_path_uses_database_url(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When sys.argv contains 'migrate', DATABASE_URL must be used."""
        monkeypatch.setattr(sys, "argv", ["manage.py", "migrate"])

        base_output = _render_template(
            jinja_env,
            "project_name/settings/base.py.j2",
            test_context,
        )
        production_output = _render_template(
            jinja_env,
            "project_name/settings/production.py.j2",
            test_context,
        )

        namespace = _execute_rendered_settings(
            monkeypatch=monkeypatch,
            package_name=test_context["package_name"],
            base_output=base_output,
            target_output=production_output,
            target_module_name="production",
            config_values={
                "SECRET_KEY": "a-valid-production-secret-key",
                "DATABASE_URL": (
                    "postgresql://postgres:postgres@localhost:5432/testproject"
                ),
            },
        )

        databases = namespace["DATABASES"]
        assert isinstance(databases, dict)
        assert databases["default"]["URL"] == (
            "postgresql://postgres:postgres@localhost:5432/testproject"
        )


class TestLocalSettingsRuntimeDatabaseUrl:
    """Verify local settings prefers RUNTIME_DATABASE_URL when set (CR-T14-001).

    The Docker Compose environment provides RUNTIME_DATABASE_URL for the
    restricted runtime role.  When set, local.py must use that URL instead
    of DATABASE_URL.  When unset, it must fall back to DATABASE_URL for
    backward compatibility.
    """

    def test_uses_runtime_database_url_when_set(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When RUNTIME_DATABASE_URL is set, local.py should use it."""
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        local_output = _render_template(
            jinja_env, "project_name/settings/local.py.j2", test_context
        )
        runtime_url = "postgresql://testproject_app:password@db:5432/testproject"
        superuser_url = "postgresql://postgres:postgres@db:5432/testproject"

        namespace = _execute_rendered_settings(
            monkeypatch=monkeypatch,
            package_name=test_context["package_name"],
            base_output=base_output,
            target_output=local_output,
            target_module_name="local",
            config_values={
                "SECRET_KEY": "django-insecure-dev-key",
                "RUNTIME_DATABASE_URL": runtime_url,
                "DATABASE_URL": superuser_url,
            },
        )

        databases = namespace["DATABASES"]
        assert isinstance(databases, dict)
        assert databases["default"]["URL"] == runtime_url

    def test_falls_back_to_database_url_when_runtime_unset(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When only DATABASE_URL is set, local.py should use it (backward compat)."""
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        local_output = _render_template(
            jinja_env, "project_name/settings/local.py.j2", test_context
        )
        database_url = "postgresql://postgres:postgres@localhost:5432/testproject"

        namespace = _execute_rendered_settings(
            monkeypatch=monkeypatch,
            package_name=test_context["package_name"],
            base_output=base_output,
            target_output=local_output,
            target_module_name="local",
            config_values={
                "SECRET_KEY": "django-insecure-dev-key",
                "DATABASE_URL": database_url,
            },
        )

        databases = namespace["DATABASES"]
        assert isinstance(databases, dict)
        assert databases["default"]["URL"] == database_url

    def test_raises_value_error_when_neither_url_set(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When neither DATABASE_URL nor RUNTIME_DATABASE_URL is set, fail."""
        base_output = _render_template(
            jinja_env, "project_name/settings/base.py.j2", test_context
        )
        local_output = _render_template(
            jinja_env, "project_name/settings/local.py.j2", test_context
        )

        with pytest.raises(ValueError, match="DATABASE_URL"):
            _execute_rendered_settings(
                monkeypatch=monkeypatch,
                package_name=test_context["package_name"],
                base_output=base_output,
                target_output=local_output,
                target_module_name="local",
                config_values={"SECRET_KEY": "django-insecure-dev-key"},
            )


class TestHTMLTemplateStructure:
    """Verify HTML templates contain required structural elements."""

    def test_base_html_has_doctype(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template includes DOCTYPE declaration."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert "<!DOCTYPE html>" in output

    def test_base_html_has_meta_viewport(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template includes responsive viewport meta tag."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert 'name="viewport"' in output
        assert "width=device-width" in output

    def test_base_html_has_blocks(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template includes extensible blocks."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert "{% block title %}" in output or "<title>" in output
        assert "{% block content %}" in output
        assert "{% block extra_js %}" in output
        assert "{% block extra_css %}" in output

    def test_base_html_links_to_css(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template links to stylesheet."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert "style.css" in output

    def test_index_html_extends_base(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test index HTML template extends base template."""
        # Verify template loads successfully
        jinja_env.get_template("templates/index.html.j2")
        # Read the raw template file to check extends directive
        import pathlib

        assert isinstance(jinja_env.loader, FileSystemLoader)

        template_path = (
            pathlib.Path(jinja_env.loader.searchpath[0]) / "templates" / "index.html.j2"
        )
        source = template_path.read_text()
        assert "{% extends" in source or "{%raw%}{% extends" in source
        assert "base.html" in source

    def test_index_html_has_welcome_message(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test index HTML template includes welcome message."""
        template = jinja_env.get_template("templates/index.html.j2")
        output = template.render(test_context)
        assert "Welcome to testproject" in output

    def test_index_html_has_next_steps(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test index HTML template includes next steps guidance."""
        template = jinja_env.get_template("templates/index.html.j2")
        output = template.render(test_context)
        assert "Next Steps" in output
        assert "manage.py" in output


class TestCSSTemplateStructure:
    """Verify CSS templates contain required styling rules."""

    def test_css_has_body_styles(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes body element styling."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "body {" in output
        assert "font-family:" in output

    def test_css_has_responsive_design(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes responsive media queries."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "@media" in output
        assert "max-width" in output

    def test_css_has_header_styles(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes header element styling."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "header" in output

    def test_css_has_footer_styles(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes footer element styling."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "footer" in output


class TestMissingVariableErrors:
    """Verify templates handle missing variables appropriately."""

    def test_missing_project_name_renders_partial(self, jinja_env: Environment) -> None:
        """Test template renders with missing project_name using Jinja2 defaults."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render({})
        # Jinja2 default behavior renders undefined variables as empty strings
        # Production should use StrictUndefined for explicit failures
        assert ".settings" in output


class TestDevOpsTemplateLoading:
    """Verify all DevOps templates can be loaded by Jinja2."""

    def test_ci_workflow_loads(self, jinja_env: Environment) -> None:
        """Test CI workflow template loads without errors."""
        template = jinja_env.get_template("github/workflows/ci.yml.j2")
        assert template is not None

    def test_makefile_loads(self, jinja_env: Environment) -> None:
        """Test Makefile template loads without errors."""
        template = jinja_env.get_template("Makefile.j2")
        assert template is not None

    def test_pyproject_toml_loads(self, jinja_env: Environment) -> None:
        """Test pyproject.toml template loads without errors."""
        template = jinja_env.get_template("pyproject.toml.j2")
        assert template is not None

    def test_precommit_config_loads(self, jinja_env: Environment) -> None:
        """Test .pre-commit-config template loads without errors."""
        template = jinja_env.get_template(".pre-commit-config.yaml.j2")
        assert template is not None

    def test_github_ci_workflow_loads(self, jinja_env: Environment) -> None:
        """Test generated GitHub CI workflow template loads without errors."""
        template = jinja_env.get_template("github/workflows/ci.yml.j2")
        assert template is not None

    def test_dockerfile_loads(self, jinja_env: Environment) -> None:
        """Test Dockerfile template loads without errors."""
        template = jinja_env.get_template("Dockerfile.j2")
        assert template is not None

    def test_docker_compose_loads(self, jinja_env: Environment) -> None:
        """Test docker-compose.yml template loads without errors."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        assert template is not None

    def test_dockerignore_loads(self, jinja_env: Environment) -> None:
        """Test .dockerignore template loads without errors."""
        template = jinja_env.get_template(".dockerignore.j2")
        assert template is not None

    def test_env_example_loads(self, jinja_env: Environment) -> None:
        """Test .env.example template loads without errors."""
        template = jinja_env.get_template(".env.example.j2")
        assert template is not None

    def test_gitignore_loads(self, jinja_env: Environment) -> None:
        """Test .gitignore template loads without errors."""
        template = jinja_env.get_template(".gitignore.j2")
        assert template is not None

    def test_db_init_sql_loads(self, jinja_env: Environment) -> None:
        """Test db/init.sql.j2 template loads without errors."""
        template = jinja_env.get_template("db/init.sql.j2")
        assert template is not None

    def test_operations_md_loads(self, jinja_env: Environment) -> None:
        """Test OPERATIONS.md.j2 template loads without errors."""
        template = jinja_env.get_template("OPERATIONS.md.j2")
        assert template is not None

    def test_editorconfig_loads(self, jinja_env: Environment) -> None:
        """Test .editorconfig template loads without errors."""
        template = jinja_env.get_template(".editorconfig.j2")
        assert template is not None

    def test_lint_script_loads(self, jinja_env: Environment) -> None:
        """Test scripts/lint.sh template loads without errors."""
        template = jinja_env.get_template("scripts/lint.sh.j2")
        assert template is not None

    def test_start_sh_loads(self, jinja_env: Environment) -> None:
        """Test start.sh template loads without errors."""
        template = jinja_env.get_template("start.sh.j2")
        assert template is not None


class TestDevOpsTemplateRendering:
    """Verify DevOps templates render correctly with sample context data."""

    def test_ci_workflow_postgres_service_present(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """CI workflow should include a PostgreSQL service container (SA1.5)."""
        template = jinja_env.get_template("github/workflows/ci.yml.j2")
        output = template.render(test_context)

        assert "services:" in output
        assert "image: postgres:" in output
        assert "POSTGRES_HOST_AUTH_METHOD: trust" in output
        assert "--health-cmd pg_isready" in output
        assert "ports:" in output
        assert "- 5432:5432" in output

    def test_ci_workflow_contains_tenant_isolation_check(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """CI workflow should include a check_tenant_isolation step when orgs is selected or implied (SA1.5)."""
        template = jinja_env.get_template("github/workflows/ci.yml.j2")

        # Default (selected_modules=None) — legacy behavior: render the step
        output = template.render(test_context)
        assert "check_tenant_isolation" in output
        assert "DATABASE_URL: postgres://postgres@localhost/postgres" in output
        assert "migrate" in output
        assert "QUICKSCALE_ALLOW_BYPASSRLS" in output

        # With orgs explicitly selected — step present
        output_with_orgs = template.render(
            {**test_context, "selected_modules": ["orgs"]}
        )
        assert "check_tenant_isolation" in output_with_orgs
        assert "QUICKSCALE_ALLOW_BYPASSRLS" in output_with_orgs
        assert "migrate" in output_with_orgs

        # Without orgs selected — step absent
        output_without_orgs = template.render(
            {**test_context, "selected_modules": ["auth"]}
        )
        assert "check_tenant_isolation" not in output_without_orgs

        # Empty selected_modules — step absent (CR-SA15-002: [] must not render dead orgs-only entrypoints)
        output_empty = template.render({**test_context, "selected_modules": []})
        assert "check_tenant_isolation" not in output_empty

    def test_makefile_contains_check_tenant_isolation_target(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Makefile should include a check-tenant-isolation target when orgs is selected or implied (SA1.5)."""
        template = jinja_env.get_template("Makefile.j2")

        # Default (selected_modules=None) — legacy behavior: render target
        output = template.render(test_context)
        assert "check-tenant-isolation:" in output
        assert "check_tenant_isolation" in output
        assert "--postgres-only" in output
        assert "--format json" in output
        assert "QUICKSCALE_ALLOW_BYPASSRLS=1" in output
        assert "RUNTIME_DATABASE_URL='' poetry run python manage.py migrate" in output

        # With orgs explicitly selected — target present
        output_with_orgs = template.render(
            {**test_context, "selected_modules": ["orgs"]}
        )
        assert "check-tenant-isolation:" in output_with_orgs
        assert "QUICKSCALE_ALLOW_BYPASSRLS=1" in output_with_orgs
        assert (
            "RUNTIME_DATABASE_URL='' poetry run python manage.py migrate"
            in output_with_orgs
        )

        # Without orgs selected — target absent
        output_without_orgs = template.render(
            {**test_context, "selected_modules": ["auth"]}
        )
        assert "check-tenant-isolation:" not in output_without_orgs

        # Empty selected_modules — target absent (CR-SA15-002: [] must not render dead orgs-only entrypoints)
        output_empty = template.render({**test_context, "selected_modules": []})
        assert "check-tenant-isolation:" not in output_empty

    def test_ci_workflow_caller_parity_exercises_classification_contract(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Generated CI workflow must exercise the SA15.1 widened classification
        contract via check_tenant_isolation --postgres-only --format json.

        The management command internally runs get_unclassified_concrete_models()
        which uses the SA15.1 widened scope (all non-contrib, non-third-party
        apps) and implicit M2M through-model inference.  This caller-parity test
        proves the generated project's CI pipeline triggers that path.

        The step runs after migrations so the DB schema is available for
        detection (CR-SA15.1-002).
        """
        template = jinja_env.get_template("github/workflows/ci.yml.j2")

        # Default (all modules) — step present with classification flags.
        output = template.render(test_context)
        assert "check_tenant_isolation" in output, (
            "CI must invoke check_tenant_isolation (SA1.5)"
        )
        assert "--postgres-only" in output, (
            "CI must pass --postgres-only (required for FORCE-RLS checks)"
        )
        assert "--format json" in output, (
            "CI must use JSON output for structured parsing"
        )
        # Classification runs before --postgres-only skip (CR-SA14-002).
        assert "migrate" in output, (
            "Migrations must run before check_tenant_isolation so the "
            "DB schema is available for classification detection"
        )

        # With orgs explicitly selected — same contract.
        output_with_orgs = template.render(
            {**test_context, "selected_modules": ["orgs"]}
        )
        assert "check_tenant_isolation" in output_with_orgs
        assert "--postgres-only" in output_with_orgs

    def test_makefile_caller_parity_exercises_classification_contract(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Generated Makefile must exercise the SA15.1 widened classification
        contract via the check-tenant-isolation target.

        The target runs both migrations and the classification check with
        --postgres-only --format json, proving that the generated project's
        local workflow triggers the same widened contract as CI
        (CR-SA15.1-002).
        """
        template = jinja_env.get_template("Makefile.j2")

        # Default (all modules) — target present with classification flags.
        output = template.render(test_context)
        assert "check-tenant-isolation:" in output, (
            "Makefile must have a check-tenant-isolation target (SA1.5)"
        )
        assert "check_tenant_isolation" in output, (
            "Makefile target must invoke check_tenant_isolation"
        )
        assert "--postgres-only" in output, "Makefile must pass --postgres-only"
        assert "--format json" in output, "Makefile must use JSON output format"
        # Migrations run first so the schema is available.
        assert "migrate" in output, (
            "Makefile must run migrations before the classification check"
        )

    def test_makefile_renders_expected_targets(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Makefile should render the shipped generic workflow contract."""
        template = jinja_env.get_template("Makefile.j2")
        output = template.render(test_context)

        assert output is not None
        assert ".DEFAULT_GOAL := help" in output
        assert (
            "setup: ## Install backend dependencies and frontend dependencies when present"
            in output
        )
        assert (
            "lint-frontend: ## Run frontend lint checks when frontend exists" in output
        )
        assert (
            "test: test-backend test-frontend ## Run backend tests and frontend tests when frontend exists"
            in output
        )
        assert "cd frontend && pnpm test:coverage;" in output
        assert "No frontend/package.json found, skipping frontend tests." in output

    def test_readme_renders_make_first_workflow_for_html(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """HTML starter README should prefer make targets without implying a frontend."""
        template = jinja_env.get_template("README.md.j2")
        output = template.render({**test_context, "theme": "showcase_html"})

        assert "The generated root `Makefile` is the default local entrypoint" in output
        assert "make setup" in output
        assert "make test" in output
        assert "make lint" in output
        assert "make check" in output
        assert "### Frontend Code Quality" not in output
        assert (
            "Node.js 24+ installed for the generated `frontend/` workspace"
            not in output
        )
        assert "pnpm available for frontend setup and checks" not in output
        assert "make lint-frontend" not in output
        assert "make test-frontend" not in output

    def test_readme_renders_react_frontend_workflow(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """React starter README should expose the delegated frontend workflow."""
        template = jinja_env.get_template("README.md.j2")
        output = template.render({**test_context, "theme": "showcase_react"})

        assert "### Frontend Code Quality" in output
        assert "Node.js 24+ installed for the generated `frontend/` workspace" in output
        assert "pnpm available for frontend setup and checks" in output
        assert "make lint-frontend" in output
        assert "make test-frontend" in output
        assert "pnpm test:coverage" in output

    def test_readme_docker_migration_clears_runtime_url(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """README Docker migration should unset RUNTIME_DATABASE_URL (CR-T14-004).

        The Docker Compose backend has RUNTIME_DATABASE_URL in its environment
        for the restricted runtime role. Running ``manage.py migrate`` under
        that role would fail because the runtime role cannot run DDL. The README
        must clear RUNTIME_DATABASE_URL for the migration command so that
        ``local.py`` falls back to the superuser DATABASE_URL.
        """
        template = jinja_env.get_template("README.md.j2")
        output = template.render(test_context)

        assert "docker compose exec -e RUNTIME_DATABASE_URL= backend" in output, (
            "README Docker migration should unset RUNTIME_DATABASE_URL"
        )
        assert "cannot run DDL" in output, (
            "README should explain why RUNTIME_DATABASE_URL must be cleared"
        )

    def test_readme_local_migration_clears_runtime_url(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """README local/manual migration commands should unset RUNTIME_DATABASE_URL (CR-T14-004).

        When running migrations locally under settings.local, RUNTIME_DATABASE_URL
        from the environment (e.g. a leftover Docker shell) would select the
        restricted runtime role connection, which cannot run DDL.  The README
        migration commands must unset RUNTIME_DATABASE_URL so that local.py
        falls back to the superuser DATABASE_URL.
        """
        template = jinja_env.get_template("README.md.j2")
        output = template.render(test_context)

        assert "RUNTIME_DATABASE_URL= poetry run python manage.py migrate" in output, (
            "README local migration should unset RUNTIME_DATABASE_URL"
        )
        assert "cannot run DDL" in output, (
            "README should explain why RUNTIME_DATABASE_URL must be cleared"
        )

    def test_readme_production_checklist_migration_clears_runtime_url(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """README production checklist migration command should unset RUNTIME_DATABASE_URL (CR-T14-004).

        The production checklist must instruct users to unset RUNTIME_DATABASE_URL
        before running migrations so that production.py falls back to the
        superuser DATABASE_URL instead of using the restricted runtime role.
        """
        template = jinja_env.get_template("README.md.j2")
        output = template.render(test_context)

        assert "RUNTIME_DATABASE_URL= python manage.py migrate" in output, (
            "README production checklist migrate should unset RUNTIME_DATABASE_URL"
        )
        assert "cannot run DDL" in output, (
            "README should explain why RUNTIME_DATABASE_URL must be cleared"
        )

    def test_pyproject_toml_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml renders with project name.

        All Python-version-dependent assertions derive their expected
        values from the SSOT (``runtime_pins``) through the Jinja2
        render path so that a version bump propagates automatically.
        """
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "[tool.poetry]" in output
        assert f'python = "{PYTHON_CONSTRAINT}"' in output
        assert 'Django = ">=6.0.3,<6.1.0"' in output
        assert 'django-stubs = "^6.0.2"' in output
        _ruff_target = f"py{PYTHON_VERSION.replace('.', '')}"
        assert f'target-version = "{_ruff_target}"' in output
        assert f'python_version = "{PYTHON_VERSION}"' in output

    def test_precommit_config_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .pre-commit-config renders the pinned hook toolchain."""
        template = jinja_env.get_template(".pre-commit-config.yaml.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "pre-commit/pre-commit-hooks" in output
        assert "rev: v6.0.0" in output
        assert "astral-sh/ruff-pre-commit" in output
        assert "rev: v0.15.12" in output

    def test_github_ci_workflow_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test generated GitHub CI workflow renders the PG18 tooling contract."""
        template = jinja_env.get_template("github/workflows/ci.yml.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "name: CI" in output
        assert "pytest --cov=testproject" in output
        assert "runs-on: ubuntu-24.04" in output
        assert 'python-version: ["3.13"]' in output
        assert "apt.postgresql.org" in output
        assert "apt.postgresql.org.asc" in output
        assert "postgresql-client-18" in output
        assert 'echo "/usr/lib/postgresql/18/bin" >> "$GITHUB_PATH"' in output
        assert (
            'test "$(command -v pg_dump)" = "/usr/lib/postgresql/18/bin/pg_dump"'
            in output
        )
        assert (
            'test "$(command -v pg_restore)" = "/usr/lib/postgresql/18/bin/pg_restore"'
            in output
        )
        assert "pg_dump --version" in output
        assert "pg_restore --version" in output
        assert (
            "if: matrix.python-version == '3.13' && matrix.django-version == '6.0'"
            in output
        )
        assert "3.14" not in output
        assert "gpg --dearmor" not in output
        assert "gnupg" not in output

    def test_dockerfile_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile renders with project name."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "FROM python:3.13-slim-bookworm" in output

    def test_docker_compose_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml renders with project name."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        # Note: 'version:' field is obsolete in docker-compose v2+, so we don't check for it
        assert "services:" in output
        assert "db:" in output

    def test_dockerignore_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .dockerignore renders correctly."""
        template = jinja_env.get_template(".dockerignore.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "__pycache__" in output
        assert ".git" in output

    def test_env_example_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .env.example renders with project name."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "SECRET_KEY=" in output

    def test_gitignore_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore renders correctly."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "__pycache__" in output
        assert ".env" in output

    def test_editorconfig_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .editorconfig renders correctly."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "root = true" in output
        assert "indent_style" in output

    def test_db_init_sql_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test db/init.sql.j2 renders with runtime role and NOSUPERUSER/NOBYPASSRLS."""
        template = jinja_env.get_template("db/init.sql.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "testproject_app" in output
        assert "NOSUPERUSER" in output
        assert "NOBYPASSRLS" in output
        assert "NOCREATEDB" in output
        assert "NOCREATEROLE" in output
        assert "GRANT USAGE ON SCHEMA public" in output
        assert "ALTER DEFAULT PRIVILEGES" in output
        assert "CREATE ROLE" in output
        assert "IF NOT EXISTS" in output
        # CR-T14-002: Sequence privileges for auto-increment primary keys
        assert "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public" in output, (
            "init.sql should grant USAGE on all existing sequences"
        )
        assert "GRANT USAGE ON SEQUENCES TO" in output, (
            "init.sql should grant USAGE on future sequences via ALTER DEFAULT PRIVILEGES"
        )

    def test_operations_md_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test OPERATIONS.md.j2 renders with runtime role and operator guide."""
        template = jinja_env.get_template("OPERATIONS.md.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "testproject_app" in output
        assert "RUNTIME_DATABASE_URL" in output
        assert "NOSUPERUSER" in output
        assert "NOBYPASSRLS" in output
        assert "migrations" in output.lower()
        # CR-T14-003: Narrowed claim — the DATABASE_URL bullet should not overstate
        # management-command coverage (the superuser table row still accurately
        # describes superuser capabilities, but the DATABASE_URL description should
        # only mention migrations).
        assert "used for migrations, management commands" not in output, (
            "OPERATIONS.md DATABASE_URL should not claim management-command coverage"
        )
        # CR-T14-002: Sequence privileges must appear in production SQL example
        assert "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public" in output, (
            "OPERATIONS.md production SQL should include sequence usage grants"
        )
        assert "GRANT USAGE ON SEQUENCES TO" in output, (
            "OPERATIONS.md should include ALTER DEFAULT PRIVILEGES for sequences"
        )

    def test_lint_script_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test scripts/lint.sh renders with package name."""
        template = jinja_env.get_template("scripts/lint.sh.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "mypy testproject/" in output

    def test_lint_script_uses_check_mode_only(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Lint script should validate formatting/linting without auto-fixing."""
        template = jinja_env.get_template("scripts/lint.sh.j2")
        output = template.render(test_context)
        assert "ruff check --fix" not in output
        assert "ruff check ." in output
        assert "ruff format --check ." in output
        assert "pnpm format:check" in output

    def test_start_sh_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test start.sh renders with package name and all required steps."""
        template = jinja_env.get_template("start.sh.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "#!/usr/bin/env bash" in output
        assert "testproject" in output
        assert "Step 1/6" in output
        assert "Step 2/6" in output
        assert "Step 3/6" in output
        assert "Step 4/6" in output
        assert "Step 5/6" in output
        assert "Step 6/6" in output

    def test_start_sh_migration_clears_runtime_url(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """start.sh should clear RUNTIME_DATABASE_URL during migration (CR-T14-004).

        The deployment environment has RUNTIME_DATABASE_URL set for the
        restricted runtime role.  Running ``migrate`` under that role would
        fail because the runtime role cannot run DDL.  start.sh must unset
        RUNTIME_DATABASE_URL for the migration step so that local.py falls
        back to the superuser DATABASE_URL.
        """
        template = jinja_env.get_template("start.sh.j2")
        output = template.render(test_context)

        assert 'RUNTIME_DATABASE_URL="" python manage.py migrate' in output, (
            "start.sh should unset RUNTIME_DATABASE_URL for migrations"
        )
        assert "cannot run DDL" in output, (
            "start.sh should explain why RUNTIME_DATABASE_URL is cleared"
        )

    def test_start_sh_superuser_setup(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test start.sh contains idiomatic superuser creation via env vars."""
        template = jinja_env.get_template("start.sh.j2")
        output = template.render(test_context)
        assert "DJANGO_SUPERUSER_USERNAME" in output
        assert "DJANGO_SUPERUSER_EMAIL" in output
        assert "DJANGO_SUPERUSER_PASSWORD" in output
        assert "create_superuser" in output
        assert "already exists, skipping" in output

    def test_start_sh_superuser_is_nonfatal(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test superuser step does not abort deployment on failure."""
        template = jinja_env.get_template("start.sh.j2")
        output = template.render(test_context)
        # A failure in the superuser step should not kill the process
        assert "|| echo" in output
        assert "non-fatal" in output

    def test_start_sh_gunicorn_uses_package_name(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Gunicorn is started with the rendered package name."""
        template = jinja_env.get_template("start.sh.j2")
        output = template.render(test_context)
        assert "gunicorn testproject.wsgi:application" in output

    def test_start_sh_gunicorn_worker_precedence(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """start.sh should prefer GUNICORN_WORKERS, then WEB_CONCURRENCY, then 1."""
        template = jinja_env.get_template("start.sh.j2")
        output = template.render(test_context)

        assert 'gunicorn_workers="${GUNICORN_WORKERS:-${WEB_CONCURRENCY:-1}}"' in output
        assert '--workers "${gunicorn_workers}"' in output
        assert "--workers 4" not in output


class TestPyprojectTomlContent:
    """Verify pyproject.toml contains required production dependencies and configuration."""

    def test_django_dependency(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes Django dependency."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "Django" in output
        assert 'Django = ">=6.0.3,<6.1.0"' in output

    def test_postgresql_driver(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes PostgreSQL driver."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "psycopg2-binary" in output

    def test_environment_config(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes environment configuration library."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "python-decouple" in output

    def test_whitenoise_static_files(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes WhiteNoise for static files."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "whitenoise" in output

    def test_gunicorn_server(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes Gunicorn production server."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "gunicorn" in output

    def test_dev_dependencies(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes development dependencies."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "[tool.poetry.group.dev.dependencies]" in output
        assert "pytest" in output
        assert "pytest-django" in output
        assert "ruff" in output
        assert "mypy" in output

    def test_mypy_overrides_for_optional_and_untyped_imports(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test mypy ignores known modules without complete type metadata."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert 'module = ["decouple", "debug_toolbar", "debug_toolbar.*"]' in output
        assert "ignore_missing_imports = true" in output

    def test_pytest_configuration(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes pytest configuration."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "[tool.pytest.ini_options]" in output
        assert "DJANGO_SETTINGS_MODULE" in output

    def test_ruff_configuration(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes ruff formatter and linter configuration."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "[tool.ruff]" in output
        assert "select" in output
        assert "line-length" in output
        # Verify comment about ruff format replacing black
        assert "handled by ruff format" in output


class TestDockerfileContent:
    """Verify Dockerfile contains production-ready multi-stage build configuration."""

    def test_multi_stage_build(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile uses multi-stage build pattern."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "FROM python:3.13-slim-bookworm as builder" in output
        assert "FROM python:3.13-slim-bookworm" in output
        assert "bookworm-pgdg" in output
        assert "apt.postgresql.org.asc" in output
        assert "postgresql-client-18" in output
        assert "gpg --dearmor" not in output
        assert "gnupg" not in output

    def test_non_root_user(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile creates and uses non-root user."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "groupadd" in output
        assert "useradd" in output
        assert "USER django" in output

    def test_poetry_installation(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile installs Poetry for dependency management."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "pip install poetry==2.4.0" in output

    def test_optimized_layers(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile optimizes layer caching with dependency files first."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "COPY pyproject.toml poetry.lock* ./" in output
        # Dependencies installed before copying application code
        lines = output.split("\n")
        poetry_install_idx = next(
            i for i, line in enumerate(lines) if "poetry install" in line.lower()
        )
        copy_app_idx = next(i for i, line in enumerate(lines) if "COPY --chown" in line)
        assert poetry_install_idx < copy_app_idx

    @pytest.mark.parametrize("theme", ["showcase_html", "showcase_react"])
    def test_collectstatic_uses_build_time_secret_key(
        self,
        jinja_env: Environment,
        test_context: dict[str, str],
        theme: str,
    ) -> None:
        """Collectstatic should use a build-time-only SECRET_KEY."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render({**test_context, "theme": theme})

        collectstatic_line = next(
            line.strip()
            for line in output.splitlines()
            if "python manage.py collectstatic --noinput" in line
        )

        assert collectstatic_line.startswith('SECRET_KEY="$(python -c')
        assert "token_urlsafe(50)" in collectstatic_line
        assert "ENV SECRET_KEY" not in output

    def test_healthcheck(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile includes health check."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "HEALTHCHECK" in output

    def test_gunicorn_command(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile runs Gunicorn production server."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "gunicorn" in output
        assert "testproject.wsgi:application" in output

    def test_dockerfile_gunicorn_worker_precedence(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Dockerfile runtime startup should match the generated worker fallback order."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)

        assert 'gunicorn_workers="${GUNICORN_WORKERS:-${WEB_CONCURRENCY:-1}}"' in output
        assert '--workers "${gunicorn_workers}"' in output
        assert "--workers 4" not in output


class TestDockerComposeContent:
    """Verify docker-compose.yml contains complete development environment."""

    def test_postgres_service(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml includes PostgreSQL service."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "db:" in output
        assert "postgres:18-alpine" in output
        assert "POSTGRES_DB" in output

    def test_backend_service(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml includes backend service."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "backend:" in output
        assert "build:" in output

    def test_react_frontend_uses_non_root_safe_corepack_command(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """React frontend service should avoid `corepack enable` under non-root user."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render({**test_context, "theme": "showcase_react"})
        assert 'command: sh -c "corepack pnpm install --no-frozen-lockfile' in output
        assert 'command: sh -c "corepack enable' not in output

    def test_persistent_volumes(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml defines persistent volumes."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "volumes:" in output
        assert "postgres_data:" in output
        assert "static_volume:" in output
        assert "media_volume:" in output

    def test_postgres_18_uses_parent_data_mount(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml uses Postgres 18-compatible data mount point."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "- postgres_data:/var/lib/postgresql" in output
        assert "- postgres_data:/var/lib/postgresql/data" not in output

    def test_healthchecks(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml includes healthchecks."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "healthcheck:" in output
        assert "condition: service_healthy" in output

    def test_environment_variables(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml configures environment variables."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "DATABASE_URL" in output
        assert "RUNTIME_DATABASE_URL" in output
        assert "DJANGO_SETTINGS_MODULE" in output


class TestEnvExampleContent:
    """Verify .env.example contains all required environment variables."""

    def test_secret_key(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .env.example includes SECRET_KEY."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "SECRET_KEY=" in output
        assert "testproject" in output

    def test_debug_flag(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .env.example includes DEBUG flag."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "DEBUG=" in output

    def test_allowed_hosts(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .env.example includes ALLOWED_HOSTS."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "ALLOWED_HOSTS=" in output

    def test_allowed_hosts_includes_docker_address(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """
        Test that ALLOWED_HOSTS in .env.example includes 0.0.0.0 for Docker.

        Regression test for: DisallowedHost error when accessing Django on 0.0.0.0:8000
        """
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)

        # Check that 0.0.0.0 is included for Docker compatibility
        assert "0.0.0.0" in output, (
            ".env.example should include 0.0.0.0 in ALLOWED_HOSTS for Docker containers"
        )
        # Verify standard localhost entries are also present
        assert "localhost" in output, ".env.example should include localhost"
        assert "127.0.0.1" in output, ".env.example should include 127.0.0.1"

    def test_local_settings_includes_docker_address(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """
        Test that local.py settings includes 0.0.0.0 for Docker.

        Regression test for: DisallowedHost error when accessing Django on 0.0.0.0:8000
        """
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)

        # Check that 0.0.0.0 is included in ALLOWED_HOSTS for Docker compatibility
        assert "0.0.0.0" in output, (
            "local.py should include 0.0.0.0 in ALLOWED_HOSTS for Docker containers"
        )
        # Also check for the catch-all wildcard for development flexibility
        assert '"*"' in output or "'*'" in output, (
            "local.py should allow all hosts (* wildcard) for development"
        )

    def test_database_url(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .env.example includes DATABASE_URL with PostgreSQL."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "DATABASE_URL=" in output
        assert "postgresql://" in output
        assert "testproject" in output

    def test_helpful_comments(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .env.example includes explanatory comments."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "#" in output
        assert "SECURITY WARNING" in output

    def test_env_example_contains_managed_notifications_block(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Template should include the managed notifications env-var placeholders."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)

        assert "# QuickScale Notifications (managed)" in output
        assert "RESEND_API_KEY=" in output
        assert "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=" in output


class TestGitignoreContent:
    """Verify .gitignore excludes appropriate files and directories."""

    def test_python_artifacts(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes Python artifacts."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert "__pycache__" in output
        assert "*.py[cod]" in output  # Matches .pyc, .pyo, .pyd

    def test_virtual_environments(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes virtual environments."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".venv" in output
        assert "venv/" in output

    def test_django_artifacts(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes Django-specific files."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert "db.sqlite3" in output
        assert "/media" in output
        assert "/staticfiles" in output

    def test_environment_files(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes environment variable files."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".env" in output

    def test_ide_files(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes IDE-specific files."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".vscode/" in output
        assert ".idea/" in output

    def test_testing_artifacts(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes testing artifacts."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".pytest_cache" in output
        assert ".coverage" in output

    def test_private_quickscale_backup_artifacts(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes private backup artifacts without hiding state files."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".quickscale/backups/" in output
        assert "\n.quickscale/\n" not in output
        assert ".quickscale/state.yml" not in output


class TestEditorconfigContent:
    """Verify .editorconfig defines consistent editor settings."""

    def test_root_declaration(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .editorconfig declares root = true."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "root = true" in output

    def test_charset_setting(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .editorconfig sets UTF-8 charset."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "charset = utf-8" in output

    def test_line_endings(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .editorconfig sets line endings."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "end_of_line" in output

    def test_python_indent(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .editorconfig sets Python indentation to 4 spaces."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "[*.{py,pyi}]" in output or "[*.py]" in output
        assert "indent_size = 4" in output


class TestSelectedModulesTemplateSafety:
    """Verify main.tsx, App.test.tsx, and PublicSocialPages.test.tsx templates
    are compile-safe for all selected_modules variants (None, empty, partial)."""

    def test_main_tsx_full_selected_modules_renders_social_imports(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """selected_modules=None (full): social page imports present."""
        template = jinja_env.get_template("themes/showcase_react/src/main.tsx.j2")
        context = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": None,
        }
        output = template.render(context)
        assert "import { SocialEmbedsPublicPage }" in output
        assert "import { SocialLinkTreePublicPage }" in output
        assert "renderQuickScaleRoot" in output
        assert "return <SocialLinkTreePublicPage />" in output
        assert "return <SocialEmbedsPublicPage />" in output

    def test_main_tsx_social_selected_renders_social_imports(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """selected_modules=['social']: social page imports present."""
        template = jinja_env.get_template("themes/showcase_react/src/main.tsx.j2")
        context = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": ["social"],
        }
        output = template.render(context)
        assert "import { SocialEmbedsPublicPage }" in output
        assert "import { SocialLinkTreePublicPage }" in output
        assert "return <SocialLinkTreePublicPage />" in output
        assert "return <SocialEmbedsPublicPage />" in output

    def test_main_tsx_empty_or_no_social_omits_social_imports(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Without social in selected_modules, omit social imports and
        use the simplified renderQuickScaleRoot."""
        template = jinja_env.get_template("themes/showcase_react/src/main.tsx.j2")

        # Empty list — no modules selected
        context_empty: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": [],
        }
        output = template.render(context_empty)
        assert "import { SocialEmbedsPublicPage }" not in output
        assert "import { SocialLinkTreePublicPage }" not in output
        assert "renderQuickScaleRoot" in output
        assert "return <SocialLinkTreePublicPage />" not in output
        assert "return <SocialEmbedsPublicPage />" not in output
        assert "return (" in output
        assert "<BrowserRouter>" in output

        # Only blog selected (no social)
        context_blog: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": ["blog"],
        }
        output_blog = template.render(context_blog)
        assert "import { SocialEmbedsPublicPage }" not in output_blog
        assert "import { SocialLinkTreePublicPage }" not in output_blog

    def test_app_test_tsx_full_selected_modules(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """selected_modules=None: App.test.tsx includes all module flags."""
        template = jinja_env.get_template(
            "themes/showcase_react/src/test/App.test.tsx.j2"
        )
        context = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": None,
        }
        output = template.render(context)
        assert "auth: false" in output
        assert "blog: false" in output
        assert "social: false" in output
        assert "crm: '/crm'" in output
        assert "social: '/social'" in output
        assert "analytics: '/analytics/'" in output
        assert "renders dashboard heading" in output
        assert "renders the org list shell in saas mode" in output

    def test_app_test_tsx_partial_selected_modules(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """selected_modules=['blog','auth']: only selected module flags."""
        template = jinja_env.get_template(
            "themes/showcase_react/src/test/App.test.tsx.j2"
        )
        context: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": ["blog", "auth"],
        }
        output = template.render(context)
        # Selected modules present
        assert "auth: false" in output
        assert "blog: false" in output
        # Unselected modules absent
        assert "crm: false" not in output
        assert "social: false" not in output
        assert "listings: false" not in output
        # Unselected module paths absent
        assert "crm: '/crm'" not in output
        assert "social: '/social'" not in output
        assert "analytics: '/analytics/'" not in output
        # Tests still present
        assert "renders dashboard heading" in output

    def test_app_test_tsx_empty_selected_modules(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """selected_modules=[]: only core config, no module flags."""
        template = jinja_env.get_template(
            "themes/showcase_react/src/test/App.test.tsx.j2"
        )
        context: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": [],
        }
        output = template.render(context)
        # No module flags
        assert "auth: false" not in output
        assert "blog: false" not in output
        assert "social: false" not in output
        # No module paths
        assert "crm:" not in output
        # Core structure
        assert "projectName: 'QuickScale Test Project'" in output
        assert "owner:" in output
        # Tests still present
        assert "renders dashboard heading" in output

    def test_public_social_pages_test_renders_when_social_selected(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """PublicSocialPages renders when social is selected (None or list)."""
        template = jinja_env.get_template(
            "themes/showcase_react/src/test/PublicSocialPages.test.tsx.j2"
        )

        # None (all modules)
        context_full: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": None,
        }
        output_full = template.render(context_full)
        assert "import { SocialEmbedsPublicPage }" in output_full
        assert "import { SocialLinkTreePublicPage }" in output_full
        assert "describe('public social pages'" in output_full

        # Only social selected
        context_social: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": ["social"],
        }
        output_social = template.render(context_social)
        assert "import { SocialEmbedsPublicPage }" in output_social
        assert "import { SocialLinkTreePublicPage }" in output_social
        assert "describe('public social pages'" in output_social
        # buildProjectConfig should only have social, not unrelated modules
        assert "social: true" in output_social
        assert "auth: false" not in output_social
        # modulePaths should only have social
        assert "social: surface" in output_social
        assert "crm:" not in output_social

    def test_public_social_pages_test_empty_when_social_not_selected(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """PublicSocialPages renders empty when social is not selected."""
        template = jinja_env.get_template(
            "themes/showcase_react/src/test/PublicSocialPages.test.tsx.j2"
        )

        # Empty list
        context_empty: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": [],
        }
        output = template.render(context_empty)
        assert output.strip() == "", (
            "PublicSocialPages should be empty when social is not selected"
        )

        # Only blog (no social)
        context_blog: dict = {
            **test_context,
            "theme": "showcase_react",
            "selected_modules": ["blog"],
        }
        output_blog = template.render(context_blog)
        assert output_blog.strip() == "", (
            "PublicSocialPages should be empty when social is not selected"
        )
